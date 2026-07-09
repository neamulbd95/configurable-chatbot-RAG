from datetime import datetime, timezone

from ragchatbot.ingestion.chunker import chunk_normalized_record, chunk_text, split_sentences
from ragchatbot.models import Lineage, NormalizedRecord


def test_split_sentences_basic():
    assert split_sentences("Hello world. How are you? Fine!") == [
        "Hello world.",
        "How are you?",
        "Fine!",
    ]


def test_split_sentences_empty():
    assert split_sentences("   ") == []


def test_chunk_text_respects_chunk_size_with_overlap():
    text = "One. Two. Three. Four. Five."
    chunks = chunk_text(text, chunk_size=10, chunk_overlap=3)

    assert len(chunks) > 1
    for chunk in chunks:
        # Individual sentences may exceed chunk_size alone, but packed
        # chunks should not balloon far past the configured size.
        assert len(chunk) <= 15


def test_chunk_text_oversized_single_sentence_kept_whole():
    long_sentence = "word " * 50 + "."
    chunks = chunk_text(long_sentence, chunk_size=10, chunk_overlap=2)

    assert len(chunks) == 1
    assert chunks[0].strip().startswith("word")


def test_chunk_normalized_record_carries_lineage_and_scalar_attributes():
    record = NormalizedRecord(
        record_id="products:1",
        normalized_text="Widget is great. It costs ten dollars.",
        attributes={"name": "Widget", "price": 10.0, "tags": ["a", "b"]},
        lineage=Lineage(
            source_table="products",
            primary_key="1",
            extracted_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        ),
    )

    chunks = chunk_normalized_record(record, chunk_size=100, chunk_overlap=10)

    assert len(chunks) >= 1
    first = chunks[0]
    assert first.record_id == "products:1"
    assert first.chunk_id == "products:1::0"
    assert first.metadata["source_table"] == "products"
    assert first.metadata["primary_key"] == "1"
    assert first.metadata["price"] == 10.0
    assert "tags" not in first.metadata  # non-scalar attributes are dropped
    assert first.metadata["access_tags"] == []


def test_chunk_normalized_record_carries_access_tags():
    record = NormalizedRecord(
        record_id="products:1",
        normalized_text="Widget is great.",
        attributes={},
        lineage=Lineage(
            source_table="products",
            primary_key="1",
            extracted_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        ),
    )

    chunks = chunk_normalized_record(record, chunk_size=100, chunk_overlap=10, access_tags=["sales"])

    assert chunks[0].metadata["access_tags"] == ["sales"]
