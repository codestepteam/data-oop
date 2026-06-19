// Pure layout derivation for the workflow pipeline canvas.
// Extracted from WorkflowTab so the per-render DAG math can be memoized and tested
// independently of the React tree.
import { MarkerType } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import type { WorkflowStep } from "../../types";

type XY = { x: number; y: number };

/** Step ids referenced via `{stepId.path}` placeholders inside a step's fields. */
export function getStepDependencies(step: WorkflowStep): string[] {
  const deps: string[] = [];
  const stepStr = JSON.stringify(step);
  const regex = /\{([a-zA-Z0-9_]+)\.[a-zA-Z0-9_.]+\}/g;
  let match;
  while ((match = regex.exec(stepStr)) !== null) {
    const stepId = match[1];
    if (!deps.includes(stepId)) {
      deps.push(stepId);
    }
  }
  return deps;
}

/** DAG-ish auto-layout: dependents drop below their sources, siblings spread by column. */
export function computeStepPositions(editorSteps: WorkflowStep[]): Record<string, XY> {
  const computedPositions: Record<string, XY> = {};
  let colCount = 0;

  const isOverlap = (x: number, y: number): boolean =>
    Object.values(computedPositions).some(
      (pos) => Math.abs(pos.x - x) < 180 && Math.abs(pos.y - y) < 80
    );

  editorSteps.forEach((step) => {
    const deps = getStepDependencies(step);
    const validDeps = deps.filter((depId) => editorSteps.some((s) => s.step_id === depId));

    let calcX = 50;
    let calcY = 50;

    if (step.action === "create_relationship" && validDeps.length >= 1) {
      let avgX = 0;
      let maxY = 0;
      validDeps.forEach((depId) => {
        const depPos = computedPositions[depId] || { x: 50, y: 50 };
        avgX += depPos.x;
        maxY = Math.max(maxY, depPos.y);
      });
      calcX = avgX / validDeps.length;
      calcY = maxY + 150;
    } else {
      calcX = colCount * 280 + 50;
      calcY = 50;
      colCount++;
    }

    while (isOverlap(calcX, calcY)) {
      calcX += 280;
    }

    computedPositions[step.step_id] = { x: calcX, y: calcY };
  });

  return computedPositions;
}

/** One animated edge per `source → step` dependency. */
export function buildFlowEdges(editorSteps: WorkflowStep[]): Edge[] {
  const flowEdges: Edge[] = [];
  editorSteps.forEach((step) => {
    const deps = getStepDependencies(step);
    const validDeps = deps.filter((depId) => editorSteps.some((s) => s.step_id === depId));
    validDeps.forEach((depId) => {
      flowEdges.push({
        id: `edge-${depId}-${step.step_id}`,
        source: depId,
        target: step.step_id,
        animated: true,
        style: { stroke: "#6366f1", strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#6366f1" },
      });
    });
  });
  return flowEdges;
}

/** React Flow nodes with the step-card label baked in; highlights the active step. */
export function buildFlowNodes(
  editorSteps: WorkflowStep[],
  activeStepIdx: number | null,
  positions: Record<string, XY>,
  customPositions: Record<string, XY>
): Node[] {
  return editorSteps.map((step, idx) => {
    const isSelected = activeStepIdx === idx;
    const pos = customPositions[step.step_id] || positions[step.step_id] || { x: idx * 260 + 50, y: 50 };
    let subtitle = "";
    let bg = "bg-white border-slate-200 text-slate-800";

    if (step.action === "create_node") {
      subtitle = `Create Node: ${step.class_name}`;
      bg = isSelected ? "bg-indigo-50 border-indigo-500 text-indigo-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "create_relationship") {
      subtitle = `Link: ${step.relationship_name}`;
      bg = isSelected ? "bg-amber-50 border-amber-500 text-amber-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "run_workflow") {
      subtitle = `Sub-Workflow: ${step.workflow_name || "(empty)"}`;
      bg = isSelected ? "bg-emerald-50 border-emerald-500 text-emerald-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "fetch_view") {
      subtitle = `Fetch View: ${step.view_name || "(empty)"}`;
      bg = isSelected ? "bg-sky-50 border-sky-500 text-sky-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "transform") {
      subtitle = "Transform data";
      bg = isSelected ? "bg-violet-50 border-violet-500 text-violet-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "abox_query") {
      subtitle = "Read-only ABox query";
      bg = isSelected ? "bg-cyan-50 border-cyan-500 text-cyan-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "http_request") {
      subtitle = `${step.method || "GET"}: ${step.url || "(empty)"}`;
      bg = isSelected ? "bg-rose-50 border-rose-500 text-rose-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "materialize_source") {
      subtitle = `Materialize: ${step.class_name || "(empty)"}`;
      bg = isSelected ? "bg-lime-50 border-lime-500 text-lime-900 border-2" : "bg-white border-slate-300 text-slate-800";
    } else if (step.action === "db_operation") {
      subtitle = `DB Operation: ${step.operation_name || "(empty)"}`;
      bg = isSelected ? "bg-orange-50 border-orange-500 text-orange-900 border-2" : "bg-white border-slate-300 text-slate-800";
    }

    return {
      id: step.step_id,
      position: pos,
      data: {
        label: (
          <div className={`p-3 rounded-lg shadow-sm border ${bg} text-left min-w-[200px] cursor-pointer`}>
            <div className="flex justify-between items-center">
              <span className="font-mono text-xs font-bold">{step.step_id}</span>
              <span className="text-[9px] px-1.5 py-0.5 bg-slate-100 rounded text-slate-500 uppercase font-medium">
                {step.action.replace("_", " ")}
              </span>
            </div>
            <div className="text-[10px] text-slate-500 mt-1 font-semibold truncate">{subtitle}</div>
            {step.loop_over && (
              <div className="text-[9px] text-emerald-600 bg-emerald-50 border border-emerald-100 rounded px-1.5 py-0.5 mt-1.5 inline-block font-bold">
                Loop: {step.loop_over}
              </div>
            )}
            {step.if_present && (
              <div className="text-[9px] text-blue-600 bg-blue-50 border border-blue-100 rounded px-1.5 py-0.5 mt-1.5 inline-block ml-1">
                If: {step.if_present}
              </div>
            )}
          </div>
        ),
      },
      style: { background: "none", border: "none", padding: 0 },
    };
  });
}
