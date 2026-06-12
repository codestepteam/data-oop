import { useEffect, useState } from "react";
import { Zap, Plus, Trash2, AlertTriangle } from "lucide-react";
import { apiFetch } from "../../api";
import type { TBoxClass, TriggerGraphReport } from "../../types";
import type { TriggerInput } from "../../hooks/useTBox";

interface CreateTriggerModalProps {
  classes: TBoxClass[];
  onClose: () => void;
  onCreateTrigger: (input: TriggerInput) => Promise<{ ok: boolean; error?: string; cycles?: string[][] }>;
  onValidateTriggers: (candidate?: TriggerInput) => Promise<TriggerGraphReport | null>;
}

/** Modal form to register a class-level trigger (on create/update → run workflow). */
export function CreateTriggerModal({ classes, onClose, onCreateTrigger, onValidateTriggers }: CreateTriggerModalProps) {
  const [trgClass, setTrgClass] = useState("");
  const [trgName, setTrgName] = useState("");
  const [trgEvent, setTrgEvent] = useState<"create" | "update">("create");
  const [trgWorkflow, setTrgWorkflow] = useState("");
  const [trgCondition, setTrgCondition] = useState("");
  const [trgOrder, setTrgOrder] = useState(0);
  const [trgDesc, setTrgDesc] = useState("");
  const [trgParams, setTrgParams] = useState<{ key: string; value: string }[]>([]);
  const [trgError, setTrgError] = useState<string | null>(null);
  const [trgReport, setTrgReport] = useState<TriggerGraphReport | null>(null);
  const [workflowNames, setWorkflowNames] = useState<string[]>([]);

  // Workflow names power the "run this workflow" dropdown.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/api/workflows");
        const data = await res.json();
        if (!cancelled && Array.isArray(data)) {
          setWorkflowNames(data.map((w: { name: string }) => w.name));
        }
      } catch (err) {
        console.error("Error fetching workflows", err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const triggerInput = (): TriggerInput => {
    const parameter_map: Record<string, string> = {};
    for (const row of trgParams) {
      if (row.key.trim()) parameter_map[row.key.trim()] = row.value;
    }
    return {
      class_name: trgClass,
      name: trgName,
      event: trgEvent,
      workflow_name: trgWorkflow,
      condition: trgCondition || null,
      order: trgOrder,
      description: trgDesc || null,
      parameter_map,
    };
  };

  const handlePreview = async () => {
    setTrgError(null);
    if (!trgClass || !trgName || !trgWorkflow) {
      setTrgError("Class, name and workflow are required to validate.");
      return;
    }
    const report = await onValidateTriggers(triggerInput());
    setTrgReport(report);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTrgError(null);
    const result = await onCreateTrigger(triggerInput());
    if (result.ok) {
      onClose();
      return;
    }
    if (result.cycles && result.cycles.length > 0) {
      setTrgError(`Trigger cycle detected: ${result.cycles.map((c) => c.join(" → ")).join("; ")}`);
    } else {
      setTrgError(result.error || "Failed to create trigger.");
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-lg w-full p-6 shadow-xl border border-slate-200 max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold text-slate-900 mb-1 flex items-center space-x-2">
          <Zap className="h-5 w-5 text-rose-500" />
          <span>Add Trigger</span>
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          When a node of the class is created/updated, the chosen workflow runs. The node's
          properties are passed as parameters (e.g. <span className="font-mono">{"{uuid}"}</span>). Cycles are
          rejected before saving.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Class</label>
              <select
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
                value={trgClass}
                onChange={(e) => setTrgClass(e.target.value)}
              >
                <option value="">Select class…</option>
                {classes.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Event</label>
              <select
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
                value={trgEvent}
                onChange={(e) => setTrgEvent(e.target.value as "create" | "update")}
              >
                <option value="create">create</option>
                <option value="update">update</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Trigger Name</label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
              value={trgName}
              onChange={(e) => setTrgName(e.target.value)}
              placeholder="e.g. on_order_created"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Run Workflow</label>
            <select
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
              value={trgWorkflow}
              onChange={(e) => setTrgWorkflow(e.target.value)}
            >
              <option value="">Select workflow…</option>
              {workflowNames.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Condition (optional)</label>
              <input
                type="text"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
                value={trgCondition}
                onChange={(e) => setTrgCondition(e.target.value)}
                placeholder="property path, fires if non-empty"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Order</label>
              <input
                type="number"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
                value={trgOrder}
                onChange={(e) => setTrgOrder(Number(e.target.value) || 0)}
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Description</label>
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-rose-500"
              rows={2}
              value={trgDesc}
              onChange={(e) => setTrgDesc(e.target.value)}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Parameter Map (workflow param ← value)
              </label>
              <button
                type="button"
                onClick={() => setTrgParams([...trgParams, { key: "", value: "" }])}
                className="text-xs text-rose-600 hover:text-rose-700 flex items-center space-x-1"
              >
                <Plus className="h-3 w-3" />
                <span>Add</span>
              </button>
            </div>
            <p className="text-[11px] text-slate-400 mb-2">
              Value is interpolated against the node, e.g. <span className="font-mono">{"{uuid}"}</span>,{" "}
              <span className="font-mono">{"{total}"}</span>, or a literal. Leave empty to pass all node properties through.
            </p>
            {trgParams.length === 0 ? (
              <p className="text-[11px] text-slate-400 italic">No bindings — node properties passed flat.</p>
            ) : (
              <div className="space-y-2">
                {trgParams.map((row, i) => (
                  <div key={i} className="flex items-center space-x-2">
                    <input
                      type="text"
                      placeholder="param name"
                      className="flex-1 px-2 py-1.5 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:border-rose-500"
                      value={row.key}
                      onChange={(e) => {
                        const next = [...trgParams];
                        next[i] = { ...next[i], key: e.target.value };
                        setTrgParams(next);
                      }}
                    />
                    <span className="text-slate-400 text-sm">←</span>
                    <input
                      type="text"
                      placeholder="{uuid} or literal"
                      className="flex-1 px-2 py-1.5 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:border-rose-500"
                      value={row.value}
                      onChange={(e) => {
                        const next = [...trgParams];
                        next[i] = { ...next[i], value: e.target.value };
                        setTrgParams(next);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setTrgParams(trgParams.filter((_, j) => j !== i))}
                      className="text-slate-400 hover:text-rose-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {trgError && (
            <div className="flex items-start space-x-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{trgError}</span>
            </div>
          )}

          {trgReport && (
            <div
              className={`text-sm rounded-lg p-2 border ${
                trgReport.valid
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : "text-rose-700 bg-rose-50 border-rose-200"
              }`}
            >
              {trgReport.valid ? (
                <span>✓ No cycle. Safe to add.</span>
              ) : (
                <span>
                  ✗ Cycle: {trgReport.cycles.map((c) => c.join(" → ")).join("; ")}
                </span>
              )}
              {trgReport.unbounded.length > 0 && (
                <p className="text-amber-700 mt-1">⚠ Unbounded fan-out (loop_over): {trgReport.unbounded.join(", ")}</p>
              )}
              {trgReport.unresolved.length > 0 && (
                <p className="text-amber-700 mt-1">⚠ Dynamic class (unanalyzable): {trgReport.unresolved.join(", ")}</p>
              )}
            </div>
          )}

          <div className="flex justify-between items-center pt-2">
            <button
              type="button"
              onClick={handlePreview}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm font-medium bg-slate-50 text-slate-700 hover:bg-slate-100"
            >
              Validate
            </button>
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm font-medium bg-white text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700"
              >
                Add Trigger
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
