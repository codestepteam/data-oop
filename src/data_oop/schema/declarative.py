"""Declarative TBox schema: author the schema as a YAML/JSON file, then plan/apply
it against a repository — the terraform pattern for ontology evolution.

The file is the source of truth: it lives in git, so schema history, review, and
rollback come from version control instead of ad-hoc graph mutations. ``plan_schema``
computes a diff (create / update / unchanged / delete) without touching anything;
``apply_schema`` executes it. With a ``graph`` handle, the plan also estimates ABox
impact — e.g. how many existing instances would violate a newly required property —
so a breaking schema change is visible before it lands.

File format (YAML)::

    interfaces:
      Named:
        description: Has a display name
        properties:
          name: {datatype: string, required: true}

    classes:
      Agent: {}
      Person:
        parents: [Agent]          # SUBCLASS_OF (or singular `parent: Agent`)
        implements: [Named]
        properties:
          age: {datatype: integer}

    relationships:
      WORKS_FOR:
        from: Person
        to: Organization
        max_count: 1
        properties:
          since: {datatype: date}

    constraints:
      person_age_range:
        kind: range
        target_kind: class
        target_id: Person
        properties: [age]
        expression: "0..150"
        severity: error

Property entries accept ``datatype / required / unique / nullable / default /
description``. A relationship key is its semantic name; ``id`` may override the
auto-generated ``rel_{from}_{NAME}_{to}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from data_oop.schema.repository import TBoxRepository

ActionKind = Literal["create", "update", "delete", "unchanged"]


@dataclass(frozen=True)
class PropertySpec:
    name: str
    datatype: str = "string"
    required: bool = False
    unique: bool = False
    nullable: bool = True
    default: Any | None = None
    description: str | None = None


@dataclass(frozen=True)
class InterfaceSpec:
    name: str
    description: str | None = None
    properties: tuple[PropertySpec, ...] = ()


@dataclass(frozen=True)
class ClassSpec:
    name: str
    label: str | None = None
    description: str | None = None
    parents: tuple[str, ...] = ()
    implements: tuple[str, ...] = ()
    properties: tuple[PropertySpec, ...] = ()


@dataclass(frozen=True)
class RelationshipSpec:
    name: str
    from_class: str
    to_class: str
    id: str | None = None
    min_count: int = 0
    max_count: int | None = None
    required: bool = False
    description: str | None = None
    properties: tuple[PropertySpec, ...] = ()

    @property
    def effective_id(self) -> str:
        return self.id or f"rel_{self.from_class}_{self.name}_{self.to_class}"


@dataclass(frozen=True)
class ConstraintSpec:
    id: str
    kind: str
    target_kind: Literal["class", "interface", "property", "relationship"]
    target_id: str
    property_names: tuple[str, ...] = ()
    expression: str | None = None
    severity: Literal["info", "warning", "error"] = "error"
    description: str | None = None


@dataclass(frozen=True)
class SchemaSpec:
    interfaces: tuple[InterfaceSpec, ...] = ()
    classes: tuple[ClassSpec, ...] = ()
    relationships: tuple[RelationshipSpec, ...] = ()
    constraints: tuple[ConstraintSpec, ...] = ()


@dataclass(frozen=True)
class PlanAction:
    kind: ActionKind
    entity: str  # "property" | "interface" | "class" | "binding" | "subclass" | ...
    target: str
    detail: str = ""
    # Estimated number of existing ABox instances that would violate this change
    # (None = not estimated; requires a graph handle at plan time).
    abox_impact: int | None = None


@dataclass(frozen=True)
class SchemaPlan:
    actions: tuple[PlanAction, ...] = ()

    def changes(self) -> list[PlanAction]:
        return [a for a in self.actions if a.kind != "unchanged"]

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for action in self.actions:
            counts[action.kind] = counts.get(action.kind, 0) + 1
        parts = [f"{counts.get(k, 0)} {k}" for k in ("create", "update", "delete", "unchanged")]
        return ", ".join(parts)

    def render(self) -> str:
        symbol = {"create": "+", "update": "~", "delete": "-", "unchanged": " "}
        lines = []
        for action in self.actions:
            if action.kind == "unchanged":
                continue
            line = f"{symbol[action.kind]} {action.entity} {action.target}"
            if action.detail:
                line += f"  ({action.detail})"
            if action.abox_impact:
                line += f"  [!] {action.abox_impact} existing instance(s) would violate"
            lines.append(line)
        lines.append(f"Plan: {self.summary()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_schema_file(path: str | Path) -> SchemaSpec:
    """Parse a YAML (or JSON — YAML is a superset) schema file into a SchemaSpec."""
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Schema file must be a mapping, got {type(raw).__name__}")
    return parse_schema_spec(raw)


def parse_schema_spec(raw: dict[str, Any]) -> SchemaSpec:
    known = {"interfaces", "classes", "relationships", "constraints"}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"Unknown top-level schema keys: {sorted(unknown)}")

    interfaces = tuple(
        InterfaceSpec(
            name=name,
            description=body.get("description"),
            properties=_parse_properties(body.get("properties")),
        )
        for name, body in _items(raw.get("interfaces"))
    )
    classes = tuple(
        ClassSpec(
            name=name,
            label=body.get("label"),
            description=body.get("description"),
            parents=_parents(body),
            implements=tuple(body.get("implements") or ()),
            properties=_parse_properties(body.get("properties")),
        )
        for name, body in _items(raw.get("classes"))
    )
    relationships = tuple(
        RelationshipSpec(
            name=name,
            from_class=_required_key(body, "from", f"relationships.{name}"),
            to_class=_required_key(body, "to", f"relationships.{name}"),
            id=body.get("id"),
            min_count=int(body.get("min_count", 0)),
            max_count=None if body.get("max_count") is None else int(body["max_count"]),
            required=bool(body.get("required", False)),
            description=body.get("description"),
            properties=_parse_properties(body.get("properties")),
        )
        for name, body in _items(raw.get("relationships"))
    )
    constraints = tuple(
        ConstraintSpec(
            id=cid,
            kind=_required_key(body, "kind", f"constraints.{cid}"),
            target_kind=_required_key(body, "target_kind", f"constraints.{cid}"),
            target_id=_required_key(body, "target_id", f"constraints.{cid}"),
            property_names=tuple(body.get("properties") or ()),
            expression=body.get("expression"),
            severity=body.get("severity", "error"),
            description=body.get("description"),
        )
        for cid, body in _items(raw.get("constraints"))
    )
    return SchemaSpec(
        interfaces=interfaces,
        classes=classes,
        relationships=relationships,
        constraints=constraints,
    )


def _items(section: Any) -> list[tuple[str, dict[str, Any]]]:
    if section is None:
        return []
    if not isinstance(section, dict):
        raise ValueError(f"Schema section must be a mapping, got {type(section).__name__}")
    out = []
    for name, body in section.items():
        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise ValueError(f"Entry {name!r} must be a mapping, got {type(body).__name__}")
        out.append((str(name), body))
    return out


def _parents(body: dict[str, Any]) -> tuple[str, ...]:
    parents = body.get("parents")
    parent = body.get("parent")
    if parents and parent:
        raise ValueError("Use either `parent` or `parents`, not both")
    if parent:
        return (str(parent),)
    return tuple(parents or ())


def _required_key(body: dict[str, Any], key: str, where: str) -> Any:
    if key not in body:
        raise ValueError(f"{where}: missing required key {key!r}")
    return body[key]


def _parse_properties(section: Any) -> tuple[PropertySpec, ...]:
    return tuple(
        PropertySpec(
            name=name,
            datatype=body.get("datatype", "string"),
            required=bool(body.get("required", False)),
            unique=bool(body.get("unique", False)),
            nullable=bool(body.get("nullable", True)),
            default=body.get("default"),
            description=body.get("description"),
        )
        for name, body in _items(section)
    )


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def plan_schema(
    repo: TBoxRepository,
    spec: SchemaSpec,
    *,
    prune: bool = False,
    graph: Any | None = None,
) -> SchemaPlan:
    """Diff ``spec`` against the repository without applying anything.

    With ``prune=True`` entities present in the repo but absent from the spec are
    marked for deletion. With a ``graph`` handle, newly-required property bindings get
    an ABox impact estimate (count of existing instances that would violate).
    """
    actions: list[PlanAction] = []

    # Properties (shared pool): collect every PropertySpec by name across owners.
    for prop in _all_property_specs(spec):
        existing = repo.get_property(prop.name)
        if existing is None:
            actions.append(PlanAction("create", "property", prop.name, f"datatype={prop.datatype}"))
        elif existing.datatype != prop.datatype:
            actions.append(
                PlanAction(
                    "update", "property", prop.name,
                    f"datatype {existing.datatype} -> {prop.datatype}",
                )
            )
        else:
            actions.append(PlanAction("unchanged", "property", prop.name))

    for iface in spec.interfaces:
        if repo.get_interface(iface.name) is None:
            actions.append(PlanAction("create", "interface", iface.name))
        else:
            actions.append(PlanAction("unchanged", "interface", iface.name))
        actions.extend(
            _plan_bindings(repo, "interface", iface.name, iface.properties, graph=None)
        )

    for cls in spec.classes:
        existing_class = repo.get_class(cls.name)
        if existing_class is None:
            actions.append(PlanAction("create", "class", cls.name))
        else:
            actions.append(PlanAction("unchanged", "class", cls.name))

        current_parents = (
            {c.name for c in repo.get_superclasses(cls.name, transitive=False)}
            if existing_class is not None
            else set()
        )
        for parent in cls.parents:
            if parent not in current_parents:
                actions.append(PlanAction("create", "subclass", f"{cls.name} -> {parent}"))
            else:
                actions.append(PlanAction("unchanged", "subclass", f"{cls.name} -> {parent}"))
        if prune:
            for parent in sorted(current_parents - set(cls.parents)):
                actions.append(PlanAction("delete", "subclass", f"{cls.name} -> {parent}"))

        current_ifaces = (
            {i.name for i in repo.get_interfaces_of_class(cls.name)}
            if existing_class is not None
            else set()
        )
        for iface_name in cls.implements:
            if iface_name not in current_ifaces:
                actions.append(PlanAction("create", "implements", f"{cls.name} -> {iface_name}"))
            else:
                actions.append(PlanAction("unchanged", "implements", f"{cls.name} -> {iface_name}"))
        if prune:
            for iface_name in sorted(current_ifaces - set(cls.implements)):
                actions.append(PlanAction("delete", "implements", f"{cls.name} -> {iface_name}"))

        actions.extend(
            _plan_bindings(repo, "class", cls.name, cls.properties, graph=graph)
        )

    for rel in spec.relationships:
        existing_rel = repo.get_relationship(rel.effective_id)
        target = f"{rel.effective_id} ({rel.from_class})-[:{rel.name}]->({rel.to_class})"
        if existing_rel is None:
            actions.append(PlanAction("create", "relationship", target))
        elif (
            existing_rel.min_count != rel.min_count
            or existing_rel.max_count != rel.max_count
            or existing_rel.required != rel.required
        ):
            actions.append(
                PlanAction(
                    "update", "relationship", target,
                    f"cardinality {existing_rel.min_count}..{existing_rel.max_count}"
                    f" -> {rel.min_count}..{rel.max_count}",
                )
            )
        else:
            actions.append(PlanAction("unchanged", "relationship", target))
        actions.extend(
            _plan_bindings(repo, "relationship", rel.effective_id, rel.properties, graph=None)
        )

    for constraint in spec.constraints:
        existing_constraint = repo.get_constraint(constraint.id)
        if existing_constraint is None:
            actions.append(
                PlanAction("create", "constraint", constraint.id, f"kind={constraint.kind}")
            )
        elif (
            existing_constraint.kind != constraint.kind
            or existing_constraint.target_kind != constraint.target_kind
            or existing_constraint.target_id != constraint.target_id
            or existing_constraint.property_names != constraint.property_names
            or existing_constraint.expression != constraint.expression
            or existing_constraint.severity != constraint.severity
        ):
            actions.append(PlanAction("update", "constraint", constraint.id))
        else:
            actions.append(PlanAction("unchanged", "constraint", constraint.id))

    if prune:
        actions.extend(_plan_prune(repo, spec))

    return SchemaPlan(tuple(actions))


def _all_property_specs(spec: SchemaSpec) -> list[PropertySpec]:
    seen: dict[str, PropertySpec] = {}
    owners = (
        [(i.properties) for i in spec.interfaces]
        + [(c.properties) for c in spec.classes]
        + [(r.properties) for r in spec.relationships]
    )
    for props in owners:
        for prop in props:
            existing = seen.get(prop.name)
            if existing is not None and existing.datatype != prop.datatype:
                raise ValueError(
                    f"Property {prop.name!r} declared with conflicting datatypes: "
                    f"{existing.datatype!r} vs {prop.datatype!r}"
                )
            seen.setdefault(prop.name, prop)
    return list(seen.values())


def _plan_bindings(
    repo: TBoxRepository,
    owner_kind: Literal["class", "interface", "relationship"],
    owner_id: str,
    props: tuple[PropertySpec, ...],
    *,
    graph: Any | None,
) -> list[PlanAction]:
    current: dict[str, Any] = {}
    try:
        if owner_kind == "class":
            effective = repo.get_properties_of_class(owner_id, include_interfaces=False)
        elif owner_kind == "interface":
            effective = repo.get_properties_of_interface(owner_id)
        else:
            effective = repo.get_properties_of_relationship(owner_id)
        current = {e.property.name: e.binding for e in effective}
    except Exception:
        current = {}  # owner does not exist yet — every binding is a create

    actions: list[PlanAction] = []
    for prop in props:
        target = f"{owner_id}.{prop.name}"
        binding = current.get(prop.name)
        if binding is None:
            detail = "required" if prop.required else ""
            impact = None
            if prop.required and owner_kind == "class" and graph is not None:
                impact = _count_missing(graph, owner_id, prop.name)
            actions.append(PlanAction("create", "binding", target, detail, abox_impact=impact))
        elif (
            binding.required != prop.required
            or binding.unique != prop.unique
            or binding.nullable != prop.nullable
            or binding.default != prop.default
        ):
            impact = None
            if prop.required and not binding.required and owner_kind == "class" and graph is not None:
                impact = _count_missing(graph, owner_id, prop.name)
            actions.append(
                PlanAction(
                    "update", "binding", target,
                    f"required={prop.required} unique={prop.unique}",
                    abox_impact=impact,
                )
            )
        else:
            actions.append(PlanAction("unchanged", "binding", target))
    return actions


def _count_missing(graph: Any, class_name: str, property_name: str) -> int | None:
    from data_oop.schema.validator import NAME_RE

    if not NAME_RE.match(class_name) or not NAME_RE.match(property_name):
        return None
    try:
        rows = graph.query(
            f"MATCH (n:{class_name}) WHERE n.{property_name} IS NULL RETURN count(n)"
        ).result_set
        return int(rows[0][0]) if rows and rows[0] else 0
    except Exception:
        return None


def _plan_prune(repo: TBoxRepository, spec: SchemaSpec) -> list[PlanAction]:
    actions: list[PlanAction] = []
    spec_classes = {c.name for c in spec.classes}
    spec_interfaces = {i.name for i in spec.interfaces}
    spec_rel_ids = {r.effective_id for r in spec.relationships}
    spec_constraints = {c.id for c in spec.constraints}

    for constraint in repo.list_constraints():
        if constraint.id not in spec_constraints:
            actions.append(PlanAction("delete", "constraint", constraint.id))
    for rel in repo.list_relationships():
        if rel.id not in spec_rel_ids:
            actions.append(PlanAction("delete", "relationship", rel.id))
    for cls in repo.list_classes():
        if cls.name not in spec_classes:
            actions.append(PlanAction("delete", "class", cls.name))
    for iface in repo.list_interfaces():
        if iface.name not in spec_interfaces:
            actions.append(PlanAction("delete", "interface", iface.name))
    return actions


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyResult:
    plan: SchemaPlan
    applied: bool
    errors: tuple[str, ...] = ()


def apply_schema(
    repo: TBoxRepository,
    spec: SchemaSpec,
    *,
    prune: bool = False,
    dry_run: bool = False,
    graph: Any | None = None,
) -> ApplyResult:
    """Apply ``spec`` to the repository (idempotent — every entity upserts).

    ``dry_run=True`` returns the plan without writing. Order: properties →
    interfaces → interface bindings → classes → subclass edges → implements →
    class bindings → relationships → relationship bindings → constraints; prune
    deletions run last in reverse dependency order.
    """
    plan = plan_schema(repo, spec, prune=prune, graph=graph)
    if dry_run:
        return ApplyResult(plan=plan, applied=False)

    for prop in _all_property_specs(spec):
        repo.create_property(
            prop.name, datatype=prop.datatype, description=prop.description
        )

    for iface in spec.interfaces:
        repo.create_interface(iface.name, description=iface.description)
        for prop in iface.properties:
            repo.attach_property_to_interface(
                interface_name=iface.name,
                property_name=prop.name,
                required=prop.required,
                unique=prop.unique,
                nullable=prop.nullable,
                default=prop.default,
            )

    for cls in spec.classes:
        repo.create_class(cls.name, label=cls.label, description=cls.description)

    # Subclass/implements edges after all classes exist (forward references in file).
    for cls in spec.classes:
        current_parents = {c.name for c in repo.get_superclasses(cls.name, transitive=False)}
        for parent in cls.parents:
            if parent not in current_parents:
                repo.set_subclass_of(class_name=cls.name, parent_name=parent)
        if prune:
            for parent in current_parents - set(cls.parents):
                repo.remove_subclass_of(class_name=cls.name, parent_name=parent)

        current_ifaces = {i.name for i in repo.get_interfaces_of_class(cls.name)}
        for iface_name in cls.implements:
            if iface_name not in current_ifaces:
                repo.implement_interface(class_name=cls.name, interface_name=iface_name)
        if prune:
            for iface_name in current_ifaces - set(cls.implements):
                repo.remove_interface(class_name=cls.name, interface_name=iface_name)

        for prop in cls.properties:
            repo.attach_property_to_class(
                class_name=cls.name,
                property_name=prop.name,
                required=prop.required,
                unique=prop.unique,
                nullable=prop.nullable,
                default=prop.default,
            )

    for rel in spec.relationships:
        repo.define_relationship(
            id=rel.effective_id,
            name=rel.name,
            from_class=rel.from_class,
            to_class=rel.to_class,
            min_count=rel.min_count,
            max_count=rel.max_count,
            required=rel.required,
            description=rel.description,
        )
        for prop in rel.properties:
            repo.attach_property_to_relationship(
                relationship_id=rel.effective_id,
                property_name=prop.name,
                required=prop.required,
                unique=prop.unique,
                nullable=prop.nullable,
                default=prop.default,
            )

    for constraint in spec.constraints:
        repo.create_constraint(
            id=constraint.id,
            kind=constraint.kind,
            target_kind=constraint.target_kind,
            target_id=constraint.target_id,
            property_names=constraint.property_names,
            expression=constraint.expression,
            severity=constraint.severity,
            description=constraint.description,
        )

    errors: list[str] = []
    if prune:
        for action in plan.actions:
            if action.kind != "delete":
                continue
            try:
                if action.entity == "constraint":
                    repo.delete_constraint(action.target)
                elif action.entity == "relationship":
                    repo.delete_relationship(action.target, detach=True)
                elif action.entity == "class":
                    repo.delete_class(action.target, detach=True)
                elif action.entity == "interface":
                    repo.delete_interface(action.target, detach=True)
                # subclass/implements prune already handled inline above
            except Exception as exc:  # surface, don't abort remaining prunes
                errors.append(f"prune {action.entity} {action.target}: {exc}")

    return ApplyResult(plan=plan, applied=True, errors=tuple(errors))
