"""
Build FAISS Index
Processes collected documents and builds the vector search index.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.fog.retriever import Retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_documents(docs_dir: str, processed_dir: str) -> list[dict]:
    """Load documents from docs and processed directories."""
    documents = []
    doc_id = 0

    # Load markdown docs
    if os.path.exists(docs_dir):
        for filename in os.listdir(docs_dir):
            if filename.endswith((".md", ".txt")):
                filepath = os.path.join(docs_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Split long docs into chunks
                chunks = split_into_chunks(content, max_chars=1000)
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "id": f"doc_{doc_id}",
                        "content": chunk,
                        "source": f"{filename}#chunk{i}",
                        "metadata": {"type": "documentation", "file": filename},
                    })
                    doc_id += 1

    # Load processed error logs
    if os.path.exists(processed_dir):
        for filename in os.listdir(processed_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(processed_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            documents.append({
                                "id": f"doc_{doc_id}",
                                "content": item.get("content", json.dumps(item)),
                                "source": filename,
                                "metadata": {"type": "error_log", **item.get("metadata", {})},
                            })
                            doc_id += 1

    logger.info(f"Loaded {len(documents)} document chunks")
    return documents


def split_into_chunks(text: str, max_chars: int = 1000) -> list[str]:
    """Split text into chunks of roughly max_chars size."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks or [text]


if __name__ == "__main__":
    docs_dir = "data/docs"
    processed_dir = "data/processed"
    index_path = "data/faiss_index/index.faiss"
    metadata_path = "data/faiss_index/metadata.json"

    print("📂 Loading documents...")
    documents = load_documents(docs_dir, processed_dir)

    if not documents:
        print("⚠️  No documents found. Run collect_logs.py first.")
        print("    Creating sample documents for testing...")
        documents = [
            {
                "id": "sample_0",
                "content": "ModuleNotFoundError is raised when Python cannot find the module. Fix: pip install <module_name>",
                "source": "sample",
                "metadata": {"type": "sample"},
            },
            {
                "id": "sample_1",
                "content": "npm ERR! ERESOLVE means npm cannot resolve the dependency tree. Fix: Use --legacy-peer-deps flag.",
                "source": "sample",
                "metadata": {"type": "sample"},
            },
            {
                "id": "sample_2",
                "content": "Docker permission denied errors usually mean the Dockerfile runs as root. Fix: Add USER directive.",
                "source": "sample",
                "metadata": {"type": "sample"},
            },
        ]

    print(f"🔧 Building FAISS index with {len(documents)} documents...")
    retriever = Retriever()
    retriever.build_index(
        documents=documents,
        batch_size=32,
        save_path=(index_path, metadata_path),
    )

    print(f"✅ Index saved to {index_path}")
    print(f"✅ Metadata saved to {metadata_path}")
