import os, re, pickle, logging
from glob import glob
from pathlib import Path
import pymupdf4llm
import fitz
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from rank_bm25 import BM25Okapi
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log
from langchain_google_genai._common import GoogleGenerativeAIError

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

RETRYABLE_ERROR_KEYWORDS = (
    "RESOURCE_EXHAUSTED", "429", "UNAVAILABLE", "503", "DEADLINE_EXCEEDED",
)

def is_retryable_google_error(exception: BaseException) -> bool:
    if not isinstance(exception, GoogleGenerativeAIError):
        return False
    message = str(exception)
    return any(keyword in message for keyword in RETRYABLE_ERROR_KEYWORDS)

MIN_CHARS_FOR_VALID_TEXT_LAYER = 20
TABLE_LINE_PATTERN = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
VIETNAMESE_CHAR_PATTERN = re.compile(r"[àáâãèéêìíòóôõùúýăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỷỹ]", re.IGNORECASE)
_ANNUAL_KW   = {"annual", "thuongnien", "yearly", "nam"}
_INTERIM_KW  = {"interim", "bannien", "halfyear", "6thang"}
YEAR_IN_FILENAME_PATTERN    = re.compile(r"(20\d{2})")
QUARTER_IN_FILENAME_PATTERN = re.compile(r"q(\d)(?!\d)", re.IGNORECASE)

def page_has_table(markdown_text: str) -> bool:
    return len(TABLE_LINE_PATTERN.findall(markdown_text)) >= 2

def extract_first_heading(markdown_text: str) -> str:
    match = HEADING_PATTERN.search(markdown_text)
    if not match:
        return ""
    heading = re.sub(r"\*+", "", match.group(1)).strip()
    return heading[:120]

def detect_language(text: str) -> str:
    sample = text[:500]
    if not sample:
        return "unknown"
    vie_ratio = len(VIETNAMESE_CHAR_PATTERN.findall(sample)) / len(sample)
    return "vie" if vie_ratio > 0.02 else "eng"

def extract_report_metadata_from_filename(filename: str) -> dict:
    base = os.path.splitext(filename)[0].lower()
    stem_flat = re.sub(r"[-_\s.]+", "", base)
    year_match = YEAR_IN_FILENAME_PATTERN.search(base)
    year = year_match.group(1) if year_match else None
    quarter_match = QUARTER_IN_FILENAME_PATTERN.search(base)
    quarter = f"Q{quarter_match.group(1)}" if quarter_match else None
    if any(kw in stem_flat for kw in _ANNUAL_KW):
        report_type = "annual"
    elif quarter:
        report_type = "quarterly"
    elif any(kw in stem_flat for kw in _INTERIM_KW):
        report_type = "interim"
    else:
        report_type = "unknown"
    return {"year": year, "quarter": quarter, "report_type": report_type}

def ocr_fallback_for_page(pdf_path: str, page_number: int) -> str:
    if not OCR_AVAILABLE:
        return ""
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="vie+eng")
        doc.close()
        return text
    except Exception as e:
        logger.warning(f"  [OCR] Lỗi khi OCR trang {page_number} của {pdf_path}: {e}")
        return ""

def load_pdfs_as_documents_from_paths(pdf_paths: list[str]) -> list[Document]:
    """Hàm này đã được sửa để nhận list các đường dẫn file (pdf_paths) thay vì folder_path"""
    documents: list[Document] = []
    for pdf_path in pdf_paths:
        filename = os.path.basename(pdf_path)
        logger.info(f"Đang đọc: {pdf_path}")
        try:
            pages = pymupdf4llm.to_markdown(pdf_path, page_chunks=True)
        except Exception as e:
            logger.error(f"Lỗi khi đọc {pdf_path}: {e} -> bỏ qua file này.")
            continue

        file_meta = extract_report_metadata_from_filename(filename)
        total_pages = len(pages)

        for page in pages:
            page_number = page["metadata"]["page_number"]
            text = page["text"]

            if len(text.strip()) < MIN_CHARS_FOR_VALID_TEXT_LAYER:
                ocr_text = ocr_fallback_for_page(pdf_path, page_number)
                if ocr_text.strip():
                    text = ocr_text
                else:
                    continue 

            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source":       filename,
                        "page":         page_number,
                        "total_pages":  total_pages,
                        "report_type":  file_meta["report_type"],
                        "year":         file_meta["year"],
                        "quarter":      file_meta["quarter"],
                        "section":      extract_first_heading(text),
                        "has_table":    page_has_table(text),
                        "language":     detect_language(text),
                    },
                )
            )
    return documents

