"""
RAG (Retrieval-Augmented Generation) service for the language learning platform.

Responsibilities:
- Embed OCR-extracted text and related context
- Persist embeddings in a FAISS vector database
- Retrieve relevant context for a user question
- Call an LLM via LangChain to generate educational explanations

This module is intentionally self-contained and does not change existing behaviour.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import User

from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFacePipeline
from langchain_community.vectorstores import FAISS
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

logger = logging.getLogger(__name__)


_rag_service: Optional["RAGService"] = None


def get_rag_service() -> "RAGService":
    """
    Get or create a singleton instance of the RAGService.

    This keeps heavy models (embeddings + LLM + FAISS index) in memory.
    """
    global _rag_service
    if _rag_service is None:
        try:
            _rag_service = RAGService()
            logger.info("✅ RAGService initialized successfully")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Failed to initialize RAGService: %s", exc)
            raise
    return _rag_service


class RAGService:
    """
    Core GenAI / RAG orchestration service.

    - Uses HuggingFace sentence-transformer embeddings via LangChain
    - Stores embeddings in a FAISS vector store on disk
    - Uses a small local LLM via HuggingFacePipeline wrapped by LangChain
    """

    def __init__(self) -> None:
        # Configure paths
        base_dir = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[1]))
        media_root = Path(getattr(settings, "MEDIA_ROOT", base_dir / "media"))
        self.index_dir = media_root / "rag_index"
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.index_dir / "faiss_index"
        self.metadata_path = self.index_dir / "metadata.json"

        # Models configuration (env overridable)
        embedding_model_name = os.getenv(
            "RAG_EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        llm_model_name = os.getenv(
            "RAG_LLM_MODEL",
            "gpt2",  # Small, local model; replace in production
        )

        logger.info("🔧 Initializing RAGService (embeddings=%s, llm=%s)", embedding_model_name, llm_model_name)

        # Embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model_name)

        # Vector store (lazy-loaded)
        self.vector_store: Optional[FAISS] = None
        self._load_vector_store_if_available()

        # LLM via LangChain
        self.llm = self._load_llm(llm_model_name)

        # Prompt for language tutor style explanations
        self.prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=(
                "You are a friendly, expert language tutor.\n\n"
                "Context:\n"
                "{context}\n\n"
                "Student question:\n"
                "{question}\n\n"
                "Instructions:\n"
                "- Answer using the context above; if the answer is not in the context, say you are not sure.\n"
                "- Explain like a tutor: simple, clear, with step-by-step reasoning.\n"
                "- Highlight important vocabulary and grammar points.\n"
                "- Provide 1–3 short example sentences where relevant.\n"
                "- Keep the tone encouraging and educational.\n\n"
                "Tutor explanation:"
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_llm(self, model_name: str) -> HuggingFacePipeline:
        """
        Load a small causal LM from Hugging Face and wrap it as a LangChain LLM.

        NOTE: This uses local models by default. For production, configure
        a larger model or a hosted LLM and adjust this method accordingly.
        """
        logger.info("📥 Loading LLM model for RAG: %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)

        text_gen = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )

        return HuggingFacePipeline(pipeline=text_gen)

    def _load_vector_store_if_available(self) -> None:
        """Load FAISS index + metadata from disk if present."""
        try:
            if self.index_path.exists():
                logger.info("📂 Loading existing FAISS index from %s", self.index_path)
                # allow_dangerous_deserialization=True is required when loading from local disk
                self.vector_store = FAISS.load_local(
                    folder_path=str(self.index_path),
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True,
                )
            else:
                logger.info("ℹ️ No existing FAISS index found; a new one will be created lazily")
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Failed to load FAISS index: %s", exc)
            self.vector_store = None

    def _save_vector_store(self) -> None:
        """Persist FAISS index and metadata to disk."""
        if self.vector_store is None:
            return

        try:
            logger.info("💾 Saving FAISS index to %s", self.index_path)
            self.index_path.mkdir(parents=True, exist_ok=True)
            self.vector_store.save_local(str(self.index_path))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Failed to save FAISS index: %s", exc)

    # ------------------------------------------------------------------
    # Public API – Indexing
    # ------------------------------------------------------------------

    def index_learning_session(
        self,
        session_id: int,
        user: User,
        extracted_text: str,
        word_definitions: Optional[List[Dict[str, Any]]] = None,
        is_single_word: bool = False,
    ) -> None:
        """
        Store OCR / text-input session content and related context into the vector DB.

        This is designed to be called after OCR/text processing is complete.
        """
        from ocr_tts_app.models import LearningHistory  # Local import to avoid circular deps

        if not extracted_text:
            logger.info("ℹ️ Skipping RAG indexing: empty extracted_text for session %s", session_id)
            return

        try:
            session = LearningHistory.objects.filter(id=session_id, user=user).first()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Failed to load LearningHistory for RAG indexing: %s", exc)
            return

        if not session:
            logger.warning("⚠️ LearningHistory not found for RAG indexing (id=%s)", session_id)
            return

        documents: List[Document] = []

        # 1) Core OCR / text content
        base_context = f"OCR/Text content from session {session.session_id}:\n{extracted_text}"
        documents.append(
            Document(
                page_content=base_context,
                metadata={
                    "type": "ocr_text",
                    "user_id": user.id,
                    "session_db_id": session.id,
                    "session_id": str(session.session_id),
                },
            )
        )

        # 2) Dictionary definitions, if applicable
        if is_single_word and word_definitions:
            dict_lines = []
            for idx, definition in enumerate(word_definitions, start=1):
                part = definition.get("part_of_speech") or ""
                meaning = definition.get("definition") or ""
                example = definition.get("example") or ""
                line = f"{idx}. ({part}) {meaning}"
                if example:
                    line += f" Example: {example}"
                dict_lines.append(line)

            dict_text = "\n".join(dict_lines)
            dict_context = (
                f"Dictionary information for the word '{extracted_text}' "
                f"from session {session.session_id}:\n{dict_text}"
            )
            documents.append(
                Document(
                    page_content=dict_context,
                    metadata={
                        "type": "dictionary",
                        "user_id": user.id,
                        "session_db_id": session.id,
                        "session_id": str(session.session_id),
                    },
                )
            )

        # 3) Lightweight summary of previous sessions for this user
        try:
            recent_sessions = (
                LearningHistory.objects.filter(user=user)
                .exclude(id=session.id)
                .order_by("-created_at")[:5]
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Failed to load previous sessions for RAG context: %s", exc)
            recent_sessions = []

        for prev in recent_sessions:
            if not prev.extracted_text:
                continue
            summary = (
                f"Previous learning session {prev.session_id} on "
                f"{prev.created_at.strftime('%Y-%m-%d %H:%M')} "
                f"({prev.learning_type}, difficulty={prev.difficulty_level}):\n"
                f"{prev.extracted_text[:500]}"
            )
            documents.append(
                Document(
                    page_content=summary,
                    metadata={
                        "type": "history",
                        "user_id": user.id,
                        "session_db_id": prev.id,
                        "session_id": str(prev.session_id),
                    },
                )
            )

        if not documents:
            logger.info("ℹ️ No documents generated for RAG indexing for session %s", session_id)
            return

        # Initialize or extend FAISS index
        try:
            if self.vector_store is None:
                logger.info("🧱 Creating new FAISS vector store for RAG")
                self.vector_store = FAISS.from_documents(documents, self.embeddings)
            else:
                logger.info("➕ Adding %d documents to existing FAISS index", len(documents))
                self.vector_store.add_documents(documents)

            self._save_vector_store()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("❌ Failed to update FAISS index: %s", exc)

    # ------------------------------------------------------------------
    # Public API – Question answering / RAG
    # ------------------------------------------------------------------

    def answer_question(
        self,
        user: User,
        question: str,
        session_id: Optional[str] = None,
        top_k: int = 4,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Perform RAG using the user's indexed learning content.

        Returns:
            (answer, sources) where `sources` is a list of lightweight
            metadata dictionaries describing retrieved documents.
        """
        if not question.strip():
            raise ValueError("Question must not be empty.")

        if self.vector_store is None:
            raise RuntimeError("RAG vector store is empty. No learning sessions have been indexed yet.")

        # Build retriever – we cannot natively filter by metadata in FAISS,
        # so we over-retrieve then filter in Python.
        retriever = self.vector_store.as_retriever(search_kwargs={"k": max(top_k * 2, 8)})

        # Retrieve candidate documents (handle both classic and LC v1+ retriever APIs)
        logger.info("🔎 Retrieving context for RAG question (user=%s, session_id=%s)", user.id, session_id)
        if hasattr(retriever, "get_relevant_documents"):
            candidate_docs: List[Document] = retriever.get_relevant_documents(question)
        else:
            # Newer LangChain retrievers are Runnables – use invoke()
            candidate_docs = retriever.invoke(question)

        filtered_docs: List[Document] = []
        session_id_str = str(session_id) if session_id is not None else None
        for doc in candidate_docs:
            meta = doc.metadata or {}

            # Restrict to current user
            if meta.get("user_id") != user.id:
                continue

            # Optionally restrict to a specific session
            if session_id_str and meta.get("session_id") != session_id_str:
                continue

            filtered_docs.append(doc)
            if len(filtered_docs) >= top_k:
                break

        if not filtered_docs:
            # Fallback: at least use the global retrieval for this user
            filtered_docs = [
                d for d in candidate_docs if (d.metadata or {}).get("user_id") == user.id
            ][:top_k]

        if not filtered_docs:
            raise RuntimeError("No relevant context found for this user in the RAG index.")

        # Concatenate context
        context_chunks = [doc.page_content for doc in filtered_docs]
        context_text = "\n\n---\n\n".join(context_chunks)

        # Format prompt and call LLM directly via LangChain
        logger.info("🧠 Running RAG LLM for user %s", user.id)
        prompt_text = self.prompt.format(context=context_text, question=question)

        result = self.llm.invoke(prompt_text)

        # LangChain LLMs may return raw strings or Message objects
        if isinstance(result, str):
            answer_text = result
        elif hasattr(result, "content"):
            answer_text = str(result.content)
        else:
            answer_text = str(result)

        # Prepare lightweight source info
        sources: List[Dict[str, Any]] = []
        for doc in filtered_docs:
            meta = doc.metadata or {}
            sources.append(
                {
                    "type": meta.get("type"),
                    "session_id": meta.get("session_id"),
                    "session_db_id": meta.get("session_db_id"),
                    "preview": doc.page_content[:200],
                }
            )

        return answer_text, sources



