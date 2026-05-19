from __future__ import annotations

from typing import Any

from ..memory import InMemoryTBoxRepository
from ..repository import TBoxRepository


def build_commerce_tbox(repo: TBoxRepository | None = None) -> TBoxRepository:
    """Build the minimal commerce TBox as a virtual semantic layer.

    This preset does not create product/variant/channel ABox instances. It only
    defines the logical classes, keys, source/table/query-method shape, and
    relationship semantics needed to connect existing data silos.
    """

    repo = repo or InMemoryTBoxRepository()

    _define_interfaces(repo)
    _define_properties(repo)
    _define_classes(repo)
    _implement_interfaces(repo)
    _attach_properties(repo)
    _define_relationships(repo)
    _attach_relationship_properties(repo)
    _define_constraints(repo)

    return repo


def _define_interfaces(repo: TBoxRepository) -> None:
    repo.create_interface("NamedResource", description="Has a human-readable name")
    repo.create_interface("StatusTracked", description="Has lifecycle/status information")
    repo.create_interface("TimeScoped", description="Has a time boundary or update time")


def _define_properties(repo: TBoxRepository) -> None:
    properties: dict[str, tuple[str, str, dict[str, Any] | None]] = {
        "name": ("string", "Human-readable name", None),
        "status": ("string", "Lifecycle status", None),
        "product_code": ("string", "Product code in source systems", None),
        "brand": ("string", "Brand name", None),
        "variant_code": ("string", "Variant code in source systems", None),
        "ezadmin_sku": ("string", "Integrated ezAdmin SKU on ProductVariant", None),
        "variant_attributes": ("json", "Variant attributes such as color/size", None),
        "channel_code": ("string", "Sales channel code", None),
        "channel_type": ("string", "Sales channel type", None),
        "channel_sku": ("string", "Channel-specific SKU on LISTED_ON relationship", None),
        "channel_product_id": ("string", "Channel product identifier", None),
        "quantity": ("integer", "Inventory quantity", None),
        "available_quantity": ("integer", "Available inventory quantity", None),
        "reserved_quantity": ("integer", "Reserved inventory quantity", None),
        "updated_at": ("datetime", "Updated timestamp", None),
        "source_key": ("string", "Stable data source key", None),
        "source_type": (
            "string",
            "Data source type",
            {"allowed_values": ["bigquery", "neon_db"]},
        ),
        "connection_ref": ("string", "Secret/env reference for connection", None),
        "table_name": ("string", "Physical table or view name", None),
        "schema_name": ("string", "Schema name", None),
        "dataset_name": ("string", "BigQuery dataset name", None),
        "fully_qualified_name": ("string", "Fully qualified table name", None),
        "table_role": ("string", "Table role such as product, inventory, revenue", None),
        "method_key": ("string", "Query method key", None),
        "metric_name": ("string", "Metric name such as revenue", None),
        "query_type": ("string", "Query type such as sql/dbt/api", None),
        "query_template": ("string", "Parameterized query template", None),
        "parameter_schema": ("json", "Query parameter schema", None),
        "result_schema": ("json", "Query result schema", None),
        "active": ("boolean", "Active flag", None),
    }
    for name, (datatype, description, metadata) in properties.items():
        repo.create_property(
            name,
            datatype=datatype,
            description=description,
            metadata=metadata,
        )


def _define_classes(repo: TBoxRepository) -> None:
    classes: tuple[tuple[str, str, str], ...] = (
        ("Product", "logical_entity", "상품 마스터. 원천 데이터는 ezAdmin 등에 존재한다."),
        ("ProductVariant", "logical_entity", "판매 단위. ezAdmin SKU를 속성으로 가진다."),
        ("Inventory", "entity", "재고 상태. 전체/채널별 재고를 모두 표현 가능하다."),
        ("SalesChannel", "entity", "판매 채널."),
        ("DataSource", "entity", "BigQuery, Neon DB 같은 외부 데이터 원천."),
        ("Table", "entity", "DataSource 안의 물리 테이블 또는 뷰."),
        ("QueryDefinition", "entity", "기간별 매출 같은 데이터를 조회하는 방법."),
    )
    for name, kind, description in classes:
        repo.create_class(name, kind=kind, description=description)


def _implement_interfaces(repo: TBoxRepository) -> None:
    for class_name in ("Product", "ProductVariant", "SalesChannel", "DataSource", "QueryDefinition"):
        repo.implement_interface(class_name=class_name, interface_name="NamedResource")

    for class_name in ("Product", "ProductVariant", "SalesChannel"):
        repo.implement_interface(class_name=class_name, interface_name="StatusTracked")

    for class_name in ("Inventory",):
        repo.implement_interface(class_name=class_name, interface_name="TimeScoped")


