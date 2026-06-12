import { FolderOpen, Plus } from "lucide-react";
import type { Workflow } from "../../types";

interface WorkflowListProps {
  workflows: Workflow[];
  selectedWorkflow: Workflow | null;
  onLoadWorkflow: (wf: Workflow) => void;
  onResetEditor: () => void;
}

/** Left-panel list of saved workflows + "new workflow" actions. */
export function WorkflowList({ workflows, selectedWorkflow, onLoadWorkflow, onResetEditor }: WorkflowListProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wider m-0">Saved Workflows</h3>
        <button onClick={onResetEditor} className="p-1 hover:bg-slate-100 rounded text-slate-500" title="New Workflow">
          <Plus className="h-4.5 w-4.5" />
        </button>
      </div>
      {workflows.length === 0 ? (
        <p className="text-xs text-slate-400 italic py-2">No workflows saved.</p>
      ) : (
        <div className="space-y-2">
          {workflows.map((wf) => (
            <button
              key={wf.name}
              onClick={() => onLoadWorkflow(wf)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-between ${
                selectedWorkflow?.name === wf.name
                  ? "bg-indigo-50 text-indigo-700 border border-indigo-100"
                  : "bg-slate-50 text-slate-700 hover:bg-slate-100 border border-transparent"
              }`}
            >
              <span className="truncate">{wf.name}</span>
              <FolderOpen className="h-4 w-4 opacity-50" />
            </button>
          ))}
        </div>
      )}
      <div className="mt-4 pt-4 border-t border-slate-100">
        <button
          onClick={onResetEditor}
          className="w-full flex items-center justify-center space-x-1 py-1.5 bg-slate-900 text-white hover:bg-slate-800 text-xs font-semibold rounded-lg"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Workflow</span>
        </button>
      </div>
    </div>
  );
}
