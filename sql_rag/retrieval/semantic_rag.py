import os
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from .schema_registry import SchemaRegistry
from ..llm.prompts import format_semantic_summary_prompt

class SemanticRAG:
    def __init__(self):
        self.corpus: List[Dict[str, Any]] = []
        self.index = None
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
        self.chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

    def build_from_db(self, db_path: str) -> None:
        """Extract 'unstructured' documents from the DB for semantic search."""
        registry = SchemaRegistry(db_path)
        schema = registry.load_schema()
        
        docs: List[Dict[str, Any]] = []
        for table_name, info in schema.items():
            # Metadata-aware chunking: Group by table and create descriptive strings
            sample_rows = info.get("sample_rows", [])
            for row in sample_rows:
                # Filter out None values and create a key-value string
                content = "; ".join(f"{k}: {v}" for k, v in row.items() if v is not None)
                if not content.strip(): continue
                
                doc_text = f"Table: {table_name}. Data: {content}"
                docs.append({
                    "text": doc_text,
                    "metadata": {"table": table_name, "row": row}
                })
        
        # Add static documentation if any exists (placeholder)
        # docs.append({"text": "Traffic detector drift can occur due to temperature changes...", "metadata": {"source": "notes"}})
        
        self.corpus = docs
        self._build_index()

    def _build_index(self) -> None:
        if not self.corpus:
            return
            
        texts = [doc["text"] for doc in self.corpus]
        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.embedding_model
            )
            embeddings = np.array([e.embedding for e in response.data]).astype("float32")
            
            self.index = faiss.IndexFlatL2(embeddings.shape[1])
            self.index.add(embeddings)
        except Exception as e:
            print(f"Failed to build semantic index: {e}")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or not self.corpus:
            return []
            
        try:
            response = self.client.embeddings.create(
                input=[query],
                model=self.embedding_model
            )
            query_vector = np.array([response.data[0].embedding]).astype("float32")
            
            _, indices = self.index.search(query_vector, top_k)
            
            results = []
            for idx in indices[0]:
                if idx < 0 or idx >= len(self.corpus): continue
                results.append(self.corpus[idx])
            return results
        except Exception as e:
            print(f"Semantic search failed: {e}")
            return []

    def summarize(self, question: str, docs: List[Dict[str, Any]]) -> str:
        if not docs:
            return "No relevant semantic context found."
            
        context_text = "\n\n".join([doc["text"] for doc in docs])
        # Note: We'll use the grounded answer generator logic for consistency, 
        # but this is for pure semantic RAG.
        prompt = format_semantic_summary_prompt(question, context_text)
        
        response = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[{"role": "user", "content": prompt}],
            timeout=30
        )
        return response.choices[0].message.content.strip()