def _attach_properties(repo: TBoxRepository) -> None:
    _attach_interface(repo, "NamedResource", "name", required=True, nullable=False)
    _attach_interface(repo, "StatusTracked", "status", required=True, nullable=False)
    _attach_interface(repo, "TimeScoped", "updated_at", required=True, nullable=False)

    class_properties: dict[str, tuple[tuple[str, dict[str, Any]], ...]] = {
        "Product": (
            ("product_code", {"required": True, "unique": True, "nullable": False}),
            ("brand", {}),
        ),
        "ProductVariant": (
            ("variant_code", {"required": True, "unique": True, "nullable": False}),
            ("ezadmin_sku", {"required": True, "unique": True, "nullable": False}),
            ("variant_attributes", {}),
        ),
        "Inventory": (
            ("quantity", {"required": True, "nullable": False}),
            ("available_quantity", {}),
            ("reserved_quantity", {}),
        ),
        "SalesChannel": (
            ("channel_code", {"required": True, "unique": True, "nullable": False}),
            ("channel_type", {}),
        ),
        "DataSource": (
            ("source_key", {"required": True, "unique": True, "nullable": False}),
            ("source_type", {"required": True, "nullable": False}),
            ("connection_ref", {}),
        ),
        "Table": (
            ("table_name", {"required": True, "nullable": False}),
            ("schema_name", {}),
            ("dataset_name", {}),
            ("fully_qualified_name", {"required": True, "unique": True, "nullable": False}),
            ("table_role", {}),
        ),
        "QueryDefinition": (
            ("method_key", {"required": True, "unique": True, "nullable": False}),
            ("metric_name", {"required": True, "nullable": False}),
            ("query_type", {"required": True, "nullable": False}),
            ("query_template", {}),
            ("parameter_schema", {"required": True, "nullable": False}),
            ("result_schema", {"required": True, "nullable": False}),
        ),
    }
    for class_name, properties in class_properties.items():
        for property_name, options in properties:
            repo.attach_property_to_class(
                class_name=class_name,
                property_name=property_name,
                **options,
            )


def _define_relationships(repo: TBoxRepository) -> None:
    relationships = (
        ("commerce.product_has_variant", "HAS_VARIANT", "Product", "ProductVariant", 1, None, True),
        (
            "commerce.variant_listed_on_channel",
            "LISTED_ON",
            "ProductVariant",
            "SalesChannel",
            0,
            None,
            False,
        ),
        ("commerce.inventory_for_variant", "FOR_VARIANT", "Inventory", "ProductVariant", 1, 1, True),
        ("commerce.inventory_for_channel", "FOR_CHANNEL", "Inventory", "SalesChannel", 0, 1, False),
        ("commerce.datasource_has_table", "HAS_TABLE", "DataSource", "Table", 0, None, False),
        ("commerce.query_reads_from_table", "READS_FROM", "QueryDefinition", "Table", 1, None, True),
    )
    for relationship_id, name, from_class, to_class, min_count, max_count, required in relationships:
        repo.define_relationship(
            id=relationship_id,
            name=name,
            from_class=from_class,
            to_class=to_class,
            min_count=min_count,
            max_count=max_count,
            required=required,
        )


def _attach_relationship_properties(repo: TBoxRepository) -> None:
    relationship_properties: dict[str, tuple[tuple[str, dict[str, Any]], ...]] = {
        "commerce.variant_listed_on_channel": (
            ("channel_sku", {"required": True, "nullable": False}),
            ("channel_product_id", {}),
            ("active", {"required": True, "nullable": False, "default": True}),
        ),
    }
    for relationship_id, properties in relationship_properties.items():
        for property_name, options in properties:
            repo.attach_property_to_relationship(
                relationship_id=relationship_id,
                property_name=property_name,
                **options,
            )


def _define_constraints(repo: TBoxRepository) -> None:
    constraints = (
        ("commerce.product.product_code_unique", "unique", "class", "Product", ("product_code",), None),
        (
            "commerce.variant.variant_code_unique",
            "unique",
            "class",
            "ProductVariant",
            ("variant_code",),
            None,
        ),
        (
            "commerce.variant.ezadmin_sku_unique",
            "unique",
            "class",
            "ProductVariant",
            ("ezadmin_sku",),
            None,
        ),
        (
            "commerce.channel.channel_code_unique",
            "unique",
            "class",
            "SalesChannel",
            ("channel_code",),
            None,
        ),
        (
            "commerce.datasource.source_key_unique",
            "unique",
            "class",
            "DataSource",
            ("source_key",),
            None,
        ),
        (
            "commerce.table.fqn_unique",
            "unique",
            "class",
            "Table",
            ("fully_qualified_name",),
            None,
        ),
        (
            "commerce.query.method_key_unique",
            "unique",
            "class",
            "QueryDefinition",
            ("method_key",),
            None,
        ),
        (
            "commerce.channel_sku_unique_per_channel",
            "scoped_unique",
            "relationship",
            "commerce.variant_listed_on_channel",
            ("channel_sku",),
            {"scope": "to_class:SalesChannel"},
        ),
    )
    for constraint_id, kind, target_kind, target_id, property_names, metadata in constraints:
        repo.create_constraint(
            id=constraint_id,
            kind=kind,
            target_kind=target_kind,  # type: ignore[arg-type]
            target_id=target_id,
            property_names=property_names,
            metadata=metadata,
        )


def _attach_interface(
    repo: TBoxRepository,
    interface_name: str,
    property_name: str,
    **options: Any,
) -> None:
    repo.attach_property_to_interface(
        interface_name=interface_name,
        property_name=property_name,
        **options,
    )
