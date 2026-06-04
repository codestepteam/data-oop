"""Class-level triggers: run a stored workflow when an ABox node is created or
updated.

Two concerns live here:

1. **Static analysis** (``analyze_trigger_graph`` / ``validate_trigger_graph``) —
   triggers form a directed graph (trigger -> the triggers its workflow can fire).
   A cycle in that graph is an infinite/divergent callback loop. We detect cycles
   at registration time so a bad trigger is rejected before it can ever run. The
   analysis is a conservative over-approximation: ``if_present`` conditions and
   ``loop_over`` data are not known statically, so "no cycle" is a proof of safety
   while "cycle" is a possibility (may be a false positive). Unresolved dynamic
   ``class_name`` and ``loop_over`` fan-out are reported, not silently dropped.

2. **Runtime dispatch** (``dispatch_triggers``) — called from ``upsert_abox_node``
   after a node is merged. Depth-limited as a backstop for whatever static
   analysis cannot prove.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data_oop.schema.models import TriggerDef

# Hard cap on how deep a trigger -> workflow -> trigger chain may recurse at
# runtime. Static cycle detection prevents known loops; this guards the rest
# (conditional firing, dynamic classes, loop_over data) from runaway recursion.
MAX_TRIGGER_DEPTH = 10


# ----------------------------------------------------------------------------
# Static analysis
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class WorkflowEmission:
    """What events a workflow can emit, derived from its steps."""

    events: frozenset[tuple[str, str]]  # (class_name, event) pairs
    has_loop_fanout: bool  # a create_node sits under loop_over -> unbounded width
    has_dynamic_class: bool  # a create_node target class is a {variable} -> unknown


@dataclass
class TriggerGraphReport:
    """Result of analysing a set of triggers against the known workflows."""

    cycles: list[list[str]] = field(default_factory=list)  # each = trigger names in loop
    unbounded: list[str] = field(default_factory=list)  # triggers reaching loop_over fan-out
    unresolved: list[str] = field(default_factory=list)  # triggers reaching dynamic class_name
    missing_workflows: list[str] = field(default_factory=list)  # trigger -> unknown workflow

    @property
    def valid(self) -> bool:
        return not self.cycles


def workflow_emits(
    workflow_name: str,
    workflow_steps: dict[str, list[dict[str, Any]]],
    _seen: frozenset[str] | None = None,
) -> WorkflowEmission:
    """Compute the set of (class, event) pairs a workflow can emit.

    A ``create_node`` step emits both ``create`` and ``update`` for its class
    (a MERGE may do either). ``run_workflow`` steps are expanded recursively.
    Dynamic class names (``{var}``) and ``loop_over`` fan-out are flagged.
    """

    seen = _seen or frozenset()
    if workflow_name in seen or workflow_name not in workflow_steps:
        # Unknown or already-expanded workflow contributes nothing.
        return WorkflowEmission(frozenset(), False, False)

    seen = seen | {workflow_name}
    events: set[tuple[str, str]] = set()
    loop_fanout = False
    dynamic = False

    for step in workflow_steps[workflow_name]:
        action = step.get("action")
        if action == "create_node":
            class_name = step.get("class_name") or ""
            if "{" in class_name or not class_name:
                dynamic = True
                continue
            events.add((class_name, "create"))
            events.add((class_name, "update"))
            if step.get("loop_over"):
                loop_fanout = True
        elif action == "run_workflow":
            nested_name = step.get("workflow_name")
            if not nested_name:
                continue
            nested = workflow_emits(nested_name, workflow_steps, seen)
            events |= nested.events
            loop_fanout = loop_fanout or nested.has_loop_fanout or bool(step.get("loop_over"))
            dynamic = dynamic or nested.has_dynamic_class
        # create_relationship does not emit node triggers.

    return WorkflowEmission(frozenset(events), loop_fanout, dynamic)


def _build_adjacency(
    triggers: list[TriggerDef],
    workflow_steps: dict[str, list[dict[str, Any]]],
) -> tuple[dict[int, list[int]], list[WorkflowEmission]]:
    """Edge i -> j when trigger i's workflow can emit trigger j's (class, event)."""

    by_target: dict[tuple[str, str], list[int]] = {}
    for index, trigger in enumerate(triggers):
        by_target.setdefault((trigger.class_name, trigger.event), []).append(index)

    emissions = [workflow_emits(t.workflow_name, workflow_steps) for t in triggers]
    adjacency: dict[int, list[int]] = {i: [] for i in range(len(triggers))}
    for index, emission in enumerate(emissions):
        targets: set[int] = set()
        for pair in emission.events:
            for target_index in by_target.get(pair, ()):
                targets.add(target_index)
        adjacency[index] = sorted(targets)
    return adjacency, emissions


def _find_cycles(adjacency: dict[int, list[int]]) -> list[list[int]]:
    """Return simple cycles (as index lists) via DFS back-edge detection."""

    cycles: list[list[int]] = []
    seen_signatures: set[frozenset[int]] = set()
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in adjacency}
    stack: list[int] = []

    def visit(node: int) -> None:
        color[node] = GRAY
        stack.append(node)
        for neighbour in adjacency[node]:
            if color[neighbour] == GRAY:
                # Back-edge: extract the loop slice from the stack.
                start = stack.index(neighbour)
                cycle = stack[start:]
                signature = frozenset(cycle)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    cycles.append(cycle[:])
            elif color[neighbour] == WHITE:
                visit(neighbour)
        stack.pop()
        color[node] = BLACK

    for node in adjacency:
        if color[node] == WHITE:
            visit(node)
    return cycles


def _reachable(adjacency: dict[int, list[int]], start: int) -> set[int]:
    out: set[int] = set()
    frontier = [start]
    while frontier:
        node = frontier.pop()
        for neighbour in adjacency[node]:
            if neighbour not in out:
                out.add(neighbour)
                frontier.append(neighbour)
    return out


def analyze_trigger_graph(
    triggers: list[TriggerDef],
    workflow_steps: dict[str, list[dict[str, Any]]],
) -> TriggerGraphReport:
    """Analyse a trigger set for loops and divergence. Never raises."""

    report = TriggerGraphReport()
    if not triggers:
        return report

    for trigger in triggers:
        if trigger.workflow_name not in workflow_steps:
            report.missing_workflows.append(trigger.name)

    adjacency, emissions = _build_adjacency(triggers, workflow_steps)

    cycles = _find_cycles(adjacency)
    report.cycles = [[triggers[i].name for i in cycle] for cycle in cycles]

    # Divergence flags: a trigger is unbounded/unresolved if its own workflow or
    # anything it can reach has loop_over fan-out / a dynamic class target.
    for index, trigger in enumerate(triggers):
        chain = {index} | _reachable(adjacency, index)
        if any(emissions[i].has_loop_fanout for i in chain):
            report.unbounded.append(trigger.name)
        if any(emissions[i].has_dynamic_class for i in chain):
            report.unresolved.append(trigger.name)

    return report


def validate_trigger_graph(
    triggers: list[TriggerDef],
    workflow_steps: dict[str, list[dict[str, Any]]],
) -> TriggerGraphReport:
    """Analyse and raise ``TriggerCycleError`` if a cycle exists. Returns the
    report otherwise (callers may inspect ``unbounded`` / ``unresolved``)."""

    report = analyze_trigger_graph(triggers, workflow_steps)
    if report.cycles:
        from data_oop.exceptions import TriggerCycleError

        raise TriggerCycleError(report.cycles)
    return report


# ----------------------------------------------------------------------------
# Runtime dispatch
# ----------------------------------------------------------------------------
def _fetch_node_props(graph: Any, class_name: str, uuid: Any) -> dict[str, Any] | None:
    """Read the full current property map of an ABox node."""
    if not uuid:
        return None
    from data_oop.falkor.abox import _safe_identifier

    label = _safe_identifier(class_name, "class")
    rows = graph.query(
        f"MATCH (n:{label} {{uuid: $uuid}}) RETURN properties(n)", {"uuid": uuid}
    ).result_set
    if rows and rows[0] and rows[0][0]:
        return dict(rows[0][0])
    return None


def dispatch_triggers(
    *,
    graph: Any,
    class_name: str,
    event: str,
    node: dict[str, Any],
    depth: int,
) -> list[dict[str, Any]]:
    """Run every enabled trigger registered for ``(class_name, event)``.

    The trigger's workflow parameters are determined as follows:

    * The **full current node state** is read from the graph (not just the upsert
      delta) and used as the interpolation context.
    * If the trigger has a ``parameter_map``, each entry ``param -> template`` is
      interpolated against the node to build the workflow parameters — this is the
      explicit "which param gets which value" binding.
    * If ``parameter_map`` is empty, the node's properties are passed through flat.

    Each workflow runs one level deeper so the global depth cap bounds any chain
    static analysis missed.

    Returns the per-trigger workflow results (for logging/testing). Failures are
    non-blocking: a workflow error is recorded and the next trigger still runs,
    so a callback never rolls back the node that fired it.
    """

    if depth >= MAX_TRIGGER_DEPTH:
        return []

    # Lazy imports avoid an import cycle: workflows -> falkor_abox -> triggers.
    from data_oop.falkor.repository import FalkorTBoxRepository
    from data_oop.workflow.workflows import _interpolate, _resolve_path, run_workflow

    repo = FalkorTBoxRepository(graph)
    triggers = repo.get_triggers_for_class(class_name, event=event)  # enabled, ordered
    if not triggers:
        return []

    # Read the full node once; fall back to the upsert delta if it has vanished.
    context = _fetch_node_props(graph, class_name, node.get("uuid")) or dict(node)

    results: list[dict[str, Any]] = []
    for trigger in triggers:
        if trigger.condition:
            value = _resolve_path(trigger.condition, context)
            if value is None or value == "" or value == []:
                continue
        if trigger.parameter_map:
            parameters = {
                key: _interpolate(template, context)
                for key, template in trigger.parameter_map.items()
            }
        else:
            parameters = dict(context)
        try:
            outcome = run_workflow(
                graph=graph,
                name=trigger.workflow_name,
                parameters=parameters,
                _depth=depth + 1,
            )
            results.append({"trigger": trigger.name, "status": "ok", "result": outcome})
        except Exception as exc:  # noqa: BLE001 - non-blocking by design
            results.append({"trigger": trigger.name, "status": "error", "error": str(exc)})
    return results
