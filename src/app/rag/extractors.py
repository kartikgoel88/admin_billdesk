"""RAG-based policy extractors: vector search over policy text for decision engine context."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.extractors._paths import project_path
from app.extractors.policy_extractor import PolicyExtractor as BasePolicyExtractor


class RAGPolicyExtractor:
    """
    RAG-based policy extraction using vector embeddings.
    Provides semantic search over policy documents.
    """

    def __init__(self, policy_text: str, config: Any):
        self.policy_text = policy_text
        self.config = config
        self.vector_store = None
        self.embeddings = None

    def _init_rag(self):
        """Initialize RAG components lazily"""
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain.text_splitter import RecursiveCharacterTextSplitter

            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.rag_chunk_size,
                chunk_overlap=self.config.rag_chunk_overlap
            )
            chunks = text_splitter.split_text(self.policy_text)

            # Create embeddings and vector store
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.config.rag_embedding_model
            )
            self.vector_store = FAISS.from_texts(chunks, self.embeddings)

            print(f"✅ RAG initialized with {len(chunks)} policy chunks")
            return True

        except ImportError as e:
            print(f"⚠️ RAG dependencies not installed: {e}")
            print("   Install with: pip install faiss-cpu sentence-transformers langchain-community")
            return False
        except Exception as e:
            print(f"⚠️ RAG initialization failed: {e}")
            return False

    def query_policy(self, query: str) -> str:
        """Query policy using RAG retrieval"""
        if self.vector_store is None:
            if not self._init_rag():
                return ""

        docs = self.vector_store.similarity_search(query, k=self.config.rag_top_k)
        return "\n\n".join([doc.page_content for doc in docs])

    def get_relevant_policy_for_category(self, category: str) -> str:
        """Get policy sections relevant to a specific expense category"""
        queries = {
            "commute": "cab taxi commute transportation travel allowance limit policy",
            "cab": "cab taxi commute transportation travel allowance limit policy",
            "meal": "meal food allowance daily limit lunch dinner policy",
            "fuel": "fuel petrol diesel reimbursement vehicle policy"
        }
        query = queries.get(category, category + " policy allowance limit")
        return self.query_policy(query)


class PolicyExtractorWithRAG:
    """
    Wrapper around BasePolicyExtractor that adds RAG capabilities.
    """

    def __init__(self, config: Any):
        self.config = config
        self.rag_extractor = None
        self.policy = None

        if self.config.enable_rag:
            print("🔍 RAG mode enabled for policy extraction")

    def extract(self, policy_path: str, system_prompt_path: str) -> Optional[Dict]:
        """Extract policy from PDF using existing PolicyExtractor (policy_path is under app resources_dir)."""
        print(f"\n📋 Extracting policy from: {policy_path}")
        root = project_path()
        root_folder = root + os.sep
        input_path = policy_path if os.path.isabs(policy_path) else project_path(policy_path)
        extractor = BasePolicyExtractor(
            root_folder=root_folder,
            input_pdf_path=input_path,
            system_prompt_path=project_path(system_prompt_path),
        )

        self.policy = extractor.run(save_to_file=True)

        # Initialize RAG if enabled
        if self.config.enable_rag and extractor.get_policy_text():
            self.rag_extractor = RAGPolicyExtractor(
                extractor.get_policy_text(),
                self.config
            )

        return self.policy

    def get_relevant_policy(self, category: str) -> Optional[str]:
        """Get relevant policy section using RAG (if enabled)"""
        if self.rag_extractor and self.config.enable_rag:
            return self.rag_extractor.get_relevant_policy_for_category(category)
        return None
