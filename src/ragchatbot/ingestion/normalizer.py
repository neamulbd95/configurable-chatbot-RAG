"""Null-safe, type-safe normalization of SourceRecord -> NormalizedRecord
(FR-1.3, FR-1.4), with an optional per-table template (FR-6.4) and
relation-list rendering for joined child rows (FR-6.2)."""

from __future__ import annotations

from datetime import date, datetime

from ragchatbot.models import Lineage, NormalizedRecord, SourceRecord


class NormalizationTemplateError(ValueError):
    """Raised when a normalization_template references a column that isn't
    present on the extracted row — the semantic half of FR-6.5 validation
    (syntax is checked at config-load time in config/tables.py)."""


def _format_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        if not value:
            return None
        if all(isinstance(item, dict) for item in value):
            rendered_rows = [
                ", ".join(
                    f"{k}: {_format_value(v)}" for k, v in item.items() if _format_value(v) is not None
                )
                for item in value
            ]
            return "; ".join(rendered_rows)
        return ", ".join(str(item) for item in value)
    return str(value)


def _default_normalized_text(columns: dict[str, object]) -> str:
    lines: list[str] = []
    for column, raw_value in columns.items():
        formatted = _format_value(raw_value)
        if formatted is None:
            continue
        lines.append(f"{column.replace('_', ' ')}: {formatted}")
    return "\n".join(lines)


def _templated_normalized_text(template: str, source_table: str, columns: dict[str, object]) -> str:
    format_values = {key: (_format_value(value) or "") for key, value in columns.items()}
    try:
        return template.format(**format_values)
    except KeyError as exc:
        raise NormalizationTemplateError(
            f"normalization_template for table '{source_table}' references "
            f"unknown column {exc}"
        ) from exc


def normalize_record(record: SourceRecord, template: str | None = None) -> NormalizedRecord:
    normalized_text = (
        _templated_normalized_text(template, record.source_table, record.columns)
        if template is not None
        else _default_normalized_text(record.columns)
    )

    return NormalizedRecord(
        record_id=record.record_id,
        normalized_text=normalized_text,
        attributes=dict(record.columns),
        lineage=Lineage(
            source_table=record.source_table,
            primary_key=record.primary_key_value,
            extracted_at=record.extracted_at,
        ),
    )
