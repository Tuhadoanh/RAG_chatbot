# SSI RAG Chatbot

Chatbot hỏi–đáp thông minh dựa trên **Retrieval-Augmented Generation (RAG)**, chuyên phân tích báo cáo tài chính và tra cứu thông tin doanh nghiệp **SSI** (Công ty Cổ phần Chứng khoán SSI).

---

## Tính năng

- **Hybrid Retrieval** — kết hợp FAISS (semantic) + BM25 (keyword) để tìm kiếm ngữ cảnh chính xác
- **Streaming SSE** — câu trả lời hiện dần theo từng token như ChatGPT
- **Lịch sử hội thoại** — sidebar quản lý nhiều phiên chat, đổi tên, xoá
- **Topic Guard** — tự động từ chối câu hỏi ngoài phạm vi SSI
- **Trích dẫn nguồn** — mỗi câu trả lời kèm trang PDF, section tham chiếu
- **Ingestion pipeline** — thêm PDF mới qua API, index chạy nền

---

## Kiến trúc

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React)                   │
│  Sidebar ←→ ChatWindow ←→ InputBar ←→ MessageBubble     │
└───────────────────────┬─────────────────────────────────┘
                        │ SSE / REST
┌───────────────────────▼─────────────────────────────────┐
│                   Backend (FastAPI)                     │
│                                                         │
│  /api/chat/stream                                       │
│       │                                                 │
│       ├─ Topic Guard (Gemini classifier)                │
│       ├─ Question Rewriter (Gemini)                     │
│       ├─ HybridRetriever                                │
│       │      ├─ FAISS  (semantic, weight 0.7)           │
│       │      └─ BM25   (keyword,  weight 0.3)           │
│       └─ Answer Generator (Gemini streaming)            │
│                                                         │
│  /api/sessions   — quản lý phiên chat (MySQL)           │
│  /api/ingest     — thêm tài liệu mới (MongoDB + FAISS)  │
└───────┬───────────────────────────┬─────────────────────┘
        │                           │
   ┌────▼────┐               ┌──────▼──────┐
   │  MySQL  │               │   MongoDB   │
   │ (chat   │               │  (file      │
   │history) │               │   index)    │
   └─────────┘               └─────────────┘
```

---

## Tech Stack

| Layer | Công nghệ |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| Backend | FastAPI, Python 3.11+ |
| LLM | Google Gemini 2.5 Flash |
| Embedding | Google `gemini-embedding-2` |
| Vector DB | FAISS (CPU) |
| Keyword Search | BM25 (`rank_bm25`) |
| SQL | MySQL 8 + SQLAlchemy (async) |
| Document Store | MongoDB 7 |
| Containerization | Docker Compose |

---

## Yêu cầu hệ thống

- Python **3.11+**
- Node.js **18+**
- Docker & Docker Compose
- Google API Key (Gemini)

---

## Cài đặt & Chạy

### 1. Clone repo

```bash
git clone https://github.com/Tuhadoanh/RAG_chatbot.git
cd RAG_chatbot
```

### 2. Khởi động database (Docker)

```bash
docker-compose up -d
```

Lệnh này khởi động MySQL (port 3306) và MongoDB (port 27017).

### 3. Cài đặt Backend

```bash
cd backend

# Tạo virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Cài dependencies
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Mở file `.env` và điền:

```env
GOOGLE_API_KEY=your_google_api_key_here   # bắt buộc
MYSQL_PASSWORD=strongpassword              # phải khớp docker-compose.yml
```

> Lấy Google API Key tại: https://aistudio.google.com/app/apikey

### 5. Build vector index từ tài liệu PDF

Trước khi chạy lần đầu, cần tạo FAISS index và BM25 index từ các file PDF trong `New_Sources/`.

**Cách 1 — qua API (sau khi backend đã chạy):**
```bash
curl -X POST http://localhost:8000/api/ingest
```

**Cách 2 — chạy trực tiếp (script):**
```bash
cd backend
python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.core.ingestion import run_ingestion
from app.core.config import settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embeddings = GoogleGenerativeAIEmbeddings(
    model='gemini-embedding-2',
    google_api_key=settings.GOOGLE_API_KEY
)
asyncio.run(run_ingestion(
    new_sources_path=settings.NEW_SOURCES_PATH,
    faiss_db_path=settings.DB_FAISS_PATH,
    bm25_index_path=settings.BM25_INDEX_PATH,
    embeddings=embeddings,
    mongo_client=None
))
"
```

> Quá trình này mất khoảng 2–5 phút tuỳ số lượng trang PDF.

### 6. Chạy Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend sẵn sàng tại `http://localhost:8000`  
Swagger UI: `http://localhost:8000/docs`

### 7. Cài đặt & Chạy Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở trình duyệt tại `http://localhost:5173`

---

## Thêm tài liệu mới

1. Copy file PDF vào thư mục `backend/New_Sources/`
2. Gọi API:
   ```bash
   curl -X POST http://localhost:8000/api/ingest
   ```
3. Kiểm tra tiến độ:
   ```bash
   curl http://localhost:8000/api/ingest/status
   ```

---

## Cấu trúc dự án

```
RAG_chatbot/
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── chat.py        # SSE streaming endpoint
│   │   │   ├── sessions.py    # CRUD phiên chat
│   │   │   └── ingest.py      # Trigger ingestion
│   │   ├── core/
│   │   │   ├── rag_pipeline.py   # Topic guard + RAG chain
│   │   │   ├── retriever.py      # Hybrid FAISS + BM25
│   │   │   ├── ingestion.py      # PDF → chunks → index
│   │   │   └── config.py
│   │   └── db/
│   │       ├── models.py      # SQLAlchemy models
│   │       ├── mysql.py
│   │       └── mongodb.py
│   ├── New_Sources/           # Đặt PDF tài liệu vào đây
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                   # (local only, không commit)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.tsx    # Lịch sử chat
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── InputBar.tsx
│   │   └── hooks/
│   │       └── useChat.ts     # SSE streaming hook
│   └── package.json
└── docker-compose.yml         # MySQL + MongoDB
```

---

## API Reference

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/api/chat/stream` | Gửi câu hỏi, nhận SSE token stream |
| `GET` | `/api/sessions` | Danh sách phiên chat |
| `POST` | `/api/sessions` | Tạo phiên mới |
| `GET` | `/api/sessions/{id}/history` | Lịch sử tin nhắn |
| `PATCH` | `/api/sessions/{id}` | Đổi tên phiên |
| `DELETE` | `/api/sessions/{id}` | Xoá phiên |
| `POST` | `/api/ingest` | Kích hoạt index tài liệu |
| `GET` | `/api/ingest/status` | Trạng thái index |

---

## Troubleshooting

**`503 UNAVAILABLE` từ Gemini API**  
→ Google API đang quá tải tạm thời. Thử lại sau vài giây.

**`faiss_db` không tìm thấy khi khởi động**  
→ Chưa chạy ingestion. Xem bước 5 ở trên.

**MySQL connection refused**  
→ Chạy `docker-compose up -d` và đợi khoảng 10 giây để MySQL khởi động.

**CORS error trên browser**  
→ Đảm bảo backend đang chạy tại `http://localhost:8000`.

---

## License

MIT