def split_documents(docs: list[Document]) -> list[Document]:
    """Hàm tách nội dung trang chứa bảng và trang thường"""
    MARKDOWN_SEPARATORS = ["\n#{1,6} ", "```\n", "\n\\*\\*\\*+\n", "\n---+\n", "\n___+\n", "\n\n", "\n", " ", ""]
    MAX_TABLE_PAGE_CHARS = 6000

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200, chunk_overlap=200, add_start_index=True, strip_whitespace=True, separators=MARKDOWN_SEPARATORS
    )
    table_text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_TABLE_PAGE_CHARS, chunk_overlap=0, add_start_index=True,
        strip_whitespace=True, separators=["\n\n", "\n"],
    )

    table_docs = [d for d in docs if d.metadata.get("has_table")]
    text_docs = [d for d in docs if not d.metadata.get("has_table")]

    splits = text_splitter.split_documents(text_docs)

    for doc in table_docs:
        if len(doc.page_content) <= MAX_TABLE_PAGE_CHARS:
            splits.append(doc) 
        else:
            splits.extend(table_text_splitter.split_documents([doc]))
            
    return splits

def wait_for_google_quota(retry_state):
    exception = retry_state.outcome.exception()
    if exception is not None:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exception))
        if match:
            suggested_wait = float(match.group(1)) + 1 
            return min(suggested_wait, 120.0)
    return wait_exponential(multiplier=2.0, max=120.0)(retry_state)

@retry(
    retry=retry_if_exception(is_retryable_google_error),
    wait=wait_for_google_quota,
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def add_batch_with_backoff(vectorstore, batch):
    vectorstore.add_documents(batch)

async def add_documents_with_retry(vectorstore, splits):
    """Hàm chèn tài liệu theo lô (batch) và xử lý lỗi Rate Limit để hỗ trợ API gọi Async"""
    BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "1400"))
    for i in range(0, len(splits), BATCH_SIZE):
        batch = splits[i : i + BATCH_SIZE]
        try:
            add_batch_with_backoff(vectorstore, batch)
            logger.info(f" -> Đã chèn xong chunk từ {i} -> {i + len(batch)}")
        except Exception as e:
            logger.error(f" -> Lỗi ở chunk {i} -> {i + len(batch)}: {e}")

# Kết thúc đoạn lấy từ add_data1.py
# ── THÊM MỚI: BM25 Index Builder ───────────────────────────────────────────

def build_bm25_index(documents: list[Document], save_path: str) -> BM25Okapi:
    """
    Xây dựng BM25 index từ danh sách Document.
    BM25 tokenize đơn giản theo whitespace — đủ tốt cho tiếng Việt với từ đã tách.
    Lưu pickle để load nhanh sau này mà không cần rebuild.
    """
    corpus = [doc.page_content.lower().split() for doc in documents]
    bm25 = BM25Okapi(corpus)
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        # Lưu cả bm25 object VÀ documents để map index -> Document
        pickle.dump({"bm25": bm25, "documents": documents}, f)
    logger.info(f"BM25 index đã lưu: {len(documents)} documents -> {save_path}")
    return bm25


