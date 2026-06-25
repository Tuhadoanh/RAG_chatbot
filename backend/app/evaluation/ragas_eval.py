# backend/app/evaluation/ragas_eval.py
"""
Đánh giá RAG pipeline sử dụng RAGAS framework.
Chạy: python -m app.evaluation.ragas_eval

Metrics:
- Faithfulness: LLM judge xem câu trả lời có contradicts context không
- Answer Relevance: embedding similarity giữa question và answer
- Context Relevance: tỉ lệ context thực sự được dùng để trả lời
"""
import asyncio
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Import pipeline
from ..core.rag_pipeline import RAGPipeline
from ..core.retriever import HybridRetriever
from ..db.mongodb import save_eval_result
from .create_testset import TEST_DATASET


async def run_evaluation():
    # Khởi tạo pipeline (tương tự như trong main.py)
    # ... (load FAISS, BM25, tạo pipeline)

    questions = []
    answers = []
    contexts = []
    ground_truths = []

    print("Đang chạy RAG pipeline trên test set...")
    for item in TEST_DATASET:
        q = item["question"]

        # Chạy RAG (không stream, lấy full response)
        result = await pipeline.ainvoke(q, chat_history=[])
        answer = result["answer"]
        retrieved_docs = result["retrieved_docs"]

        questions.append(q)
        answers.append(answer)
        contexts.append([d.page_content for d in retrieved_docs])
        ground_truths.append(item["ground_truth"])

    # Tạo RAGAS dataset
    ragas_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    # Cấu hình RAGAS dùng Gemini
    gemini_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    )
    gemini_embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
    )

    print("Đang đánh giá với RAGAS...")
    results = evaluate(
        dataset=ragas_dataset,
        metrics=[
            faithfulness,       # 0.0–1.0: càng cao càng ít hallucinate
            answer_relevancy,   # 0.0–1.0: càng cao câu trả lời càng đúng trọng tâm
            context_precision,  # 0.0–1.0: càng cao context retrieved càng liên quan
        ],
        llm=gemini_llm,
        embeddings=gemini_embeddings,
    )

    # In kết quả
    print("\n" + "="*60)
    print("KẾT QUẢ ĐÁNH GIÁ RAG PIPELINE")
    print("="*60)
    print(f"Faithfulness:       {results['faithfulness']:.3f}  (mục tiêu > 0.80)")
    print(f"Answer Relevancy:   {results['answer_relevancy']:.3f}  (mục tiêu > 0.75)")
    print(f"Context Precision:  {results['context_precision']:.3f}  (mục tiêu > 0.70)")
    print("="*60)

    # Lưu vào MongoDB để tracking theo thời gian
    for i, item in enumerate(TEST_DATASET):
        await save_eval_result({
            "question": item["question"],
            "answer": answers[i],
            "ground_truth": item["ground_truth"],
            "contexts": contexts[i],
            "faithfulness": float(results["faithfulness"]),
            "answer_relevance": float(results["answer_relevancy"]),
            "context_relevance": float(results["context_precision"]),
        })

    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())