import { useState } from "react";
import { Play, Search } from "lucide-react";
import type { Workflow, RunResult } from "../../types";

interface RunPanelProps {
  selectedWorkflow: Workflow;
  runParams: Record<string, string>;
  setRunParams: (v: Record<string, string>) => void;
  runResult: RunResult | null;
  running: boolean;
  onRunWorkflow: () => void;
  openNodeSelector: (className: string, callback: (uuid: string) => void) => void;
}

/** Run-time parameter form + execution result for the selected workflow. */
export function RunPanel({
  selectedWorkflow,
  runParams,
  setRunParams,
  runResult,
  running,
  onRunWorkflow,
  openNodeSelector,
}: RunPanelProps) {
  const [showRunResult, setShowRunResult] = useState(false);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wider mb-4 flex items-center space-x-1">
        <Play className="h-4 w-4 text-emerald-500 fill-emerald-500" />
        <span>Run Workflow</span>
      </h3>
      <div className="space-y-4">
        {Object.keys(runParams).length === 0 ? (
          <p className="text-xs text-slate-400 italic">No parameters required.</p>
        ) : (
          selectedWorkflow.parameters && selectedWorkflow.parameters.length > 0 ? (
          selectedWorkflow.parameters.map((param) => {
              if (param.type === "array") {
                let arrayValues: string[] = [];
                try {
                  const parsed = JSON.parse(runParams[param.name] || "[]");
                  if (Array.isArray(parsed)) {
                    arrayValues = parsed;
                  }
                } catch (e) {
                  const raw = runParams[param.name] || "";
                  if (raw.trim()) {
                    arrayValues = raw.split(",").map(v => v.trim()).filter(Boolean);
                  }
                }

                const handleAddArrayItem = (itemVal: string) => {
                  const trimmed = itemVal.trim();
                  if (!trimmed) return;
                  const updated = [...arrayValues, trimmed];
                  setRunParams({ ...runParams, [param.name]: JSON.stringify(updated) });
                };

                return (
                  <div key={param.name} className="space-y-1.5">
                    <label className="block text-[11px] font-bold text-slate-500 mb-0.5">
                      {param.name} {param.required && <span className="text-rose-500">*</span>}
                      <span className="text-[10px] text-slate-400 font-normal ml-1">
                        (array&lt;{param.array_item_type === "uuid" ? `uuid:${param.array_item_class}` : param.array_item_type}&gt;)
                      </span>
                    </label>
                    {param.description && (
                      <span className="block text-[10px] text-slate-400 mb-1 italic leading-tight">{param.description}</span>
                    )}

                    {/* Visual List Builder Tags */}
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 flex flex-wrap gap-1 min-h-[40px]">
                      {arrayValues.length === 0 ? (
                        <span className="text-[10px] text-slate-400 italic self-center">No items added</span>
                      ) : (
                        arrayValues.map((val, vIdx) => (
                          <div key={vIdx} className="bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full px-2 py-0.5 flex items-center space-x-1 text-[10px]">
                            <span className="truncate max-w-[120px] font-mono">{val}</span>
                            <button
                              type="button"
                              onClick={() => {
                                const updated = arrayValues.filter((_, i) => i !== vIdx);
                                setRunParams({ ...runParams, [param.name]: JSON.stringify(updated) });
                              }}
                              className="text-indigo-400 hover:text-indigo-700 font-bold ml-1"
                            >
                              ×
                            </button>
                          </div>
                        ))
                      )}
                    </div>

                    {/* Item Add Control */}
                    {param.array_item_type === "uuid" && param.array_item_class ? (
                      <button
                        type="button"
                        onClick={() => openNodeSelector(param.array_item_class || "", handleAddArrayItem)}
                        className="w-full py-1 border border-slate-300 bg-white hover:bg-slate-50 rounded-lg text-slate-600 text-xs font-medium flex items-center justify-center space-x-1"
                      >
                        <Search className="h-3 w-3" />
                        <span>Select {param.array_item_class} Node</span>
                      </button>
                    ) : (
                      <div className="flex items-center space-x-1">
                        <input
                          type="text"
                          id={`add-item-input-${param.name}`}
                          className="flex-1 px-2.5 py-1 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500"
                          placeholder={`Add ${param.array_item_type || "item"}...`}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              const el = e.currentTarget;
                              handleAddArrayItem(el.value);
                              el.value = "";
                            }
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const el = document.getElementById(`add-item-input-${param.name}`) as HTMLInputElement;
                            if (el) {
                              handleAddArrayItem(el.value);
                              el.value = "";
                            }
                          }}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold"
                        >
                          +
                        </button>
                      </div>
                    )}
                  </div>
                );
              }

              return (
                <div key={param.name} className="space-y-1">
                  <label className="block text-[11px] font-bold text-slate-500 mb-0.5">
                    {param.name} {param.required && <span className="text-rose-500">*</span>}
                    <span className="text-[10px] text-slate-400 font-normal ml-1">({param.type})</span>
                  </label>
                  {param.description && (
                    <span className="block text-[10px] text-slate-400 mb-1 italic leading-tight">{param.description}</span>
                  )}
                  <input
                    type="text"
                    required={param.required}
                    className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500"
                    placeholder={param.required ? "Required" : "Optional"}
                    value={runParams[param.name] || ""}
                    onChange={(e) =>
                      setRunParams({ ...runParams, [param.name]: e.target.value })
                    }
                  />
                </div>
              );
            })
          ) : (
            Object.keys(runParams).map((paramName) => (
              <div key={paramName}>
                <label className="block text-[11px] font-bold text-slate-500 mb-1">{paramName}</label>
                <input
                  type="text"
                  className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500"
                  value={runParams[paramName] || ""}
                  onChange={(e) =>
                    setRunParams({ ...runParams, [paramName]: e.target.value })
                  }
                />
              </div>
            ))
          )
        )}
        <button
          onClick={onRunWorkflow}
          disabled={running}
          className="w-full py-2 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700 disabled:bg-slate-300 transition-colors"
        >
          {running ? "Executing..." : "Execute"}
        </button>
      </div>

      {runResult && (
        <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
          <button
            type="button"
            onClick={() => setShowRunResult(!showRunResult)}
            className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs font-semibold text-slate-600 border border-slate-200 transition-colors"
          >
            <span>Execution Results ({runResult.status || (runResult.error ? "Failed" : "Success")})</span>
            <span className="text-[10px] text-indigo-600 font-bold font-mono">{showRunResult ? "Collapse" : "Expand"}</span>
          </button>
          {showRunResult && (
            <pre className="bg-slate-900 text-indigo-300 text-[10px] p-3 rounded-lg overflow-x-auto max-h-64 font-mono w-full">
              {JSON.stringify(runResult, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