async def mark_file_as_processed(mongo_client, filename: str, chunk_count: int):
    """
    Ghi nhận file đã xử lý vào MongoDB để tránh index lại lần sau.
    Collection: processed_files
    """
    db = mongo_client["rag_chatbot"]
    await db.processed_files.update_one(
        {"filename": filename},
        {"$set": {
            "filename": filename,
            "chunk_count": chunk_count,
            "processed_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


async def get_already_processed_files(mongo_client) -> set[str]:
    """Trả về set tên file đã được index để skip."""
    db = mongo_client["rag_chatbot"]
    cursor = db.processed_files.find({}, {"filename": 1})
    return {doc["filename"] async for doc in cursor}


async def run_ingestion(
    new_sources_path: str,
    faiss_db_path: str,
    bm25_index_path: str,
    embeddings: GoogleGenerativeAIEmbeddings,
    mongo_client,
) -> dict:
    """
    Pipeline ingestion hoàn chỉnh:
    1. Phát hiện file mới (chưa xử lý)
    2. Load + split PDF
    3. Upsert FAISS
    4. Rebuild BM25 index
    5. Ghi nhận vào MongoDB
    """
    already_processed = await get_already_processed_files(mongo_client)

    # Lọc chỉ file CHƯA xử lý
    all_pdfs = sorted(glob(os.path.join(new_sources_path, "**", "*.pdf"), recursive=True))
    new_pdfs = [p for p in all_pdfs if os.path.basename(p) not in already_processed]

    if not new_pdfs:
        return {"status": "no_new_files", "processed": 0}

    docs = load_pdfs_as_documents_from_paths(new_pdfs)  # Adapt từ add_data_1.py

    # Split documents (giữ logic bảng từ add_data_1.py)
    splits = split_documents(docs)

    # Upsert vào FAISS
    if os.path.exists(faiss_db_path):
        vectorstore = FAISS.load_local(faiss_db_path, embeddings, allow_dangerous_deserialization=True)
        await add_documents_with_retry(vectorstore, splits)
    else:
        vectorstore = await FAISS.afrom_documents(splits, embeddings)

    vectorstore.save_local(faiss_db_path)

    # Rebuild BM25 (cần TOÀN BỘ corpus, không thể incremental)
    # Load tất cả documents từ FAISS docstore
    all_docs = list(vectorstore.docstore._dict.values())
    build_bm25_index(all_docs, bm25_index_path)

    # Ghi nhận vào MongoDB
    for pdf_path in new_pdfs:
        filename = os.path.basename(pdf_path)
        chunk_count = sum(1 for d in splits if d.metadata.get("source") == filename)
        await mark_file_as_processed(mongo_client, filename, chunk_count)

    return {"status": "success", "processed": len(new_pdfs), "chunks": len(splits)}

# ==============================================================================
# ENTRY POINT - Điểm kích hoạt khi chạy script trực tiếp từ Terminal
# ==============================================================================
if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from ..db.mongodb import get_mongo_client

    # Load file .env để lấy API Key và các đường dẫn
    load_dotenv()

    async def main():
        print("🚀 Bắt đầu quá trình nạp dữ liệu (Ingestion Pipeline)...")
        
        # 1. Khởi tạo Embeddings và MongoDB Client
        embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")
        mongo_client = get_mongo_client()

        # 2. Lấy đường dẫn từ cấu hình hoặc dùng mặc định
        new_sources = os.getenv("NEW_SOURCES_PATH", "./New_Sources")
        faiss_path = os.getenv("DB_FAISS_PATH", "faiss_db")
        bm25_path = os.getenv("BM25_INDEX_PATH", "bm25_index/bm25.pkl")

        print(f"📂 Đang quét thư mục: {os.path.abspath(new_sources)}")

        # 3. Chạy hàm xử lý chính
        try:
            result = await run_ingestion(
                new_sources_path=new_sources,
                faiss_db_path=faiss_path,
                bm25_index_path=bm25_path,
                embeddings=embeddings,
                mongo_client=mongo_client
            )
            print(f"✅ KẾT QUẢ: {result}")
        except Exception as e:
            print(f"❌ CÓ LỖI XẢY RA: {e}")

    # Chạy vòng lặp bất đồng bộ
    asyncio.run(main())