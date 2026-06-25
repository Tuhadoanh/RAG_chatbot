# backend/app/api/routes/eval.py
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from ...db.mongodb import get_mongo_client, get_eval_stats

router = APIRouter(tags=["evaluation"])

_eval_status: dict = {"running": False, "last_result": None, "error": None}


@router.post("/eval/run")
async def trigger_evaluation(background_tasks: BackgroundTasks, quick: bool = False):
    """
    Kích hoạt RAGAS evaluation chạy nền.
    quick=true  → chỉ 3 câu đầu (kiểm tra nhanh ~2 phút)
    quick=false → toàn bộ 15 câu (~10-15 phút)
    """
    if _eval_status["running"]:
        raise HTTPException(status_code=409, detail="Evaluation đang chạy, vui lòng đợi.")

    async def run_task():
        _eval_status["running"] = True
        _eval_status["error"] = None
        try:
            from ...evaluation.ragas_eval import run_evaluation
            result = await run_evaluation(quick=quick)
            _eval_status["last_result"] = result
        except Exception as exc:
            _eval_status["error"] = str(exc)
        finally:
            _eval_status["running"] = False

    background_tasks.add_task(run_task)
    return {
        "status": "started",
        "quick": quick,
        "message": f"Đang đánh giá {'3 câu (quick)' if quick else '15 câu (full)'}. "
                   "Kiểm tra GET /api/eval/status để theo dõi.",
    }


@router.get("/eval/status")
async def evaluation_status():
    """Trả về trạng thái lần đánh giá gần nhất."""
    return {
        "running":     _eval_status["running"],
        "last_result": _eval_status["last_result"],
        "error":       _eval_status["error"],
    }


@router.get("/eval/history")
async def evaluation_history(limit: int = 10):
    """Lấy lịch sử các lần đánh giá từ MongoDB (tổng hợp theo run_id)."""
    client = get_mongo_client()
    from ...core.config import settings
    db = client[settings.MONGODB_DATABASE]

    pipeline = [
        {"$sort": {"evaluated_at": -1}},
        {
            "$group": {
                "_id": "$run_id",
                "evaluated_at":      {"$first": "$evaluated_at"},
                "n_samples":         {"$sum": 1},
                "avg_faithfulness":  {"$avg": "$faithfulness"},
                "avg_answer_rel":    {"$avg": "$answer_relevancy"},
                "avg_ctx_precision": {"$avg": "$context_precision"},
                "avg_ctx_recall":    {"$avg": "$context_recall"},
            }
        },
        {"$sort": {"evaluated_at": -1}},
        {"$limit": limit},
    ]
    runs = await db.eval_results.aggregate(pipeline).to_list(limit)

    return {
        "runs": [
            {
                "run_id":          r["_id"],
                "evaluated_at":    str(r.get("evaluated_at", "")),
                "n_samples":       r["n_samples"],
                "faithfulness":    round(r["avg_faithfulness"] or 0, 3),
                "answer_relevancy": round(r["avg_answer_rel"] or 0, 3),
                "context_precision": round(r["avg_ctx_precision"] or 0, 3),
                "context_recall":  round(r["avg_ctx_recall"] or 0, 3),
            }
            for r in runs
        ]
    }


@router.get("/eval/stats")
async def evaluation_aggregate_stats():
    """Điểm trung bình tất cả lần đánh giá đã lưu."""
    stats = await get_eval_stats()
    if not stats:
        return {"message": "Chưa có dữ liệu đánh giá. Chạy POST /api/eval/run trước."}
    stats.pop("_id", None)
    return stats
