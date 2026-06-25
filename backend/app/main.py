# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db.mysql import init_db
from .db.mongodb import get_mongo_client
from .api.routes import chat, sessions, ingest
from .core.config import settings
from .core.rag_pipeline import RAGPipeline
from .core.retriever import HybridRetriever
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Truyền api_key trực tiếp — không phụ thuộc os.environ
    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2",
        google_api_key=settings.GOOGLE_API_KEY,   # ← thêm dòng này
    )

    vectorstore = FAISS.load_local(
        settings.DB_FAISS_PATH,
        embeddings,
        allow_dangerous_deserialization=True
    )

    retriever = HybridRetriever(
        vectorstore=vectorstore,
        bm25_index_path=settings.BM25_INDEX_PATH,
        k=settings.RETRIEVER_K,
    )

    app.state.rag_pipeline = RAGPipeline(retriever, settings.RETRIEVER_SCORE_THRESHOLD)
    app.state.embeddings = embeddings
    app.state.vectorstore = vectorstore

    yield


app = FastAPI(title="SSI RAG Chatbot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")