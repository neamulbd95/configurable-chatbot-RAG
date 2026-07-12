import pytest
from pydantic import ValidationError

from ragchatbot.config.tables import RelationConfig, TableConfig, load_table_configs


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


def test_qualified_name_without_schema_is_just_the_table_name():
    table = TableConfig(name="products", primary_key="id")
    assert table.qualified_name == "products"


def test_qualified_name_with_schema_is_schema_dot_table():
    table = TableConfig(name="products", primary_key="id", schema="sales")
    assert table.qualified_name == "sales.products"
    assert table.schema_name == "sales"


def test_table_config_schema_field_accepts_python_attribute_name_too():
    # populate_by_name=True: both the YAML alias "schema" and the Python
    # attribute name "schema_name" work when constructing directly.
    table = TableConfig(name="products", primary_key="id", schema_name="sales")
    assert table.qualified_name == "sales.products"


def test_relation_config_schema_defaults_to_none():
    relation = RelationConfig(table="orders", local_key="id", foreign_key="product_id")
    assert relation.schema_name is None


def test_relation_config_accepts_schema_alias():
    relation = RelationConfig(
        table="orders", schema="sales", local_key="id", foreign_key="product_id"
    )
    assert relation.schema_name == "sales"


def test_two_tables_same_name_different_schema_have_distinct_identity():
    sales_products = TableConfig(name="products", primary_key="id", schema="sales")
    archive_products = TableConfig(name="products", primary_key="id", schema="archive")

    assert sales_products.qualified_name != archive_products.qualified_name


def _write_tables_yaml(tmp_path, content: str):
    path = tmp_path / "tables.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_table_configs_applies_default_schema_when_table_omits_it(tmp_path):
    path = _write_tables_yaml(
        tmp_path,
        "tables:\n"
        "  - name: asset\n"
        "    primary_key: id\n"
        "    relations:\n"
        "      - table: valuation\n"
        "        local_key: id\n"
        "        foreign_key: asset_id\n",
    )

    tables = load_table_configs(path, default_schema="esg")

    assert tables[0].schema_name == "esg"
    assert tables[0].qualified_name == "esg.asset"
    # Relations without their own schema inherit the default too.
    assert tables[0].relations[0].schema_name == "esg"


def test_load_table_configs_per_table_schema_overrides_default(tmp_path):
    path = _write_tables_yaml(
        tmp_path,
        "tables:\n"
        "  - name: asset\n"
        "    primary_key: id\n"
        "    schema: archive\n",
    )

    tables = load_table_configs(path, default_schema="esg")

    assert tables[0].schema_name == "archive"


def test_load_table_configs_without_default_schema_leaves_it_unset(tmp_path):
    path = _write_tables_yaml(
        tmp_path, "tables:\n  - name: products\n    primary_key: id\n"
    )

    tables = load_table_configs(path)

    assert tables[0].schema_name is None
    assert tables[0].qualified_name == "products"
