from datetime import datetime, timezone

import pytest

from ragchatbot.ingestion.normalizer import NormalizationTemplateError, normalize_record
from ragchatbot.models import SourceRecord


def _record(**columns: object) -> SourceRecord:
    return SourceRecord(
        source_table="products",
        primary_key_value="42",
        columns=columns,
        extracted_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
    )


def test_normalize_record_formats_scalars_and_skips_nulls():
    record = _record(name="Widget", price=19.5, in_stock=True, discontinued=False, notes=None)

    normalized = normalize_record(record)

    assert "name: Widget" in normalized.normalized_text
    assert "price: 19.5" in normalized.normalized_text
    assert "in stock: yes" in normalized.normalized_text
    assert "discontinued: no" in normalized.normalized_text
    assert "notes" not in normalized.normalized_text


def test_normalize_record_preserves_lineage():
    record = _record(name="Widget")

    normalized = normalize_record(record)

    assert normalized.record_id == "products:42"
    assert normalized.lineage.source_table == "products"
    assert normalized.lineage.primary_key == "42"


def test_normalize_record_formats_datetime_iso():
    record = _record(created_at=datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc))

    normalized = normalize_record(record)

    assert "created at: 2026-01-01T12:30:00+00:00" in normalized.normalized_text


def test_normalize_record_with_template_renders_placeholders():
    record = _record(name="Widget", price=19.5)

    normalized = normalize_record(record, template="Product {name} costs {price}.")

    assert normalized.normalized_text == "Product Widget costs 19.5."


def test_normalize_record_with_template_unknown_column_raises_clear_error():
    record = _record(name="Widget")

    with pytest.raises(NormalizationTemplateError, match="unknown column"):
        normalize_record(record, template="Product {name} costs {price}.")


def test_normalize_record_formats_relation_list_of_dicts():
    record = _record(
        name="Widget",
        orders=[{"order_id": 1, "total": 20.0}, {"order_id": 2, "total": 15.0}],
    )

    normalized = normalize_record(record)

    assert "orders: order_id: 1, total: 20; order_id: 2, total: 15" in normalized.normalized_text


def test_normalize_record_skips_empty_relation_list():
    record = _record(name="Widget", orders=[])

    normalized = normalize_record(record)

    assert "orders" not in normalized.normalized_text
