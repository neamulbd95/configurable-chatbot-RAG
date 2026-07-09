import pytest
from pydantic import ValidationError

from ragchatbot.config.tables import RelationConfig, TableConfig


def test_table_config_defaults():
    table = TableConfig(name="products", primary_key="id")

    assert table.access_tags == []
    assert table.relations == []
    assert table.normalization_template is None


def test_table_config_accepts_valid_template():
    table = TableConfig(
        name="products",
        primary_key="id",
        normalization_template="Product {name} costs {price}.",
    )
    assert table.normalization_template == "Product {name} costs {price}."


def test_table_config_rejects_positional_placeholder():
    with pytest.raises(ValidationError, match="named placeholders"):
        TableConfig(name="products", primary_key="id", normalization_template="Value: {}")


def test_table_config_rejects_malformed_template_syntax():
    with pytest.raises(ValidationError, match="Invalid normalization_template syntax"):
        TableConfig(name="products", primary_key="id", normalization_template="Unclosed {name")


def test_table_config_with_relations_and_access_tags():
    table = TableConfig(
        name="products",
        primary_key="id",
        access_tags=["sales"],
        relations=[
            RelationConfig(table="orders", local_key="id", foreign_key="product_id"),
        ],
    )

    assert table.access_tags == ["sales"]
    assert table.relations[0].table == "orders"
    assert table.relations[0].max_related_rows == 20
