import { ReactFlow, Background, Controls } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import { Code } from "lucide-react";
import type { WorkflowStep } from "../../types";

interface WorkflowCanvasProps {
  editorSteps: WorkflowStep[];
  flowNodes: Node[];
  flowEdges: Edge[];
  onSelectStep: (idx: number) => void;
  onMoveNode: (stepId: string, position: { x: number; y: number }) => void;
}

/** Read-only React Flow rendering of the pipeline; clicks select, drags reposition. */
export function WorkflowCanvas({ editorSteps, flowNodes, flowEdges, onSelectStep, onMoveNode }: WorkflowCanvasProps) {
  return (
    <div className="space-y-4">
      <span className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Visual Pipeline Flow</span>
      <div className="h-[420px] w-full border border-slate-200 rounded-xl bg-slate-50 relative overflow-hidden mb-4">
        {editorSteps.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
            <Code className="h-8 w-8 mb-2 text-slate-300 animate-pulse" />
            <span className="text-xs font-medium">No steps defined. Add a step below to begin.</span>
          </div>
        ) : (
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            onNodeClick={(_, node) => {
              const idx = editorSteps.findIndex((s) => s.step_id === node.id);
              if (idx !== -1) {
                onSelectStep(idx);
              }
            }}
            onNodeDragStop={(_, node) => onMoveNode(node.id, node.position)}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            nodesConnectable={false}
            nodesDraggable={true}
          >
            <Background color="#cbd5e1" gap={16} size={1} />
            <Controls showInteractive={false} />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
