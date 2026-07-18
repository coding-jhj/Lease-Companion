"""추가 패키지 없이 동작하는 결정적 Okapi BM25 검색."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Sequence

from lease_companion_ai.rag.models import (
    EvidenceQuery,
    RagChunk,
    RetrievalHit,
    query_to_search_text,
)


Tokenizer = Callable[[str], list[str]]
_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


class BM25Index:
    """메모리 내 청크에 대한 결정적 BM25 검색 인덱스."""

    def __init__(
        self,
        chunks: Sequence[RagChunk],
        *,
        tokenizer: Tokenizer = tokenize,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if not chunks:
            raise ValueError("BM25 인덱스에는 청크가 1개 이상 필요합니다.")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 파라미터는 k1>0, 0<=b<=1이어야 합니다.")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("BM25 인덱스에 중복 chunk_id가 있습니다.")

        self._chunks = tuple(chunks)
        self._tokenizer = tokenizer
        self._k1 = k1
        self._b = b
        self._documents = [tokenizer(chunk.text) for chunk in chunks]
        if any(not document for document in self._documents):
            raise ValueError("BM25 청크에는 검색 가능한 토큰이 필요합니다.")
        self._term_frequencies = [Counter(document) for document in self._documents]
        self._document_frequencies: Counter[str] = Counter()
        for document in self._documents:
            self._document_frequencies.update(set(document))
        self._average_length = sum(map(len, self._documents)) / len(self._documents)

    def _score(self, document_index: int, query_terms: set[str]) -> float:
        term_frequencies = self._term_frequencies[document_index]
        document_length = len(self._documents[document_index])
        document_count = len(self._documents)
        score = 0.0
        for term in query_terms:
            frequency = term_frequencies.get(term, 0)
            if frequency == 0:
                continue
            document_frequency = self._document_frequencies[term]
            inverse_document_frequency = math.log(
                1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + self._k1 * (
                1 - self._b + self._b * document_length / self._average_length
            )
            score += inverse_document_frequency * frequency * (self._k1 + 1) / denominator
        return score

    def search(
        self,
        query: EvidenceQuery | str,
        *,
        top_k: int = 20,
    ) -> list[RetrievalHit]:
        if top_k <= 0:
            raise ValueError("top_k는 양수여야 합니다.")
        query_text = query_to_search_text(query)
        query_terms = set(self._tokenizer(query_text))
        if not query_terms:
            return []

        scored = [
            (self._score(index, query_terms), chunk)
            for index, chunk in enumerate(self._chunks)
        ]
        ranked = sorted(
            ((score, chunk) for score, chunk in scored if score > 0),
            key=lambda item: (-item[0], item[1].chunk_id),
        )[:top_k]
        return [
            RetrievalHit(
                chunk=chunk,
                score=score,
                rank=rank,
                retrieval_method="bm25",
            )
            for rank, (score, chunk) in enumerate(ranked, start=1)
        ]
