from typing import Any

import pytest
from bson import ObjectId

from app.chunking import DocumentChunker
from app.config import Settings
from app.extraction.models import ExtractedPage
from app.vectorization import (
    BgeM3Embedder,
    ChromaVectorStore,
    EmbeddingError,
    VectorStoreError,
)


class FakeEmbeddingModel:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[dict[str, Any]] = []

    def encode(self, sentences: list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"sentences": sentences, **kwargs})
        return {"dense_vecs": self.vectors}


class FakeCollection:
    def __init__(self, existing_ids: list[str] | None = None) -> None:
        self.existing_ids = existing_ids or []
        self.upserts: list[dict[str, Any]] = []
        self.deletes: list[dict[str, Any]] = []

    def get(self, **kwargs: Any) -> dict[str, Any]:
        return {"ids": self.existing_ids}

    def upsert(self, **kwargs: Any) -> None:
        self.upserts.append(kwargs)

    def delete(self, **kwargs: Any) -> None:
        self.deletes.append(kwargs)


class FakeChromaClient:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection
        self.names: list[str] = []

    def get_or_create_collection(self, *, name: str) -> FakeCollection:
        self.names.append(name)
        return self.collection


def _chunks(count_text: str = "Evidence") -> list[Any]:
    return DocumentChunker(Settings()).chunk_document(
        document_id=ObjectId(),
        curriculum_id=ObjectId(),
        document_type="cv",
        pages=[ExtractedPage(pageNumber=1, text=count_text)],
    )


def test_bge_m3_dense_embedding_is_1024_dimensions() -> None:
    chunks = _chunks()
    model = FakeEmbeddingModel([[0.01] * 1024])
    records = BgeM3Embedder(Settings(), model=model).embed_chunks(chunks)

    assert len(records) == 1
    assert len(records[0].embedding) == 1024
    assert records[0].text == chunks[0].text
    assert model.calls == [
        {
            "sentences": ["Evidence"],
            "batch_size": 8,
            "return_dense": True,
            "return_sparse": False,
            "return_colbert_vecs": False,
        }
    ]


@pytest.mark.parametrize(
    "vectors",
    [
        [[0.0] * 1023],
        [[float("nan")] * 1024],
        [],
    ],
)
def test_invalid_embedding_output_is_rejected(vectors: list[list[float]]) -> None:
    with pytest.raises(EmbeddingError):
        BgeM3Embedder(
            Settings(), model=FakeEmbeddingModel(vectors)
        ).embed_chunks(_chunks())


def test_chromadb_upsert_contains_exact_vector_record_and_removes_stale_ids() -> None:
    chunks = _chunks("A" * 501)
    records = BgeM3Embedder(
        Settings(), model=FakeEmbeddingModel([[0.01] * 1024 for _ in chunks])
    ).embed_chunks(chunks)
    stale_id = f"{chunks[0].metadata.documentId}-p99-c01"
    collection = FakeCollection(existing_ids=[chunks[0].id, stale_id])
    client = FakeChromaClient(collection)
    store = ChromaVectorStore(Settings(), client=client)

    assert store.upsert_document(records) == len(records)
    assert client.names == ["document_chunks"]
    payload = collection.upserts[0]
    assert payload["ids"] == [record.id for record in records]
    assert payload["documents"] == [record.text for record in records]
    assert all(len(vector) == 1024 for vector in payload["embeddings"])
    assert payload["metadatas"] == [
        record.metadata.to_dict() for record in records
    ]
    assert collection.deletes == [{"ids": [stale_id]}]


def test_chromadb_rejects_mixed_documents() -> None:
    first = _chunks()[0]
    second = _chunks()[0]
    records = BgeM3Embedder(
        Settings(),
        model=FakeEmbeddingModel([[0.0] * 1024, [0.0] * 1024]),
    ).embed_chunks([first, second])
    store = ChromaVectorStore(
        Settings(), client=FakeChromaClient(FakeCollection())
    )
    with pytest.raises(VectorStoreError, match="one documentId"):
        store.upsert_document(records)
