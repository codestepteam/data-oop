from __future__ import annotations

import re
from typing import Any

from .exceptions import TBoxNotFoundError
from .models import (
    ClassDef,
    ConstraintDef,
    EffectiveClassSchema,
    EffectivePropertyDef,
    EffectiveRelationshipSchema,
    PropertyBinding,
    PropertyDef,
    RelationshipDef,
    ValidationIssue,
    ValidationReport,
)
from .repository import TBoxRepository

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
ALLOWED_CLASS_KINDS = {"entity", "logical_entity"}

SUPPORTED_DATATYPES = {
    "unknown",
    "any",
    "string",
    "str",
    "integer",
    "int",
    "float",
    "number",
    "boolean",
    "bool",
    "date",
    "datetime",
    "object",
    "json",
    "array",
    "list",
    "uuid",
}


class TBoxValidator:
    """Validates TBox schema consistency without validating ABox instances."""

    def __init__(self, repo: TBoxRepository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def validate_tbox(self) -> ValidationReport:
        issues: list[ValidationIssue] = []

        for class_def in self.repo.list_classes():
            issues.extend(self._validate_name("class", class_def.name, class_def.name))
            issues.extend(self._validate_class_kind(class_def))
            issues.extend(self._validate_class_property_conflicts(class_def.name))
            issues.extend(self._validate_property_bindings(
                self.repo.get_properties_of_class(class_def.name, include_interfaces=False)
            ))

        for interface_def in self.repo.list_interfaces():
            issues.extend(
                self._validate_name("interface", interface_def.name, interface_def.name)
            )
            issues.extend(
                self._validate_property_bindings(
                    self.repo.get_properties_of_interface(interface_def.name)
                )
            )

        for property_def in self.repo.list_properties():
            issues.extend(
                self._validate_name("property", property_def.name, property_def.name)
            )
            issues.extend(self._validate_property_def(property_def))

        for relationship_def in self.repo.list_relationships():
            issues.extend(self._validate_relationship_def(relationship_def))
            issues.extend(
                self._validate_property_bindings(
                    self.repo.get_properties_of_relationship(relationship_def.id)
                )
            )

        issues.extend(self._validate_relationship_semantic_duplicates())

        for constraint in self.repo.list_constraints():
            issues.extend(self._validate_constraint_def(constraint))

        return ValidationReport(tuple(issues))

    def validate_class(self, class_name: str) -> ValidationReport:
        issues: list[ValidationIssue] = []
        class_def = self.repo.get_class(class_name)
        if class_def is None:
            return ValidationReport(
                (
                    self._issue(
                        "class.not_found",
                        "error",
                        f"ClassDef not found: {class_name}",
                        "class",
                        class_name,
                    ),
                )
            )

        issues.extend(self._validate_name("class", class_def.name, class_def.name))
        issues.extend(self._validate_class_kind(class_def))
        issues.extend(self._validate_class_property_conflicts(class_name))
        issues.extend(
            self._validate_property_bindings(
                self.repo.get_properties_of_class(class_name, include_interfaces=False)
            )
        )
        for relationship in self.repo.list_relationships(from_class=class_name):
            issues.extend(self._validate_relationship_def(relationship))
        for constraint in self.repo.list_constraints(
            target_kind="class", target_id=class_name
        ):
            issues.extend(self._validate_constraint_def(constraint))
        return ValidationReport(tuple(issues))

    def validate_interface(self, interface_name: str) -> ValidationReport:
        issues: list[ValidationIssue] = []
        interface_def = self.repo.get_interface(interface_name)
        if interface_def is None:
            return ValidationReport(
                (
                    self._issue(
                        "interface.not_found",
                        "error",
                        f"InterfaceDef not found: {interface_name}",
                        "interface",
                        interface_name,
                    ),
                )
            )
        issues.extend(
            self._validate_name("interface", interface_def.name, interface_def.name)
        )
        issues.extend(
            self._validate_property_bindings(
                self.repo.get_properties_of_interface(interface_name)
            )
        )
        for constraint in self.repo.list_constraints(
            target_kind="interface", target_id=interface_name
        ):
            issues.extend(self._validate_constraint_def(constraint))
        return ValidationReport(tuple(issues))

    def validate_relationship(self, relationship_id: str) -> ValidationReport:
        relationship = self.repo.get_relationship(relationship_id)
        if relationship is None:
            return ValidationReport(
                (
                    self._issue(
                        "relationship.not_found",
                        "error",
                        f"RelationshipDef not found: {relationship_id}",
                        "relationship",
                        relationship_id,
                    ),
                )
            )
        issues = self._validate_relationship_def(relationship)
        issues.extend(
            self._validate_property_bindings(
                self.repo.get_properties_of_relationship(relationship_id)
            )
        )
        for constraint in self.repo.list_constraints(
            target_kind="relationship", target_id=relationship_id
        ):
            issues.extend(self._validate_constraint_def(constraint))
        return ValidationReport(tuple(issues))

    def validate_constraint(self, constraint_id: str) -> ValidationReport:
        constraint = self.repo.get_constraint(constraint_id)
        if constraint is None:
            return ValidationReport(
                (
                    self._issue(
                        "constraint.not_found",
                        "error",
                        f"ConstraintDef not found: {constraint_id}",
                        "constraint",
                        constraint_id,
                    ),
                )
            )
        return ValidationReport(tuple(self._validate_constraint_def(constraint)))

    def get_effective_class_schema(self, class_name: str) -> EffectiveClassSchema:
        class_def = self.repo.get_class(class_name)
        if class_def is None:
            raise TBoxNotFoundError(f"ClassDef not found: {class_name}")
        return EffectiveClassSchema(
            class_def=class_def,
            interfaces=tuple(self.repo.get_interfaces_of_class(class_name)),
            properties=tuple(self.repo.get_properties_of_class(class_name)),
            outgoing_relationships=tuple(
                self.repo.list_relationships(from_class=class_name)
            ),
            incoming_relationships=tuple(self.repo.list_relationships(to_class=class_name)),
            constraints=tuple(
                self.repo.list_constraints(target_kind="class", target_id=class_name)
            ),
        )

    def get_effective_relationship_schema(
        self, relationship_id: str
    ) -> EffectiveRelationshipSchema:
        relationship_def = self.repo.get_relationship(relationship_id)
        if relationship_def is None:
            raise TBoxNotFoundError(f"RelationshipDef not found: {relationship_id}")
        return EffectiveRelationshipSchema(
            relationship_def=relationship_def,
            properties=tuple(self.repo.get_properties_of_relationship(relationship_id)),
            constraints=tuple(
                self.repo.list_constraints(
                    target_kind="relationship", target_id=relationship_id
                )
            ),
        )

    # ------------------------------------------------------------------
    # validation internals
    # ------------------------------------------------------------------
    @staticmethod
    def _issue(
        code: str,
        severity: str,
        message: str,
        target_kind: str,
        target_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationIssue:
        return ValidationIssue(
            code=code,
            severity=severity,  # type: ignore[arg-type]
            message=message,
            target_kind=target_kind,  # type: ignore[arg-type]
            target_id=target_id,
            metadata=dict(metadata or {}),
        )

    def _validate_name(
        self, target_kind: str, target_id: str, name: str
    ) -> list[ValidationIssue]:
        if NAME_RE.match(name):
            return []
        return [
            self._issue(
                f"{target_kind}.invalid_name",
                "error",
                f"Invalid {target_kind} name: {name}",
                target_kind,
                target_id,
                {"name": name, "pattern": NAME_RE.pattern},
            )
        ]

    def _validate_class_kind(self, class_def: ClassDef) -> list[ValidationIssue]:
        if class_def.kind in ALLOWED_CLASS_KINDS:
            return []
        return [
            self._issue(
                "class.invalid_kind",
                "error",
                f"Invalid ClassDef.kind: {class_def.kind}",
                "class",
                class_def.name,
                {"kind": class_def.kind, "allowed": sorted(ALLOWED_CLASS_KINDS)},
            )
        ]

    def _validate_property_def(self, property_def: PropertyDef) -> list[ValidationIssue]:
        datatype = property_def.datatype
        if datatype in SUPPORTED_DATATYPES:
            return []
        return [
            self._issue(
                "property.unsupported_datatype",
                "error",
                f"Unsupported datatype for property {property_def.name}: {datatype}",
                "property",
                property_def.name,
                {"datatype": datatype},
            )
        ]

    def _validate_property_bindings(
        self, properties: list[EffectivePropertyDef]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for effective in properties:
            binding = effective.binding
            target_id = f"{binding.owner_kind}:{binding.owner_id}.{binding.property_name}"
            for field_name in ("required", "unique", "nullable"):
                if not isinstance(getattr(binding, field_name), bool):
                    issues.append(
                        self._issue(
                            "property_binding.invalid_flag",
                            "error",
                            f"Property binding flag must be bool: {field_name}",
                            "edge",
                            target_id,
                            {"field": field_name},
                        )
                    )
            if not self._default_matches_datatype(
                binding.default, effective.property.datatype
            ):
                issues.append(
                    self._issue(
                        "property_binding.default_type_mismatch",
                        "error",
                        "Default value is incompatible with property datatype",
                        "edge",
                        target_id,
                        {
                            "default": binding.default,
                            "datatype": effective.property.datatype,
                        },
                    )
                )
        return issues

    @staticmethod
    def _default_matches_datatype(default: Any | None, datatype: str) -> bool:
        if default is None:
            return True
        if datatype in {"unknown", "any", "json", "uuid", "date", "datetime"}:
            return True
        if datatype in {"string", "str"}:
            return isinstance(default, str)
        if datatype in {"integer", "int"}:
            return isinstance(default, int) and not isinstance(default, bool)
        if datatype in {"float", "number"}:
            return isinstance(default, (int, float)) and not isinstance(default, bool)
        if datatype in {"boolean", "bool"}:
            return isinstance(default, bool)
        if datatype in {"object"}:
            return isinstance(default, dict)
        if datatype in {"array", "list"}:
            return isinstance(default, (list, tuple))
        return True

    def _validate_class_property_conflicts(self, class_name: str) -> list[ValidationIssue]:
        sources: list[EffectivePropertyDef] = []
        for interface_def in self.repo.get_interfaces_of_class(class_name):
            sources.extend(self.repo.get_properties_of_interface(interface_def.name))
        sources.extend(
            self.repo.get_properties_of_class(class_name, include_interfaces=False)
        )

        grouped: dict[str, list[PropertyBinding]] = {}
        for source in sources:
            grouped.setdefault(source.property.name, []).append(source.binding)

        issues: list[ValidationIssue] = []
        for property_name, bindings in grouped.items():
            defaults = [binding.default for binding in bindings if binding.default is not None]
            distinct_defaults: list[Any] = []
            for default in defaults:
                if not any(default == existing for existing in distinct_defaults):
                    distinct_defaults.append(default)
            if len(distinct_defaults) > 1:
                issues.append(
                    self._issue(
                        "class.property_default_conflict",
                        "error",
                        "Multiple property bindings provide conflicting defaults",
                        "class",
                        class_name,
                        {
                            "property_name": property_name,
                            "defaults": distinct_defaults,
                        },
                    )
                )
        return issues

    def _validate_relationship_def(
        self, relationship: RelationshipDef
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        issues.extend(
            self._validate_name("relationship", relationship.id, relationship.name)
        )
        if self.repo.get_class(relationship.from_class) is None:
            issues.append(
                self._issue(
                    "relationship.from_class_not_found",
                    "error",
                    f"FROM_CLASS target not found: {relationship.from_class}",
                    "relationship",
                    relationship.id,
                    {"from_class": relationship.from_class},
                )
            )
        if self.repo.get_class(relationship.to_class) is None:
            issues.append(
                self._issue(
                    "relationship.to_class_not_found",
                    "error",
                    f"TO_CLASS target not found: {relationship.to_class}",
                    "relationship",
                    relationship.id,
                    {"to_class": relationship.to_class},
                )
            )
        if relationship.min_count < 0:
            issues.append(
                self._issue(
                    "relationship.min_count_negative",
                    "error",
                    "FROM_CLASS.minCount must be >= 0",
                    "relationship",
                    relationship.id,
                    {"min_count": relationship.min_count},
                )
            )
        if relationship.max_count is not None and relationship.max_count < relationship.min_count:
            issues.append(
                self._issue(
                    "relationship.max_count_less_than_min_count",
                    "error",
                    "FROM_CLASS.maxCount must be >= FROM_CLASS.minCount",
                    "relationship",
                    relationship.id,
                    {
                        "min_count": relationship.min_count,
                        "max_count": relationship.max_count,
                    },
                )
            )
        if relationship.required and relationship.min_count < 1:
            issues.append(
                self._issue(
                    "relationship.required_without_min_count",
                    "error",
                    "FROM_CLASS.required=True requires FROM_CLASS.minCount >= 1",
                    "relationship",
                    relationship.id,
                    {"min_count": relationship.min_count},
                )
            )
        return issues

    def _validate_relationship_semantic_duplicates(self) -> list[ValidationIssue]:
        grouped: dict[tuple[str, str, str], list[RelationshipDef]] = {}
        for relationship in self.repo.list_relationships():
            key = (relationship.from_class, relationship.name, relationship.to_class)
            grouped.setdefault(key, []).append(relationship)

        issues: list[ValidationIssue] = []
        for semantic_key, relationships in grouped.items():
            if len(relationships) <= 1:
                continue
            issues.append(
                self._issue(
                    "relationship.semantic_duplicate",
                    "error",
                    "Duplicate relationship semantic key",
                    "relationship",
                    relationships[0].id,
                    {
                        "semantic_key": semantic_key,
                        "relationship_ids": [r.id for r in relationships],
                    },
                )
            )
        return issues

    def _validate_constraint_def(self, constraint: ConstraintDef) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if constraint.severity not in {"info", "warning", "error"}:
            issues.append(
                self._issue(
                    "constraint.invalid_severity",
                    "error",
                    f"Invalid constraint severity: {constraint.severity}",
                    "constraint",
                    constraint.id,
                    {"severity": constraint.severity},
                )
            )

        if not self._target_exists(constraint.target_kind, constraint.target_id):
            issues.append(
                self._issue(
                    "constraint.target_not_found",
                    "error",
                    "Constraint target does not exist",
                    "constraint",
                    constraint.id,
                    {
                        "target_kind": constraint.target_kind,
                        "target_id": constraint.target_id,
                    },
                )
            )
            return issues

        available = self._effective_property_names(
            constraint.target_kind, constraint.target_id
        )
        if constraint.target_kind == "property" and constraint.property_names:
            issues.append(
                self._issue(
                    "constraint.property_names_not_applicable",
                    "error",
                    "property_names cannot target a PropertyDef constraint",
                    "constraint",
                    constraint.id,
                    {"property_names": constraint.property_names},
                )
            )
        for property_name in constraint.property_names:
            if property_name not in available:
                issues.append(
                    self._issue(
                        "constraint.property_not_found",
                        "error",
                        "Constraint property name is not in target effective properties",
                        "constraint",
                        constraint.id,
                        {
                            "property_name": property_name,
                            "target_kind": constraint.target_kind,
                            "target_id": constraint.target_id,
                        },
                    )
                )

        if constraint.kind in {"regex", "range", "expression"} and not constraint.expression:
            issues.append(
                self._issue(
                    "constraint.expression_required",
                    "error",
                    f"Constraint kind requires expression: {constraint.kind}",
                    "constraint",
                    constraint.id,
                    {"kind": constraint.kind},
                )
            )
        return issues

    def _target_exists(self, target_kind: str, target_id: str) -> bool:
        if target_kind == "class":
            return self.repo.get_class(target_id) is not None
        if target_kind == "interface":
            return self.repo.get_interface(target_id) is not None
        if target_kind == "property":
            return self.repo.get_property(target_id) is not None
        if target_kind == "relationship":
            return self.repo.get_relationship(target_id) is not None
        return False

    def _effective_property_names(self, target_kind: str, target_id: str) -> set[str]:
        if target_kind == "class":
            return {
                effective.property.name
                for effective in self.repo.get_properties_of_class(target_id)
            }
        if target_kind == "interface":
            return {
                effective.property.name
                for effective in self.repo.get_properties_of_interface(target_id)
            }
        if target_kind == "relationship":
            return {
                effective.property.name
                for effective in self.repo.get_properties_of_relationship(target_id)
            }
        if target_kind == "property":
            property_def = self.repo.get_property(target_id)
            return {property_def.name} if property_def is not None else set()
        return set()
