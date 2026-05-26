from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

OwnerKind = Literal["class", "interface", "relationship"]
TargetKind = Literal["class", "interface", "property", "relationship"]
Severity = Literal["info", "warning", "error"]
ValidationTargetKind = Literal[
    "class", "interface", "property", "relationship", "constraint", "edge"
]


@dataclass(frozen=True)
class ClassDef:
    name: str
    label: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterfaceDef:
    name: str
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyDef:
    name: str
    datatype: str = "unknown"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PropertyBinding:
    owner_kind: OwnerKind
    owner_id: str
    property_name: str
    required: bool = False
    unique: bool = False
    nullable: bool = True
    default: Any | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectivePropertyDef:
    property: PropertyDef
    binding: PropertyBinding
    source_kind: OwnerKind
    source_id: str


@dataclass(frozen=True)
class RelationshipDef:
    id: str
    name: str
    from_class: str
    to_class: str
    min_count: int = 0
    max_count: int | None = None
    required: bool = False
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintDef:
    id: str
    kind: str
    target_kind: TargetKind
    target_id: str
    property_names: tuple[str, ...] = ()
    expression: str | None = None
    severity: Severity = "error"
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectiveClassSchema:
    class_def: ClassDef
    interfaces: tuple[InterfaceDef, ...]
    properties: tuple[EffectivePropertyDef, ...]
    outgoing_relationships: tuple[RelationshipDef, ...]
    incoming_relationships: tuple[RelationshipDef, ...]
    constraints: tuple[ConstraintDef, ...]


@dataclass(frozen=True)
class EffectiveRelationshipSchema:
    relationship_def: RelationshipDef
    properties: tuple[EffectivePropertyDef, ...]
    constraints: tuple[ConstraintDef, ...]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    target_kind: ValidationTargetKind
    target_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors()

    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def raise_if_invalid(self) -> None:
        if not self.valid:
            from .exceptions import TBoxValidationError

            raise TBoxValidationError(self)


WorkflowAction = Literal["create_node", "create_relationship", "run_workflow"]
WorkflowParameterType = Literal[
    "string", "integer", "float", "boolean", "date", "datetime", "email", "url", "phone", "uuid", "array"
]


@dataclass(frozen=True)
class WorkflowParameterDef:
    name: str
    type: WorkflowParameterType
    array_item_type: str | None = None
    array_item_class: str | None = None
    required: bool = True
    description: str | None = None


@dataclass(frozen=True)
class WorkflowStepDef:
    step_id: str
    action: WorkflowAction
    class_name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    uuid: str | None = None
    from_class: str | None = None
    from_uuid: str | None = None
    relationship_name: str | None = None
    to_class: str | None = None
    to_uuid: str | None = None
    if_present: str | None = None
    loop_over: str | None = None
    loop_var: str | None = None
    workflow_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDef:
    name: str
    steps: tuple[WorkflowStepDef, ...]
    parameters: tuple[WorkflowParameterDef, ...] = ()
    description: str | None = None
    uuid: str | None = None
