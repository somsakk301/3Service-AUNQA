import pytest
from pydantic import ValidationError

from app.config import Settings


def test_locked_srs_defaults() -> None:
    settings = Settings()

    assert settings.embedding_model == "BAAI/bge-m3"
    assert settings.embedding_dimension == 1024
    assert settings.chunk_size == 500
    assert settings.chunk_overlap == 100


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("embedding_model", "another/model"),
        ("embedding_dimension", 768),
        ("chunk_size", 1000),
        ("chunk_overlap", 50),
    ],
)
def test_locked_srs_values_cannot_be_changed(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})

