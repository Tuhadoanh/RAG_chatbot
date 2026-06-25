# backend/app/core/rag_pipeline.py
import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage

from .retriever import HybridRetriever

logger = logging.getLogger(__name__)

# ── Prompt (giữ logic từ chatbot_1.py, thêm instruction về hybrid search) ──

OFF_TOPIC_REPLY = (
    "Câu hỏi của bạn không liên quan tới doanh nghiệp SSI, "
    "bạn vui lòng hỏi về các vấn đề trong phạm vi!"
)

TOPIC_GUARD_TEMPLATE = """Bạn là bộ phân loại câu hỏi cho chatbot RAG chuyên về báo cáo tài chính \
và thông tin doanh nghiệp SSI (Công ty Cổ phần Chứng khoán SSI).

Phạm vi được chấp nhận:
- Thông tin, hoạt động kinh doanh của SSI
- Báo cáo tài chính SSI (doanh thu, lợi nhuận, tài sản, nợ, vốn chủ sở hữu…)
- Kết quả kinh doanh theo quý/năm của SSI
- Thị trường chứng khoán, sản phẩm/dịch vụ liên quan đến SSI
- Các khái niệm tài chính/kế toán giúp hiểu báo cáo của SSI

Lưu ý: Nếu đây là câu hỏi tiếp nối trong cuộc hội thoại đang nói về SSI, hãy coi là RELEVANT.

Lịch sử hội thoại gần đây:
{history}

Câu hỏi cần phân loại: {question}

Trả lời CHỈ bằng một trong hai từ: RELEVANT hoặc OFF_TOPIC"""

SYSTEM_TEMPLATE = """You are an expert data analyst and business strategy consultant.
Using ONLY the provided information below, answer the user's questions concerning SSI.

RULES:
1) Use ONLY the provided context to answer.
2) If the answer is not clearly contained in the context, say: "I don't know based on the provided documents."
3) Do NOT use outside knowledge, guessing, or web information.
4) For every factual claim, cite its source. Format: (source, p.page, section).

Context:
{context}"""

REWRITE_TEMPLATE = """Given a chat history and the latest user question which might reference
context in the chat history, formulate a standalone question which can be understood without
the chat history. Do NOT answer the question, just reformulate it if needed, otherwise return as is."""


def format_docs(docs: list) -> str:
    """Giữ nguyên từ chatbot_1.py — thêm metadata header trước mỗi chunk."""
    if not docs:
        return "No relevant context found in the provided documents."
    parts = []
    for doc in docs:
        m = doc.metadata
        header_parts = [f"Source: {m.get('source', '?')}"]
        header_parts.append(f"Page: {m.get('page', '?')}/{m.get('total_pages', '?')}")
        if m.get("section"):
            header_parts.append(f"Section: {m['section']}")
        if m.get("year"):
            header_parts.append(f"Year: {m['year']}")
        if m.get("quarter"):
            header_parts.append(f"Quarter: {m['quarter']}")
        header = "[" + " | ".join(header_parts) + "]"
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


class RAGPipeline:
    def __init__(self, retriever: HybridRetriever, score_threshold: float = 0.5):
        self.retriever = retriever
        self.score_threshold = score_threshold

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_TEMPLATE),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ])

        self.rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", REWRITE_TEMPLATE),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ])

        self.question_rewriter = self.rewrite_prompt | self.llm | StrOutputParser()

    async def _is_on_topic(self, question: str, chat_history: list) -> bool:
        """Dùng LLM phân loại câu hỏi có trong phạm vi SSI hay không.
        Fail-open: nếu API lỗi thì cho câu hỏi đi qua pipeline bình thường."""
        try:
            recent = chat_history[-4:]
            history_lines = []
            for msg in recent:
                role = "Người dùng" if msg["role"] == "human" else "Trợ lý"
                history_lines.append(f"{role}: {msg['content'][:300]}")
            history_text = "\n".join(history_lines) if history_lines else "Không có"

            prompt_text = TOPIC_GUARD_TEMPLATE.format(
                history=history_text,
                question=question,
            )
            response = await self.llm.ainvoke(prompt_text)
            return "OFF_TOPIC" not in response.content.strip().upper()
        except Exception as exc:
            logger.warning("Topic guard failed (%s), defaulting to on-topic.", exc)
            return True

    def _get_standalone_question(self, input_dict: dict) -> str:
        """Rewrite câu hỏi nếu có lịch sử, tránh tốn LLM call nếu không cần."""
        if not input_dict.get("chat_history"):
            return input_dict["question"]
        return self.question_rewriter.invoke(input_dict)

    def _retrieve(self, standalone_question: str) -> list:
        """Gọi HybridRetriever."""
        return self.retriever.retrieve(standalone_question, self.score_threshold)

    async def astream(self, question: str, chat_history: list):
        """
        Async generator stream từng token để SSE streaming về frontend.
        chat_history: list of {"role": "human"/"ai", "content": str}
        """
        # Convert sang LangChain message objects
        lc_history = []
        for msg in chat_history:
            if msg["role"] == "human":
                lc_history.append(HumanMessage(content=msg["content"]))
            else:
                lc_history.append(AIMessage(content=msg["content"]))

        # ── Topic guard ──────────────────────────────────────────────────────
        on_topic = await self._is_on_topic(question, chat_history)
        if not on_topic:
            yield OFF_TOPIC_REPLY
            yield {"__metadata__": {"retrieved_docs": [], "standalone_question": question}}
            return
        # ─────────────────────────────────────────────────────────────────────

        # Rewrite question
        standalone_q = self._get_standalone_question({
            "question": question,
            "chat_history": lc_history,
        })

        # Retrieve
        docs = self._retrieve(standalone_q)
        context = format_docs(docs)

        # Build prompt và stream
        messages = self.prompt.format_messages(
            context=context,
            chat_history=lc_history,
            question=question,
        )

        full_response = ""
        async for chunk in self.llm.astream(messages):
            token = chunk.content
            if token:
                full_response += token
                yield token

        # Trả về metadata cho caller
        yield {"__metadata__": {
            "retrieved_docs": [
                {
                    "source": d.metadata.get("source"),
                    "page": d.metadata.get("page"),
                    "section": d.metadata.get("section"),
                    "content_preview": d.page_content[:200],
                }
                for d in docs
            ],
            "standalone_question": standalone_q,
        }}