"""
Build FAISS Index
Processes collected documents and builds the vector search index.
Recursively reads all docs from data/docs/ (including subdirectories)
and all processed data from data/processed/ (including StackOverflow JSON).
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.fog.retriever import Retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported text document extensions
TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".yml", ".yaml", ".adoc"}


def load_documents(docs_dir: str, processed_dir: str) -> list[dict]:
    """Load documents from docs and processed directories (recursively)."""
    documents = []
    doc_id = 0

    # ---------------------------------------------------
    # 1. Load text docs (markdown, rst, yml, adoc, txt)
    #    Recurse into ALL subdirectories
    # ---------------------------------------------------
    if os.path.exists(docs_dir):
        for root, _dirs, files in os.walk(docs_dir):
            for filename in sorted(files):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in TEXT_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {filepath}: {e}")
                    continue

                if len(content.strip()) < 50:
                    continue  # skip near-empty files

                # Relative path for source reference
                rel_path = os.path.relpath(filepath, docs_dir)

                # Split long docs into chunks
                chunks = split_into_chunks(content, max_chars=1000)
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "id": f"doc_{doc_id}",
                        "content": chunk,
                        "source": f"{rel_path}#chunk{i}",
                        "metadata": {"type": "documentation", "file": rel_path},
                    })
                    doc_id += 1

    # ---------------------------------------------------
    # 2. Load processed JSON data (sample logs + SO data)
    #    Recurse into ALL subdirectories
    # ---------------------------------------------------
    if os.path.exists(processed_dir):
        for root, _dirs, files in os.walk(processed_dir):
            for filename in sorted(files):
                if not filename.endswith(".json"):
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, processed_dir)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        data = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not parse {filepath}: {e}")
                    continue

                if isinstance(data, list):
                    for item in data:
                        content = _extract_json_content(item)
                        if len(content.strip()) < 30:
                            continue

                        # Chunk long entries
                        chunks = split_into_chunks(content, max_chars=1200)
                        for i, chunk in enumerate(chunks):
                            documents.append({
                                "id": f"doc_{doc_id}",
                                "content": chunk,
                                "source": f"{rel_path}#item{doc_id}",
                                "metadata": {
                                    "type": "stackoverflow" if "so_" in filename else "error_log",
                                    "file": rel_path,
                                    **item.get("metadata", {}),
                                },
                            })
                            doc_id += 1

    logger.info(f"Loaded {doc_id} document chunks total")
    return documents


def _extract_json_content(item: dict) -> str:
    """Extract readable content from a JSON item (supports SO format and generic)."""
    parts = []

    # StackOverflow format: title + body + answers
    if "title" in item:
        parts.append(f"Q: {item['title']}")
    if "body" in item:
        parts.append(item["body"])
    if "answers" in item and isinstance(item["answers"], list):
        for ans in item["answers"][:3]:  # Top 3 answers
            if isinstance(ans, dict) and "body" in ans:
                parts.append(f"A: {ans['body']}")
            elif isinstance(ans, str):
                parts.append(f"A: {ans}")

    # Generic format: content field
    if "content" in item:
        parts.append(item["content"])

    # Fallback: dump the whole item
    if not parts:
        parts.append(json.dumps(item, indent=2)[:2000])

    return "\n\n".join(parts)


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
    index_dir = "data/faiss_index"
    index_path = os.path.join(index_dir, "index.faiss")
    metadata_path = os.path.join(index_dir, "metadata.json")

    # Ensure output dir exists
    os.makedirs(index_dir, exist_ok=True)

    print("[*] Loading documents...")
    documents = load_documents(docs_dir, processed_dir)

    if not documents:
        print("[!] No documents found. Run fetch_knowledge.py first.")
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

    print(f"[*] Building FAISS index with {len(documents)} documents...")

    # Show breakdown by type
    type_counts = {}
    for doc in documents:
        t = doc.get("metadata", {}).get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    for doc_type, count in sorted(type_counts.items()):
        print(f"    {doc_type}: {count} chunks")

    retriever = Retriever()
    retriever.build_index(
        documents=documents,
        batch_size=32,
        save_path=(index_path, metadata_path),
    )

    print(f"\n[OK] Index saved to {index_path}")
    print(f"[OK] Metadata saved to {metadata_path}")
    print(f"[OK] Total: {len(documents)} document chunks indexed")
