from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import joblib
from pypdf import PdfReader
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import REFERENCE_DIR, VECTOR_STORE_DIR


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def chunk_text(text: str, chunk_size: int = 420, overlap: int = 80) -> List[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def build_reference_chunks(reference_dir: Path) -> List[Dict]:
    chunks: List[Dict] = []
    for path in sorted(reference_dir.glob("*.json")):
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            topics = " ".join(item.get("related_topics", []))
            summary = item.get("summary", "")
            if summary:
                chunks.append(
                    {
                        "chunk_id": f"{item['id']}::summary",
                        "title": item.get("title", "未命名参考"),
                        "source": item.get("source", "未注明来源"),
                        "source_url": item.get("source_url", ""),
                        "source_type": item.get("source_type", "reference"),
                        "related_topics": item.get("related_topics", []),
                        "label": "摘要",
                        "text": summary,
                        "highlights": [],
                        "retrieval_text": normalize_text(f"{item.get('title', '')} {topics} {summary}"),
                    }
                )
            for index, paragraph in enumerate(item.get("evidence_paragraphs", [])):
                text = paragraph.get("text", "")
                if not text:
                    continue
                chunks.append(
                    {
                        "chunk_id": f"{item['id']}::evidence::{index}",
                        "title": item.get("title", "未命名参考"),
                        "source": item.get("source", "未注明来源"),
                        "source_url": item.get("source_url", ""),
                        "source_type": item.get("source_type", "reference"),
                        "related_topics": item.get("related_topics", []),
                        "label": paragraph.get("label", f"证据段落 {index + 1}"),
                        "text": text,
                        "highlights": paragraph.get("highlights", []),
                        "retrieval_text": normalize_text(
                            f"{item.get('title', '')} {topics} {paragraph.get('label', '')} {text}"
                        ),
                    }
                )
    return chunks


def build_pdf_chunks(files_dir: Path) -> List[Dict]:
    chunks: List[Dict] = []
    for pdf_path in sorted(files_dir.glob("*.pdf")):
        title = pdf_path.stem.lstrip("_")
        reader = PdfReader(str(pdf_path))
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages[:12])
        for index, chunk in enumerate(chunk_text(extracted)):
            chunks.append(
                {
                    "chunk_id": f"pdf::{pdf_path.stem}::{index}",
                    "title": title,
                    "source": str(pdf_path),
                    "source_url": "",
                    "source_type": "local_pdf_chunk",
                    "related_topics": [title],
                    "label": f"PDF片段 {index + 1}",
                    "text": chunk,
                    "highlights": [],
                    "retrieval_text": normalize_text(f"{title} {chunk}"),
                }
            )
    return chunks


def build_vector_store(*, files_dir: Path, reference_dir: Path, output_dir: Path) -> Dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks = build_reference_chunks(reference_dir) + build_pdf_chunks(files_dir)
    if not chunks:
        raise ValueError("No chunks available to build vector store")

    vectorizer = TfidfVectorizer(max_features=8000, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([item["retrieval_text"] for item in chunks])

    (output_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    sparse.save_npz(output_dir / "tfidf_matrix.npz", matrix)
    joblib.dump(vectorizer, output_dir / "tfidf_vectorizer.joblib")

    return {"chunks": len(chunks), "features": int(matrix.shape[1])}


class LocalVectorRetriever:
    def __init__(self, vector_dir: Path | None = None) -> None:
        self.vector_dir = vector_dir or VECTOR_STORE_DIR
        self._loaded = False
        self._chunks: List[Dict] = []
        self._matrix = None
        self._vectorizer = None

    @property
    def ready(self) -> bool:
        return (
            (self.vector_dir / "chunks.json").exists()
            and (self.vector_dir / "tfidf_matrix.npz").exists()
            and (self.vector_dir / "tfidf_vectorizer.joblib").exists()
        )

    def load(self) -> None:
        if self._loaded:
            return
        if not self.ready:
            raise FileNotFoundError("Local vector store has not been built yet")
        self._chunks = json.loads((self.vector_dir / "chunks.json").read_text(encoding="utf-8"))
        self._matrix = sparse.load_npz(self.vector_dir / "tfidf_matrix.npz")
        self._vectorizer = joblib.load(self.vector_dir / "tfidf_vectorizer.joblib")
        self._loaded = True

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.ready:
            return []
        self.load()
        query_vec = self._vectorizer.transform([normalize_text(query)])
        scores = cosine_similarity(query_vec, self._matrix).ravel()
        top_indices = scores.argsort()[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            item = dict(self._chunks[int(idx)])
            item["score"] = round(score, 4)
            results.append(item)
        return results

    def retrieve_as_references(self, query: str, top_k: int = 4) -> List[Dict]:
        results = self.retrieve(query, top_k=top_k)
        grouped: Dict[str, Dict] = {}
        for item in results:
            key = item["title"]
            if key not in grouped:
                grouped[key] = {
                    "id": f"rag::{item['chunk_id']}",
                    "title": item["title"],
                    "source": item["source"],
                    "source_url": item.get("source_url", ""),
                    "source_type": item.get("source_type", "rag"),
                    "related_topics": item.get("related_topics", []),
                    "summary": f"RAG 检索命中，相关度 {item['score']}",
                    "evidence_paragraphs": [],
                }
            grouped[key]["evidence_paragraphs"].append(
                {
                    "label": item.get("label", "证据片段"),
                    "text": item.get("text", ""),
                    "highlights": item.get("highlights", [])[:5],
                }
            )
        return list(grouped.values())

