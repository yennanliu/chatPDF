from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class RAGConfig:
    # chunking
    chunk_size: int = 800
    chunk_overlap: int = 100
    chunker: str = "recursive"       # recursive | sentence | semantic

    # retrieval
    top_k: int = 5
    retriever: str = "dense"         # dense | sparse | hybrid
    hybrid_alpha: float = 0.5

    # reranking
    reranker: str = "none"           # none | cross_encoder | llm
    rerank_top_n: int = 3

    # embedding
    embedder: str = "local"          # local | openai

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> RAGConfig:
        data = json.loads(raw) if raw else {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
