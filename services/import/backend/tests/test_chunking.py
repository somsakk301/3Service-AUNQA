import pytest
from bson import ObjectId

from app.chunking import ChunkingError, DocumentChunker, PageContext
from app.config import Settings
from app.extraction.models import ExtractedPage


@pytest.fixture
def chunker() -> DocumentChunker:
    return DocumentChunker(Settings())


def test_chunking_uses_locked_size_overlap_and_srs_chunk_id(
    chunker: DocumentChunker,
) -> None:
    document_id = ObjectId()
    curriculum_id = ObjectId()
    text = "A" * 901

    chunks = chunker.chunk_document(
        document_id=document_id,
        curriculum_id=curriculum_id,
        document_type="cv",
        pages=[ExtractedPage(pageNumber=12, text=text)],
    )

    assert [len(chunk.text) for chunk in chunks] == [500, 500, 101]
    assert chunks[0].text[-100:] == chunks[1].text[:100]
    assert chunks[1].text[-100:] == chunks[2].text[:100]
    assert [chunk.id for chunk in chunks] == [
        f"{document_id}-p12-c01",
        f"{document_id}-p12-c02",
        f"{document_id}-p12-c03",
    ]


def test_chunking_is_page_aware_and_resets_index_per_page(
    chunker: DocumentChunker,
) -> None:
    document_id = ObjectId()
    curriculum_id = ObjectId()
    chunks = chunker.chunk_document(
        document_id=str(document_id),
        curriculum_id=str(curriculum_id),
        document_type="curriculum",
        pages=[
            ExtractedPage(pageNumber=2, text="Second page"),
            ExtractedPage(pageNumber=1, text="First page"),
        ],
    )

    assert [chunk.metadata.page for chunk in chunks] == [1, 2]
    assert [chunk.metadata.chunkIndex for chunk in chunks] == [1, 1]
    assert [chunk.id for chunk in chunks] == [
        f"{document_id}-p1-c01",
        f"{document_id}-p2-c01",
    ]


def test_required_and_optional_metadata_are_chroma_compatible(
    chunker: DocumentChunker,
) -> None:
    document_id = ObjectId()
    curriculum_id = ObjectId()
    person_id = ObjectId()
    chunks = chunker.chunk_document(
        document_id=document_id,
        curriculum_id=curriculum_id,
        document_type="appointment",
        pages=[ExtractedPage(pageNumber=3, text="Appointment evidence")],
        page_contexts={
            3: PageContext(section="  appointment  ", personId=str(person_id))
        },
    )

    assert chunks[0].metadata.to_dict() == {
        "documentId": str(document_id),
        "curriculumId": str(curriculum_id),
        "documentType": "appointment",
        "page": 3,
        "chunkIndex": 1,
        "section": "appointment",
        "personId": str(person_id),
    }
    assert chunks[0].to_dict()["metadata"] == chunks[0].metadata.to_dict()


def test_unknown_optional_metadata_is_omitted(chunker: DocumentChunker) -> None:
    chunk = chunker.chunk_document(
        document_id=ObjectId(),
        curriculum_id=ObjectId(),
        document_type="cv",
        pages=[ExtractedPage(pageNumber=1, text="Short evidence")],
        page_contexts={1: PageContext(section="   ")},
    )[0]
    assert "section" not in chunk.metadata.to_dict()
    assert "personId" not in chunk.metadata.to_dict()


def test_invalid_optional_person_id_is_rejected(chunker: DocumentChunker) -> None:
    with pytest.raises(ChunkingError, match="personId"):
        chunker.chunk_document(
            document_id=ObjectId(),
            curriculum_id=ObjectId(),
            document_type="cv",
            pages=[ExtractedPage(pageNumber=1, text="Evidence")],
            page_contexts={1: PageContext(personId="invalid")},
        )


def test_blank_pages_are_skipped_without_losing_other_page_source(
    chunker: DocumentChunker,
) -> None:
    chunks = chunker.chunk_document(
        document_id=ObjectId(),
        curriculum_id=ObjectId(),
        document_type="cv",
        pages=[
            ExtractedPage(pageNumber=1, text="  \n  "),
            ExtractedPage(pageNumber=2, text="Evidence"),
        ],
    )
    assert len(chunks) == 1
    assert chunks[0].metadata.page == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [("document_id", "invalid"), ("curriculum_id", "invalid")],
)
def test_invalid_required_object_id_is_rejected(
    chunker: DocumentChunker,
    field: str,
    value: str,
) -> None:
    arguments = {
        "document_id": ObjectId(),
        "curriculum_id": ObjectId(),
        "document_type": "cv",
        "pages": [ExtractedPage(pageNumber=1, text="Evidence")],
    }
    arguments[field] = value
    with pytest.raises(ChunkingError, match="ObjectId"):
        chunker.chunk_document(**arguments)  # type: ignore[arg-type]


def test_duplicate_page_number_is_rejected(chunker: DocumentChunker) -> None:
    with pytest.raises(ChunkingError, match="unique"):
        chunker.chunk_document(
            document_id=ObjectId(),
            curriculum_id=ObjectId(),
            document_type="cv",
            pages=[
                ExtractedPage(pageNumber=1, text="First"),
                ExtractedPage(pageNumber=1, text="Duplicate"),
            ],
        )


def test_all_blank_document_is_rejected(chunker: DocumentChunker) -> None:
    with pytest.raises(ChunkingError, match="no chunkable text"):
        chunker.chunk_document(
            document_id=ObjectId(),
            curriculum_id=ObjectId(),
            document_type="cv",
            pages=[ExtractedPage(pageNumber=1, text=" \n ")],
        )
