from __future__ import annotations

from data_oop.falkor._repo_classes import _ClassMixin
from data_oop.falkor._repo_interfaces import _InterfaceMixin
from data_oop.falkor._repo_properties import _PropertyMixin
from data_oop.falkor._repo_relationships import _RelationshipMixin
from data_oop.falkor._repo_constraints import _ConstraintMixin
from data_oop.falkor._repo_connectors import _ConnectorMixin
from data_oop.falkor._repo_views import _ViewMixin
from data_oop.falkor._repo_triggers import _TriggerMixin

__all__ = ["FalkorTBoxRepository"]


class FalkorTBoxRepository(
    _ClassMixin,
    _InterfaceMixin,
    _PropertyMixin,
    _RelationshipMixin,
    _ConstraintMixin,
    _ConnectorMixin,
    _ViewMixin,
    _TriggerMixin,
):
    """TBox repository implementation that queries and updates FalkorDB directly in real-time.

    This ensures FalkorDB is the Single Source of Truth (SSOT), and all DSL modifications
    are applied instantly to the live database graph.
    """

    # All behavior is composed from the per-entity mixins above, which share
    # FalkorDB access and helpers via _RepositoryBase.
