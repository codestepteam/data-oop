"""Single source of truth for collapsing property sources into effective properties.

Both repositories (live FalkorDB and in-memory) build the same kind of source list — a
class's own bindings plus the bindings inherited from the interfaces it implements — and
then merge same-named entries with identical precedence rules. That merge lived in three
near-identical copies; this module is the one canonical implementation the repositories
share. (The validator keeps its own narrower projection: it only needs name/datatype/
required/unique, not the full EffectivePropertyDef.)
"""

from __future__ import annotations

from typing import Any

from data_oop.schema.models import EffectivePropertyDef, OwnerKind, PropertyBinding


def merge_effective_properties(
    owner_kind: OwnerKind,
    owner_id: str,
    sources: list[EffectivePropertyDef],
) -> list[EffectivePropertyDef]:
    """Collapse property ``sources`` (own + inherited) into one effective entry per name.

    For a name backed by several sources: ``required``/``unique`` are OR'd, ``nullable`` is
    AND'd, ``default`` takes the first non-null, and ``metadata`` is shallow-merged. The
    surviving property/source prefers the one whose ``source_kind`` matches ``owner_kind``,
    so a direct binding overrides an inherited one. Single-source names pass through
    unchanged. The result is sorted by property name.
    """
    grouped: dict[str, list[EffectivePropertyDef]] = {}
    for source in sources:
        grouped.setdefault(source.property.name, []).append(source)

    merged: list[EffectivePropertyDef] = []
    for property_name in sorted(grouped):
        values = grouped[property_name]
        if len(values) == 1:
            merged.append(values[0])
            continue

        defaults = [value.binding.default for value in values if value.binding.default is not None]
        default = defaults[0] if defaults else None
        metadata: dict[str, Any] = {}
        for value in values:
            metadata.update(value.binding.metadata)

        binding = PropertyBinding(
            owner_kind=owner_kind,
            owner_id=owner_id,
            property_name=property_name,
            required=any(value.binding.required for value in values),
            unique=any(value.binding.unique for value in values),
            nullable=all(value.binding.nullable for value in values),
            default=default,
            metadata=metadata,
        )
        direct_source = next(
            (value for value in values if value.source_kind == owner_kind), None
        )
        source = direct_source or values[0]
        merged.append(
            EffectivePropertyDef(
                property=source.property,
                binding=binding,
                source_kind=source.source_kind,
                source_id=source.source_id,
            )
        )
    return merged
