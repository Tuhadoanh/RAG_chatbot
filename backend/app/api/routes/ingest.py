# backend/app/api/routes/ingest.py
from fastapi import APIRouter, BackgroundTasks, Request
from ...db.mongodb import get_mongo_client
from ...core.config import settings

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
async def trigger_ingest(background_tasks: BackgroundTasks, request: Request):
    """
    Kích hoạt ingestion pipeline chạy nền.
    Dùng khi bạn thêm PDF mới vào thư mục New_Sources/.
    """
    embeddings = request.app.state.embeddings
    mongo_client = get_mongo_client()

    async def run_ingest_task():
        from ...core.ingestion import run_ingestion
        result = await run_ingestion(
            new_sources_path=settings.NEW_SOURCES_PATH,
            faiss_db_path=settings.DB_FAISS_PATH,
            bm25_index_path=settings.BM25_INDEX_PATH,
            embeddings=embeddings,
            mongo_client=mongo_client,
        )
        print(f"[Ingest] Kết quả: {result}")

    background_tasks.add_task(run_ingest_task)
    return {"status": "ingestion started", "message": "Chạy nền, kiểm tra terminal để theo dõi"}


@router.get("/ingest/status")
async def ingest_status():
    """Kiểm tra số file đã được index trong MongoDB."""
    mongo_client = get_mongo_client()
    db = mongo_client[settings.MONGODB_DATABASE]
    count = await db.processed_files.count_documents({})
    files_cursor = db.processed_files.find({}, {"filename": 1, "chunk_count": 1, "processed_at": 1})
    files = await files_cursor.to_list(100)
    return {
        "total_indexed_files": count,
        "files": [
            {
                "filename": f["filename"],
                "chunks": f.get("chunk_count", 0),
                "processed_at": str(f.get("processed_at", "")),
            }
            for f in files
        ]
    }