"""Local deterministic retrieval for the enterprise policy knowledge base."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from .utils import DATASETS_DIR
except ImportError:
    from utils import DATASETS_DIR


@dataclass
class ContextChunk:
    """A retrievable policy section."""

    id: str
    title: str
    text: str
    score: float = 0.0

    def render(self) -> str:
        """Render the chunk for prompt context."""
        return f"[{self.id}] {self.title}\n{self.text}"


def split_knowledge_base(text: str) -> list[ContextChunk]:
    """Split a markdown knowledge base into heading-based chunks."""
    chunks: list[ContextChunk] = []
    current_title = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_title and current_lines:
                chunk_id = f"kb_{len(chunks) + 1:02d}"
                chunks.append(ContextChunk(chunk_id, current_title, " ".join(current_lines).strip()))
            current_title = line.removeprefix("## ").strip()
            current_lines = []
        elif current_title and line.strip():
            current_lines.append(line.strip())

    if current_title and current_lines:
        chunk_id = f"kb_{len(chunks) + 1:02d}"
        chunks.append(ContextChunk(chunk_id, current_title, " ".join(current_lines).strip()))

    return chunks


class PolicyRetriever:
    """A lightweight TF-IDF retriever for policy sections."""

    def __init__(self, knowledge_base_path: Path | None = None):
        self.knowledge_base_path = knowledge_base_path or DATASETS_DIR / "enterprise_policy_knowledge_base.md"
        self.chunks = self._load_chunks()
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        corpus = [f"{chunk.title} {chunk.text}" for chunk in self.chunks]
        self.matrix = self.vectorizer.fit_transform(corpus) if corpus else None

    def _load_chunks(self) -> list[ContextChunk]:
        if not self.knowledge_base_path.exists():
            return []
        return split_knowledge_base(self.knowledge_base_path.read_text(encoding="utf-8"))

    def retrieve(self, query: str, top_k: int = 3) -> list[ContextChunk]:
        """Return top-k relevant context chunks for a query."""
        if not self.chunks or self.matrix is None:
            return []
        query_vector = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self.matrix).flatten()
        ranked_indexes = scores.argsort()[::-1][:top_k]
        results: list[ContextChunk] = []
        for idx in ranked_indexes:
            chunk = self.chunks[int(idx)]
            results.append(ContextChunk(chunk.id, chunk.title, chunk.text, float(scores[idx])))
        return results

    def section_by_title(self, title: str) -> ContextChunk | None:
        """Return a chunk by exact title when available."""
        normalized = re.sub(r"\s+", " ", title.strip().lower())
        for chunk in self.chunks:
            if re.sub(r"\s+", " ", chunk.title.lower()) == normalized:
                return chunk
        return None


def render_context(chunks: list[ContextChunk]) -> str:
    """Render retrieved chunks as a prompt-ready context block."""
    return "\n\n".join(chunk.render() for chunk in chunks)


if __name__ == "__main__":
    retriever = PolicyRetriever()
    for result in retriever.retrieve("Can I paste customer API keys into a ticket?"):
        print(f"{result.id} {result.title} score={result.score:.3f}")
