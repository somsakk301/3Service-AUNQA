import os

import chromadb
import pytest
from bson import ObjectId

from app.chunking import DocumentChunker
from app.config import Settings
from app.extraction.models import ExtractedPage
from app.vectorization import BgeM3Embedder, ChromaVectorStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose services",
    ),
]


class IntegrationEmbeddingModel:
    def encode(self, sentences: list[str], **kwargs: object) -> dict[str, object]:
        return {"dense_vecs": [[float(index == 0) for index in range(1024)] for _ in sentences]}


def test_chromadb_upsert_is_idempotent_and_traceable() -> None:
    settings = Settings()
    client = chromadb.HttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
    document_id = ObjectId()
    chunks = DocumentChunker(settings).chunk_document(
        document_id=document_id,
        curriculum_id=ObjectId(),
        document_type="cv",
        pages=[ExtractedPage(pageNumber=7, text="V" * 501)],
    )
    records = BgeM3Embedder(
        settings, model=IntegrationEmbeddingModel()
    ).embed_chunks(chunks)
    store = ChromaVectorStore(settings, client=client)
    try:
        assert store.upsert_document(records) == 2
        assert store.upsert_document(records) == 2
        collection = client.get_collection("document_chunks")
        result = collection.get(
            where={"documentId": str(document_id)},
            include=["documents", "embeddings", "metadatas"],
        )
        assert sorted(result["ids"]) == sorted(record.id for record in records)
        assert all(len(vector) == 1024 for vector in result["embeddings"])
        assert {metadata["page"] for metadata in result["metadatas"]} == {7}
        assert all(
            metadata["documentId"] == str(document_id)
            for metadata in result["metadatas"]
        )
    finally:
        store.delete_document(str(document_id))


@pytest.mark.model
@pytest.mark.skipif(
    os.getenv("RUN_MODEL_TESTS") != "1",
    reason="set RUN_MODEL_TESTS=1 to download and run BAAI/bge-m3",
)
def test_real_bge_m3_returns_locked_dimension() -> None:
    settings = Settings()
    chunk = DocumentChunker(settings).chunk_document(
        document_id=ObjectId(),
        curriculum_id=ObjectId(),
        document_type="cv",
        pages=[ExtractedPage(pageNumber=1, text="หลักฐานการประกันคุณภาพการศึกษา")],
    )
    records = BgeM3Embedder(settings).embed_chunks(chunk, batch_size=1)
    assert len(records) == 1
    assert len(records[0].embedding) == 1024
