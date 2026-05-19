from tbox import InMemoryTBoxRepository, TBoxValidator, build_commerce_tbox


def test_commerce_preset_builds_valid_tbox() -> None:
    repo = build_commerce_tbox()
    report = TBoxValidator(repo).validate_tbox()

    assert report.valid, [issue.code for issue in report.errors()]


def test_commerce_preset_contains_minimal_virtual_semantic_layer_schema() -> None:
    repo = build_commerce_tbox()

    class_names = {class_def.name for class_def in repo.list_classes()}
    assert class_names == {
        "Product",
        "ProductVariant",
        "Inventory",
        "SalesChannel",
        "DataSource",
        "Table",
        "QueryDefinition",
    }
    assert repo.get_class("Product").kind == "logical_entity"  # type: ignore[union-attr]
    assert repo.get_class("ProductVariant").kind == "logical_entity"  # type: ignore[union-attr]
    assert repo.get_class("Inventory").kind == "entity"  # type: ignore[union-attr]
    assert repo.get_class("SalesChannel").kind == "entity"  # type: ignore[union-attr]
    assert repo.get_class("DataSource").kind == "entity"  # type: ignore[union-attr]
    assert repo.get_class("Table").kind == "entity"  # type: ignore[union-attr]
    assert repo.get_class("QueryDefinition").kind == "entity"  # type: ignore[union-attr]

    assert repo.is_relationship_allowed(
        from_class="Product", relationship_name="HAS_VARIANT", to_class="ProductVariant"
    )
    assert repo.is_relationship_allowed(
        from_class="ProductVariant", relationship_name="LISTED_ON", to_class="SalesChannel"
    )
    assert repo.is_relationship_allowed(
        from_class="Inventory", relationship_name="FOR_VARIANT", to_class="ProductVariant"
    )
    assert repo.is_relationship_allowed(
        from_class="DataSource", relationship_name="HAS_TABLE", to_class="Table"
    )
    assert repo.is_relationship_allowed(
        from_class="QueryDefinition", relationship_name="READS_FROM", to_class="Table"
    )


def test_sku_is_property_not_class_and_channel_sku_is_relationship_property() -> None:
    repo = build_commerce_tbox()

    assert repo.get_class("SKU") is None

    variant_schema = TBoxValidator(repo).get_effective_class_schema("ProductVariant")
    variant_props = {item.property.name: item.binding for item in variant_schema.properties}
    assert variant_props["ezadmin_sku"].required is True
    assert variant_props["ezadmin_sku"].unique is True

    listed_on_properties = {
        item.property.name: item
        for item in repo.get_properties_of_relationship("commerce.variant_listed_on_channel")
    }
    assert listed_on_properties["channel_sku"].binding.required is True
    assert listed_on_properties["active"].binding.default is True


def test_query_definition_and_datasource_table_schema_exist_for_revenue_queries() -> None:
    repo = build_commerce_tbox()
    validator = TBoxValidator(repo)

    query_schema = validator.get_effective_class_schema("QueryDefinition")
    query_props = {item.property.name for item in query_schema.properties}
    assert {"method_key", "metric_name", "query_type", "parameter_schema", "result_schema"}.issubset(
        query_props
    )
    assert {rel.name for rel in query_schema.outgoing_relationships} == {"READS_FROM"}

    datasource_schema = validator.get_effective_class_schema("DataSource")
    datasource_props = {item.property.name for item in datasource_schema.properties}
    assert {"source_key", "source_type", "connection_ref"}.issubset(datasource_props)


def test_commerce_preset_can_populate_existing_repo_idempotently() -> None:
    repo = InMemoryTBoxRepository()

    returned = build_commerce_tbox(repo)
    returned_again = build_commerce_tbox(repo)

    assert returned is repo
    assert returned_again is repo
    assert TBoxValidator(repo).validate_tbox().valid
    assert len(repo.list_relationships(name="HAS_VARIANT")) == 1
