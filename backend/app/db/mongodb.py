# backend/app/db/mongodb.py
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from ..core.config import settings  # ← đổi từ os.getenv

client: AsyncIOMotorClient = None


def get_mongo_client() -> AsyncIOMotorClient:
    global client
    if client is None:
        client = AsyncIOMotorClient(settings.MONGODB_URI)
    return client


async def save_eval_result(result: dict):
    db = get_mongo_client()[settings.MONGODB_DATABASE]
    result["evaluated_at"] = datetime.now(timezone.utc)
    await db.eval_results.insert_one(result)


async def get_eval_stats() -> dict:
    db = get_mongo_client()[settings.MONGODB_DATABASE]
    pipeline = [
        {"$group": {
            "_id": None,
            "avg_faithfulness": {"$avg": "$faithfulness"},
            "avg_answer_relevance": {"$avg": "$answer_relevance"},
            "avg_context_relevance": {"$avg": "$context_relevance"},
            "count": {"$sum": 1},
        }}
    ]
    result = await db.eval_results.aggregate(pipeline).to_list(1)
    return result[0] if result else {}