"""
RAGAS Evaluation Pipeline — SSI RAG Chatbot
============================================
Chạy đầy đủ:
    cd backend
    python -m app.evaluation.ragas_eval

Chạy nhanh (3 câu hỏi đầu):
    python -m app.evaluation.ragas_eval --quick

Các bước thực hiện:
    1. Khởi tạo RAGPipeline (FAISS + BM25 + Gemini)
    2. Chạy pipeline trên TEST_DATASET → thu thập (question, answer, contexts, ground_truth)
    3. Tính 4 RAGAS metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall
    4. In báo cáo chi tiết từng câu + tổng hợp
    5. Lưu kết quả vào MongoDB (eval_results collection)
    6. Xuất CSV để phân tích offline
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# ── Setup logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Thêm backend/ vào sys.path để import nội bộ hoạt động dù chạy từ thư mục nào
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT / ".env")

# ── RAGAS imports ──────────────────────────────────────────────────────────────
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# ── Project imports ────────────────────────────────────────────────────────────
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.core.rag_pipeline import RAGPipeline
from app.core.retriever import HybridRetriever
from app.db.mongodb import get_mongo_client, save_eval_result
from app.evaluation.testset import TEST_DATASET

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Khởi tạo RAG Pipeline
# ══════════════════════════════════════════════════════════════════════════════

def build_pipeline() -> tuple[RAGPipeline, GoogleGenerativeAIEmbeddings]:
    """Load FAISS index, BM25 index và tạo RAGPipeline."""
    print("\n[Bước 1/5] Khởi tạo RAG Pipeline...")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2",
        google_api_key=settings.GOOGLE_API_KEY,
    )

    vectorstore = FAISS.load_local(
        settings.DB_FAISS_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    print(f"  ✓ FAISS index: {vectorstore.index.ntotal} vectors")

    retriever = HybridRetriever(
        vectorstore=vectorstore,
        bm25_index_path=settings.BM25_INDEX_PATH,
        k=settings.RETRIEVER_K,
    )
    print(f"  ✓ BM25 index: {len(retriever.bm25_docs)} documents")

    pipeline = RAGPipeline(retriever, settings.RETRIEVER_SCORE_THRESHOLD)
    print("  ✓ RAGPipeline sẵn sàng (Gemini 2.5 Flash)")

    return pipeline, embeddings


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Chạy pipeline trên toàn bộ test set
# ══════════════════════════════════════════════════════════════════════════════

async def collect_pipeline_outputs(
    pipeline: RAGPipeline,
    dataset: list[dict],
) -> tuple[list[str], list[str], list[list[str]], list[str]]:
    """
    Chạy RAG pipeline trên từng câu hỏi, trả về 4 danh sách song song:
        questions, answers, contexts (list of str per question), ground_truths
    """
    print(f"\n[Bước 2/5] Chạy RAG pipeline trên {len(dataset)} câu hỏi...")

    questions, answers, contexts, ground_truths = [], [], [], []

    for i, item in enumerate(dataset, 1):
        q = item["question"]
        gt = item["ground_truth"]
        print(f"  [{i:02d}/{len(dataset):02d}] {q[:70]}...")

        try:
            result = await pipeline.ainvoke(q, chat_history=[])
            answer = result["answer"]
            docs = result["retrieved_docs"]
            ctx_texts = [d.page_content for d in docs] if docs else ["Không tìm thấy ngữ cảnh phù hợp."]
        except Exception as exc:
            logger.error("Pipeline lỗi cho câu hỏi %d: %s", i, exc)
            answer = "Lỗi pipeline."
            ctx_texts = [""]

        questions.append(q)
        answers.append(answer)
        contexts.append(ctx_texts)
        ground_truths.append(gt)

        print(f"       → {len(docs) if docs else 0} docs retrieved | answer: {answer[:60]}...")

    return questions, answers, contexts, ground_truths


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Tính RAGAS metrics
# ══════════════════════════════════════════════════════════════════════════════

def _gemini_is_finished(result) -> bool:
    """
    Ragas 0.2.6 kiểm tra finish_reason == 'stop' (lowercase).
    Gemini trả về 'STOP' (uppercase) → ragas luôn nhận False → LLMDidNotFinishException.
    Parser này chuẩn hoá về lowercase trước khi so sánh.
    """
    from langchain_core.outputs import ChatGeneration
    for g in result.flatten():
        resp = g.generations[0][0]
        # Ưu tiên generation_info
        if resp.generation_info:
            reason = resp.generation_info.get("finish_reason", "")
            if reason:
                return str(reason).upper() == "STOP"
        # Fallback: response_metadata trên ChatGeneration
        if isinstance(resp, ChatGeneration) and resp.message is not None:
            meta = resp.message.response_metadata
            reason = meta.get("finish_reason") or meta.get("stop_reason", "")
            if reason:
                return str(reason).upper() in ("STOP", "END_TURN")
    return True  # không có info → giả sử đã xong


def compute_ragas_metrics(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
    embeddings: GoogleGenerativeAIEmbeddings,
) -> dict:
    """
    Tính 4 RAGAS metrics:
      - Faithfulness       : answer có grounded trong context không? (không cần ground_truth)
      - Answer Relevancy   : answer có trả lời đúng trọng tâm câu hỏi? (không cần ground_truth)
      - Context Precision  : rank của docs liên quan có cao hơn không liên quan? (cần ground_truth)
      - Context Recall     : context có chứa đủ thông tin để trả lời? (cần ground_truth)
    """
    print("\n[Bước 3/5] Tính RAGAS metrics (Gemini làm judge)...")
    print("  Đây có thể mất 3–10 phút tuỳ số lượng câu hỏi và API rate limit.\n")

    ragas_dataset = Dataset.from_dict({
        "question":     questions,
        "answer":       answers,
        "contexts":     contexts,
        "ground_truth": ground_truths,
    })

    # Truyền is_finished_parser để xử lý 'STOP' (uppercase) của Gemini
    gemini_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY,
        ),
        is_finished_parser=_gemini_is_finished,
    )
    gemini_embeddings = LangchainEmbeddingsWrapper(embeddings)

    result = evaluate(
        dataset=ragas_dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=gemini_llm,
        embeddings=gemini_embeddings,
        raise_exceptions=False,
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — In báo cáo chi tiết
# ══════════════════════════════════════════════════════════════════════════════

_TARGETS = {
    "faithfulness":      0.80,
    "answer_relevancy":  0.75,
    "context_precision": 0.70,
    "context_recall":    0.70,
}

_METRIC_LABELS = {
    "faithfulness":      "Faithfulness       (không hallucinate)",
    "answer_relevancy":  "Answer Relevancy   (câu trả lời đúng trọng tâm)",
    "context_precision": "Context Precision  (docs liên quan được rank cao)",
    "context_recall":    "Context Recall     (context đủ thông tin)",
}


def _bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def _status(score: float, target: float) -> str:
    if score >= target:
        return "PASS ✓"
    elif score >= target * 0.9:
        return "WARN ~"
    return "FAIL ✗"


def print_report(
    result,
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
    dataset: list[dict],
) -> None:
    print("\n[Bước 4/5] Tạo báo cáo...")

    W = 72
    print("\n" + "═" * W)
    print("  KẾT QUẢ ĐÁNH GIÁ RAG PIPELINE — SSI Chatbot")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * W)

    # ── Aggregate scores — dùng _repr_dict (mean của từng metric) ────────────
    print("\n  ĐIỂM TỔNG HỢP")
    print("  " + "─" * 68)

    agg_scores = {}
    for key in _TARGETS:
        try:
            score = float(result._repr_dict[key])
        except (KeyError, TypeError, ValueError):
            score = float("nan")
        agg_scores[key] = score
        target = _TARGETS[key]
        status = _status(score, target) if score == score else "N/A"
        bar = _bar(score if score == score else 0)
        label = _METRIC_LABELS[key]
        print(f"  {label:<42}  {score:.3f}  {bar}  {status}")
        print(f"  {'':42}  (mục tiêu ≥ {target:.2f})")

    # ── Per-question breakdown ────────────────────────────────────────────────
    print("\n  CHI TIẾT TỪNG CÂU HỎI")
    print("  " + "─" * 68)

    df = result.to_pandas()
    for i, row in df.iterrows():
        q = questions[i]
        a = answers[i]
        category = dataset[i].get("category", "")
        n_ctx = len(contexts[i])

        print(f"\n  [{i+1:02d}] [{category}] {q}")
        print(f"       Docs retrieved : {n_ctx}")
        print(f"       Answer preview : {a[:100].replace(chr(10), ' ')}{'...' if len(a) > 100 else ''}")

        for key in _TARGETS:
            try:
                val_f = float(row[key])
                display = f"{val_f:.3f}"
                indicator = "✓" if val_f >= _TARGETS[key] else "✗"
            except (KeyError, TypeError, ValueError):
                display = " n/a"
                indicator = "?"
            print(f"       {key:<22}: {display}  {indicator}")

    # ── Summary verdict ───────────────────────────────────────────────────────
    print("\n" + "═" * W)
    passed = sum(1 for k, v in agg_scores.items() if v == v and v >= _TARGETS[k])
    total = len(_TARGETS)
    print(f"  KẾT LUẬN: {passed}/{total} metrics đạt mục tiêu")

    if passed == total:
        print("  Pipeline chất lượng TỐT — sẵn sàng production.")
    elif passed >= total // 2:
        print("  Pipeline ở mức TRUNG BÌNH — cần cải thiện một số metrics.")
    else:
        print("  Pipeline CHƯA ĐẠT — cần review prompt, retriever hoặc testset.")

    print("═" * W + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Lưu vào MongoDB và xuất CSV
# ══════════════════════════════════════════════════════════════════════════════

async def persist_results(
    result,
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
    dataset: list[dict],
) -> Path:
    """Lưu từng mẫu đánh giá vào MongoDB và xuất file CSV."""
    print("[Bước 5/5] Lưu kết quả vào MongoDB và xuất CSV...")

    df = result.to_pandas()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    mongo_client = get_mongo_client()

    for i, row in df.iterrows():
        doc = {
            "run_id":            run_id,
            "question":          questions[i],
            "answer":            answers[i],
            "ground_truth":      ground_truths[i],
            "n_contexts":        len(contexts[i]),
            "category":          dataset[i].get("category", ""),
            "faithfulness":      _safe_float(row.get("faithfulness")),
            "answer_relevancy":  _safe_float(row.get("answer_relevancy")),
            "context_precision": _safe_float(row.get("context_precision")),
            "context_recall":    _safe_float(row.get("context_recall")),
        }
        await save_eval_result(doc)

    print(f"  ✓ {len(df)} mẫu đã lưu vào MongoDB (run_id: {run_id})")

    # CSV export
    output_dir = _BACKEND_ROOT / "eval_reports"
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / f"ragas_{run_id}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "run_id", "category", "question", "answer",
            "faithfulness", "answer_relevancy", "context_precision", "context_recall",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in df.iterrows():
            writer.writerow({
                "run_id":            run_id,
                "category":          dataset[i].get("category", ""),
                "question":          questions[i],
                "answer":            answers[i][:200],
                "faithfulness":      _safe_float(row.get("faithfulness")),       # pandas Series.get() OK
                "answer_relevancy":  _safe_float(row.get("answer_relevancy")),
                "context_precision": _safe_float(row.get("context_precision")),
                "context_recall":    _safe_float(row.get("context_recall")),
            })

    print(f"  ✓ CSV xuất: {csv_path}")
    return csv_path


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return round(f, 4) if f == f else None  # NaN → None
    except (TypeError, ValueError):
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def run_evaluation(quick: bool = False) -> dict:
    """
    Orchestrate toàn bộ quy trình đánh giá.
    quick=True: chỉ chạy 3 câu đầu để test nhanh.
    """
    dataset = TEST_DATASET[:3] if quick else TEST_DATASET

    if quick:
        print("\n  [QUICK MODE] Chỉ chạy 3 câu hỏi đầu để kiểm tra nhanh.\n")

    # Bước 1
    pipeline, embeddings = build_pipeline()

    # Bước 2
    questions, answers, contexts, ground_truths = await collect_pipeline_outputs(pipeline, dataset)

    # Bước 3
    result = compute_ragas_metrics(questions, answers, contexts, ground_truths, embeddings)

    # Bước 4
    print_report(result, questions, answers, contexts, ground_truths, dataset)

    # Bước 5
    csv_path = await persist_results(result, questions, answers, contexts, ground_truths, dataset)

    # _repr_dict chứa mean đã tính sẵn của từng metric
    agg = result._repr_dict
    return {
        "faithfulness":      _safe_float(agg.get("faithfulness")),
        "answer_relevancy":  _safe_float(agg.get("answer_relevancy")),
        "context_precision": _safe_float(agg.get("context_precision")),
        "context_recall":    _safe_float(agg.get("context_recall")),
        "csv_path":          str(csv_path),
        "n_samples":         len(dataset),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAGAS evaluation cho SSI RAG Chatbot")
    parser.add_argument("--quick", action="store_true", help="Chỉ chạy 3 câu đầu để test nhanh")
    args = parser.parse_args()

    asyncio.run(run_evaluation(quick=args.quick))
