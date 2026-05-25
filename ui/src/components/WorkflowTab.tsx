import { useState } from "react";
import {
  FolderOpen,
  Plus,
  Play,
  Save,
  Trash,
  Settings,
  Variable,
  Search,
  Code
} from "lucide-react";
import { ReactFlow, Background, Controls, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Workflow, WorkflowStep, WorkflowParameter, TBoxClass, TBoxRelationship } from "../types";

interface WorkflowTabProps {
  tbox: {
    classes: TBoxClass[];
    relationships: TBoxRelationship[];
  };
  workflows: Workflow[];
  loadingWorkflows: boolean;
  selectedWorkflow: Workflow | null;
  editorName: string;
  setEditorName: (v: string) => void;
  editorDesc: string;
  setEditorDesc: (v: string) => void;
  editorSteps: WorkflowStep[];
  editorParameters: WorkflowParameter[];
  runParams: Record<string, string>;
  setRunParams: (v: any) => void;
  runResult: any;
  running: boolean;
  onAddStep: (action: "create_node" | "create_relationship" | "run_workflow") => void;
  onRemoveStep: (idx: number) => void;
  onUpdateStep: (idx: number, fields: any) => void;
  onAddParameter: (p: WorkflowParameter) => boolean;
  onRemoveParameter: (name: string) => void;
  onSaveEditedParam: (idx: number, p: WorkflowParameter) => boolean;
  onLoadWorkflow: (wf: Workflow) => void;
  onSaveWorkflow: () => void;
  onRunWorkflow: () => void;
  onResetEditor: () => void;
  generatePythonDSL: () => string;
  openNodeSelector: (className: string, callback: (uuid: string) => void) => void;
}

export function WorkflowTab({
  tbox,
  workflows,
  selectedWorkflow,
  editorName,
  setEditorName,
  editorDesc,
  setEditorDesc,
  editorSteps,
  editorParameters,
  runParams,
  setRunParams,
  runResult,
  running,
  onAddStep,
  onRemoveStep,
  onUpdateStep,
  onAddParameter,
  onRemoveParameter,
  onSaveEditedParam,
  onLoadWorkflow,
  onSaveWorkflow,
  onRunWorkflow,
  onResetEditor,
  generatePythonDSL,
  openNodeSelector
}: WorkflowTabProps) {
  // Local state for add parameter form
  const [newParamName, setNewParamName] = useState("");
  const [newParamType, setNewParamType] = useState("string");
  const [newParamDesc, setNewParamDesc] = useState("");
  const [newParamRequired, setNewParamRequired] = useState(true);
  const [newParamItemType, setNewParamItemType] = useState("string");
  const [newParamItemClass, setNewParamItemClass] = useState("");

  // Local state for parameter inline editing
  const [editingParamIdx, setEditingParamIdx] = useState<number | null>(null);
  const [editParamName, setEditParamName] = useState("");
  const [editParamType, setEditParamType] = useState("string");
  const [editParamDesc, setEditParamDesc] = useState("");
  const [editParamRequired, setEditParamRequired] = useState(true);
  const [editParamItemType, setEditParamItemType] = useState("string");
  const [editParamItemClass, setEditParamItemClass] = useState("");

  // Collapsible control settings per step
  const [expandedSettings, setExpandedSettings] = useState<Record<number, boolean>>({});

  // Local state for React Flow active step index
  const [activeStepIdx, setActiveStepIdx] = useState<number | null>(null);

  // Local state for toggling execution results expansion
  const [showRunResult, setShowRunResult] = useState(false);

  // Local state for toggling DSL / JSON code preview
  const [showCodePreview, setShowCodePreview] = useState(false);

  // Helper to extract step dependencies from step properties / bindings
  const getStepDependencies = (step: WorkflowStep): string[] => {
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
  };

  // Calculate dynamic layout coordinates for DAG-like tree flow
  const positions: Record<string, { x: number; y: number }> = {};
  let colCount = 0;

  editorSteps.forEach((step) => {
    const deps = getStepDependencies(step);
    const validDeps = deps.filter(depId => editorSteps.some(s => s.step_id === depId));

    if (step.action === "create_relationship" && validDeps.length >= 1) {
      let avgX = 0;
      let maxY = 0;
      validDeps.forEach(depId => {
        const depPos = positions[depId] || { x: 50, y: 50 };
        avgX += depPos.x;
        maxY = Math.max(maxY, depPos.y);
      });
      positions[step.step_id] = {
        x: avgX / validDeps.length,
        y: maxY + 150
      };
    } else {
      positions[step.step_id] = {
        x: colCount * 280 + 50,
        y: 50
      };
      colCount++;
    }
  });

  // Derive nodes and edges dynamically for React Flow
  const flowNodes = editorSteps.map((step, idx) => {
    const isSelected = activeStepIdx === idx;
    const pos = positions[step.step_id] || { x: idx * 260 + 50, y: 50 };
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
        )
      },
      style: { background: "none", border: "none", padding: 0 }
    };
  });

  const flowEdges: any[] = [];
  editorSteps.forEach((step) => {
    const deps = getStepDependencies(step);
    const validDeps = deps.filter(depId => editorSteps.some(s => s.step_id === depId));
    
    if (validDeps.length > 0) {
      validDeps.forEach(depId => {
        flowEdges.push({
          id: `edge-${depId}-${step.step_id}`,
          source: depId,
          target: step.step_id,
          animated: true,
          style: { stroke: "#6366f1", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#6366f1"
          }
        });
      });
    }
  });

  const handleAddParam = () => {
    if (!newParamName) return;
    const ok = onAddParameter({
      name: newParamName,
      type: newParamType,
      required: newParamRequired,
      description: newParamDesc,
      array_item_type: newParamType === "array" ? newParamItemType : undefined,
      array_item_class: newParamType === "array" && newParamItemType === "uuid" ? newParamItemClass || tbox.classes[0]?.name : undefined,
    });
    if (ok) {
      setNewParamName("");
      setNewParamDesc("");
      setNewParamItemType("string");
      setNewParamItemClass("");
    }
  };

  const handleStartEditParam = (idx: number, p: WorkflowParameter) => {
    setEditingParamIdx(idx);
    setEditParamName(p.name);
    setEditParamType(p.type);
    setEditParamDesc(p.description);
    setEditParamRequired(p.required);
    setEditParamItemType(p.array_item_type || "string");
    setEditParamItemClass(p.array_item_class || (tbox.classes[0]?.name || ""));
  };

  const handleSaveEditParam = (idx: number) => {
    if (!editParamName) return;
    const ok = onSaveEditedParam(idx, {
      name: editParamName,
      type: editParamType,
      required: editParamRequired,
      description: editParamDesc,
      array_item_type: editParamType === "array" ? editParamItemType : undefined,
      array_item_class: editParamType === "array" && editParamItemType === "uuid" ? editParamItemClass : undefined,
    });
    if (ok) {
      setEditingParamIdx(null);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left Panel: Saved Workflows */}
      <div className="lg:col-span-3 space-y-6">
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

        {/* Execution parameters / Test Run Panel */}
        {selectedWorkflow && (
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
        )}

        {/* Collapsible DSL / JSON Preview (Faint One-Liner) */}
        <div className="pt-2 border-t border-slate-100 text-slate-400">
          <button
            type="button"
            onClick={() => setShowCodePreview(!showCodePreview)}
            className="w-full flex items-center justify-between text-[10px] font-bold tracking-wide uppercase hover:text-slate-600 transition-colors py-1 cursor-pointer"
          >
            <span className="flex items-center space-x-1">
              <Code className="h-3 w-3" />
              <span>DSL & JSON Code Previews</span>
            </span>
            <span className="font-bold font-mono text-[9px] bg-slate-100 text-slate-500 px-1 rounded">{showCodePreview ? "Hide" : "Show"}</span>
          </button>
          {showCodePreview && (
            <div className="mt-3 space-y-4 animate-fadeIn">
              {/* Python DSL */}
              <div className="border border-slate-200 rounded-lg overflow-hidden flex flex-col h-[280px]">
                <div className="bg-slate-900 px-2 py-1 flex items-center justify-between text-white text-[9px] font-bold uppercase tracking-wider">
                  <span>Python DSL</span>
                </div>
                <div className="p-2 flex-1 overflow-y-auto bg-slate-950 font-mono text-[9px] leading-normal text-indigo-300">
                  <pre className="whitespace-pre-wrap">{generatePythonDSL()}</pre>
                </div>
              </div>
              {/* JSON steps_json */}
              <div className="border border-slate-200 rounded-lg overflow-hidden flex flex-col h-[200px]">
                <div className="bg-slate-900 px-2 py-1 flex items-center justify-between text-white text-[9px] font-bold uppercase tracking-wider">
                  <span>JSON steps_json</span>
                </div>
                <div className="p-2 flex-1 overflow-y-auto bg-slate-950 font-mono text-[9px] leading-normal text-indigo-300">
                  <pre className="whitespace-pre-wrap">{JSON.stringify(editorSteps, null, 2)}</pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Middle Panel: Visual step-by-step editor */}
      <div className="lg:col-span-9 space-y-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-slate-900 text-base m-0">Workflow Steps Builder</h3>
            <div className="flex space-x-2">
              <button
                onClick={onSaveWorkflow}
                className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Save Workflow</span>
              </button>
            </div>
          </div>

          <div className="space-y-4 mb-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Workflow Name</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 font-mono"
                  placeholder="e.g. create_sales_channel"
                  value={editorName}
                  onChange={(e) => setEditorName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Description</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Optional description"
                  value={editorDesc}
                  onChange={(e) => setEditorDesc(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Parameters Schema Manager */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                <Variable className="h-4 w-4 text-indigo-500" />
                <span>Declared Input Parameters ({editorParameters.length})</span>
              </h4>
            </div>
            
            {editorParameters.length > 0 && (
              <div className="bg-white rounded-lg border border-slate-200 divide-y divide-slate-100 overflow-hidden">
                {editorParameters.map((p, idx) => {
                  const isEditing = editingParamIdx === idx;
                  return (
                    <div key={idx} className="p-2.5 text-xs">
                      {isEditing ? (
                        <div className="space-y-2">
                          <div className="grid grid-cols-3 gap-2">
                            <div className="col-span-2">
                              <label className="block text-[10px] text-slate-400 font-bold mb-0.5">Variable Name</label>
                              <input
                                type="text"
                                className="w-full px-2 py-1 border border-slate-300 rounded font-mono text-xs focus:outline-none focus:border-indigo-500"
                                value={editParamName}
                                onChange={(e) => setEditParamName(e.target.value.replace(/[^a-zA-Z0-9_]/g, ""))}
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-400 font-bold mb-0.5">Type</label>
                              <select
                                className="w-full px-2 py-1 border border-slate-300 rounded text-xs focus:outline-none focus:border-indigo-500 bg-white"
                                value={editParamType}
                                onChange={(e) => setEditParamType(e.target.value)}
                              >
                                <option value="string">string</option>
                                <option value="integer">integer</option>
                                <option value="boolean">boolean</option>
                                <option value="uuid">uuid</option>
                                <option value="array">array</option>
                              </select>
                            </div>
                          </div>
                          {editParamType === "array" && (
                            <div className="grid grid-cols-2 gap-2 mt-2">
                              <div>
                                <label className="block text-[10px] text-slate-400 font-bold mb-0.5">Item Type</label>
                                <select
                                  className="w-full px-2 py-1 border border-slate-300 rounded text-xs focus:outline-none focus:border-indigo-500 bg-white"
                                  value={editParamItemType}
                                  onChange={(e) => setEditParamItemType(e.target.value)}
                                >
                                  <option value="string">string</option>
                                  <option value="integer">integer</option>
                                  <option value="boolean">boolean</option>
                                  <option value="uuid">uuid</option>
                                </select>
                              </div>
                              {editParamItemType === "uuid" && (
                                <div>
                                  <label className="block text-[10px] text-slate-400 font-bold mb-0.5">Target Class</label>
                                  <select
                                    className="w-full px-2 py-1 border border-slate-300 rounded text-xs focus:outline-none focus:border-indigo-500 bg-white"
                                    value={editParamItemClass}
                                    onChange={(e) => setEditParamItemClass(e.target.value)}
                                  >
                                    {tbox.classes.map(c => (
                                      <option key={c.name} value={c.name}>{c.name}</option>
                                    ))}
                                  </select>
                                </div>
                              )}
                            </div>
                          )}
                          <div className="grid grid-cols-3 gap-2 items-center">
                            <div className="col-span-2">
                              <label className="block text-[10px] text-slate-400 font-bold mb-0.5">Description</label>
                              <input
                                type="text"
                                className="w-full px-2 py-1 border border-slate-300 rounded text-xs focus:outline-none focus:border-indigo-500"
                                value={editParamDesc}
                                onChange={(e) => setEditParamDesc(e.target.value)}
                              />
                            </div>
                            <div className="flex items-center space-x-2 pt-3">
                              <label className="flex items-center space-x-1 font-medium text-slate-700">
                                <input
                                  type="checkbox"
                                  className="rounded text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                                  checked={editParamRequired}
                                  onChange={(e) => setEditParamRequired(e.target.checked)}
                                />
                                <span>Required</span>
                              </label>
                            </div>
                          </div>
                          <div className="flex justify-end space-x-2 pt-1">
                            <button
                              onClick={() => setEditingParamIdx(null)}
                              className="px-2.5 py-1 border border-slate-300 bg-slate-50 hover:bg-slate-100 rounded text-[11px] font-semibold text-slate-700"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleSaveEditParam(idx)}
                              className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 rounded text-[11px] font-semibold text-white"
                            >
                              Save
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="font-bold text-slate-900 font-mono">{"{" + p.name + "}"}</span>
                            <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded ml-1.5 uppercase font-medium">
                              {p.type === "array" ? `array<${p.array_item_type === 'uuid' ? `uuid:${p.array_item_class}` : p.array_item_type}>` : p.type}
                            </span>
                            {p.required && <span className="text-[10px] text-rose-600 bg-rose-50 border border-rose-100 px-1 rounded ml-1">Req</span>}
                            {p.description && <p className="text-[10px] text-slate-400 mt-0.5 italic">{p.description}</p>}
                          </div>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleStartEditParam(idx, p)}
                              className="text-slate-400 hover:text-indigo-600"
                              title="Edit parameter"
                            >
                              <Settings className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => onRemoveParameter(p.name)}
                              className="text-slate-400 hover:text-rose-600"
                              title="Delete parameter"
                            >
                              <Trash className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Add Param Form */}
            <div className="bg-white p-3 rounded-lg border border-slate-200 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
              <div className="sm:col-span-2">
                <input
                  type="text"
                  className="w-full px-2 py-1.5 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 font-mono text-xs"
                  placeholder="Variable name (e.g. event_name)"
                  value={newParamName}
                  onChange={(e) => setNewParamName(e.target.value.replace(/[^a-zA-Z0-9_]/g, ""))}
                />
              </div>
              <div>
                <select
                  className="w-full px-2 py-1.5 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 bg-white text-xs"
                  value={newParamType}
                  onChange={(e) => setNewParamType(e.target.value)}
                >
                  <option value="string">string</option>
                  <option value="integer">integer</option>
                  <option value="boolean">boolean</option>
                  <option value="uuid">uuid</option>
                  <option value="array">array</option>
                </select>
              </div>
              {newParamType === "array" && (
                <div className="sm:col-span-3 grid grid-cols-2 gap-2 mt-1 bg-white p-2 rounded border border-slate-200">
                  <div>
                    <label className="block text-[10px] text-slate-500 font-bold mb-0.5">Array Item Type</label>
                    <select
                      className="w-full px-2 py-1 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 bg-white text-xs"
                      value={newParamItemType}
                      onChange={(e) => setNewParamItemType(e.target.value)}
                    >
                      <option value="string">string</option>
                      <option value="integer">integer</option>
                      <option value="boolean">boolean</option>
                      <option value="uuid">uuid</option>
                    </select>
                  </div>
                  {newParamItemType === "uuid" && (
                    <div>
                      <label className="block text-[10px] text-slate-500 font-bold mb-0.5">Target Class</label>
                      <select
                        className="w-full px-2 py-1 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 bg-white text-xs"
                        value={newParamItemClass}
                        onChange={(e) => setNewParamItemClass(e.target.value)}
                      >
                        {tbox.classes.map(c => (
                          <option key={c.name} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}
              <div className="sm:col-span-2">
                <input
                  type="text"
                  className="w-full px-2 py-1.5 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 text-xs"
                  placeholder="Description"
                  value={newParamDesc}
                  onChange={(e) => setNewParamDesc(e.target.value)}
                />
              </div>
              <div className="flex items-center justify-between px-1">
                <label className="flex items-center space-x-1.5 font-medium text-slate-700">
                  <input
                    type="checkbox"
                    className="rounded text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                    checked={newParamRequired}
                    onChange={(e) => setNewParamRequired(e.target.checked)}
                  />
                  <span>Required</span>
                </label>
                <button
                  type="button"
                  onClick={handleAddParam}
                  className="flex items-center space-x-0.5 px-2.5 py-1 bg-indigo-600 text-white rounded font-semibold hover:bg-indigo-700"
                >
                  <Plus className="h-3 w-3" />
                  <span>Add</span>
                </button>
              </div>
            </div>
          </div>

          {/* Pipeline Canvas & Steps Builder */}
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
                    const idx = editorSteps.findIndex(s => s.step_id === node.id);
                    if (idx !== -1) {
                      setActiveStepIdx(idx);
                    }
                  }}
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

            {/* Selected Step Configurator */}
            {activeStepIdx !== null && editorSteps[activeStepIdx] ? (() => {
              const step = editorSteps[activeStepIdx];
              const idx = activeStepIdx;
              
              return (
                <div className="border border-slate-200 rounded-xl p-4 bg-slate-50 space-y-4 relative">
                  <button
                    onClick={() => {
                      onRemoveStep(idx);
                      setActiveStepIdx(null);
                    }}
                    className="absolute top-4 right-4 text-slate-400 hover:text-rose-500 transition-colors"
                    title="Delete step"
                  >
                    <Trash className="h-4 w-4" />
                  </button>
                  
                  <div className="flex items-center space-x-2">
                    <span className="bg-indigo-600 text-white text-xs font-bold h-5 w-5 rounded-full flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <span className="font-bold text-sm text-slate-900">Step ID:</span>
                    <input
                      type="text"
                      required
                      className="bg-transparent border-b border-slate-300 font-mono text-xs focus:outline-none focus:border-indigo-500 py-0.5 w-32"
                      value={step.step_id}
                      onChange={(e) => onUpdateStep(idx, { step_id: e.target.value })}
                    />
                    <span className="text-[10px] px-2 py-0.5 bg-slate-200 rounded-full font-bold text-slate-600 uppercase tracking-wide">
                      {step.action.replace("_", " ")}
                    </span>
                  </div>

                  {/* Control Flow Settings Toggle */}
                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      onClick={() => setExpandedSettings({ ...expandedSettings, [idx]: !expandedSettings[idx] })}
                      className="text-[10px] bg-slate-200 text-slate-700 hover:bg-slate-300 px-2 py-0.5 rounded transition-colors font-semibold"
                    >
                      {expandedSettings[idx] ? "Hide Advanced Settings" : "⚙️ Advanced Settings"}
                    </button>
                    {(step.if_present || step.loop_over) && (
                      <span className="text-[9px] bg-amber-100 text-amber-800 border border-amber-200 rounded px-1.5 py-0.5 font-bold">
                        {step.if_present ? "Conditional" : ""} {step.loop_over ? "Looped" : ""}
                      </span>
                    )}
                  </div>

                  {/* Collapsible Advanced Settings Panel */}
                  {expandedSettings[idx] && (
                    <div className="bg-white border border-slate-200 rounded-lg p-3 space-y-3 text-xs">
                      {/* Conditional Run */}
                      <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Conditional Run</label>
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-500">Run only if present:</span>
                          <select
                            className="px-2 py-1 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 bg-white text-xs"
                            value={step.if_present || ""}
                            onChange={(e) => onUpdateStep(idx, { if_present: e.target.value || undefined })}
                          >
                            <option value="">Always Run</option>
                            {editorParameters.filter(p => !p.required).map(p => (
                              <option key={p.name} value={p.name}>{p.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Looped Run */}
                      <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Looped Run</label>
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-500">Loop over (array):</span>
                          <select
                            className="px-2 py-1 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 bg-white text-xs font-mono"
                            value={step.loop_over || ""}
                            onChange={(e) => {
                              const val = e.target.value;
                              const singular = val ? val.replace(/_uuids$/, "_uuid").replace(/s$/, "") : "";
                              onUpdateStep(idx, {
                                loop_over: val || undefined,
                                loop_var: val ? singular || "item" : undefined
                              });
                            }}
                          >
                            <option value="">No Loop</option>
                            {editorParameters.filter(p => p.type === "array").map(p => (
                              <option key={p.name} value={p.name}>{p.name}</option>
                            ))}
                            {editorSteps.slice(0, idx).map(prev => (
                              <option key={prev.step_id} value={`${prev.step_id}.results`}>{prev.step_id}</option>
                            ))}
                          </select>
                        </div>
                        {step.loop_over && (
                          <div className="mt-2 flex items-center space-x-2">
                            <span className="text-slate-500">Loop Variable:</span>
                            <input
                              type="text"
                              className="px-2 py-1 border border-slate-300 rounded focus:outline-none focus:border-indigo-500 font-mono text-xs w-36"
                              value={step.loop_var || "item"}
                              onChange={(e) => onUpdateStep(idx, { loop_var: e.target.value })}
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Action details */}
                  {step.action === "create_node" && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[10px] font-bold text-slate-400 uppercase">Class Name</label>
                          <select
                            className="w-full mt-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:border-indigo-500"
                            value={step.class_name}
                            onChange={(e) => onUpdateStep(idx, { class_name: e.target.value, properties: {} })}
                          >
                            {tbox.classes.map(c => (
                              <option key={c.name} value={c.name}>{c.name}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-slate-400 uppercase">Custom UUID (Optional)</label>
                          <div className="flex items-center space-x-1 mt-1">
                            <input
                              type="text"
                              className="flex-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500"
                              placeholder="Auto-generated if empty"
                              value={step.uuid || ""}
                              onChange={(e) => onUpdateStep(idx, { uuid: e.target.value })}
                            />
                            <button
                              type="button"
                              onClick={() => openNodeSelector(step.class_name || "", (uuid) => onUpdateStep(idx, { uuid }))}
                              className="px-2 py-1.5 border border-slate-300 bg-white hover:bg-slate-50 rounded-lg text-slate-500 text-xs font-medium"
                              title="Select active node"
                            >
                              <Search className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Properties Form Builder */}
                      <div>
                        <span className="block text-[10px] font-bold text-slate-400 uppercase mb-2">Properties ({Object.keys(step.properties || {}).length})</span>
                        <div className="bg-white border border-slate-200 rounded-lg p-3 space-y-3">
                          {tbox.classes.find(c => c.name === step.class_name)?.properties.map(prop => (
                            <div key={prop.name} className="flex flex-col space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-700 truncate">
                                  {prop.name} {prop.required && <span className="text-rose-500">*</span>}
                                </span>
                                {/* Param quick pills */}
                                {(editorParameters.length > 0 || (step.loop_over && step.loop_var)) && (
                                  <div className="flex flex-wrap gap-1">
                                    {editorParameters.map(p => (
                                      <button
                                        key={p.name}
                                        type="button"
                                        onClick={() => {
                                          const newProps = { ...step.properties, [prop.name]: `{${p.name}}` };
                                          onUpdateStep(idx, { properties: newProps });
                                        }}
                                        className="text-[9px] bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-100 rounded px-1"
                                        title={`Use ${p.name}`}
                                      >
                                        {p.name}
                                      </button>
                                    ))}
                                    {step.loop_over && step.loop_var && (
                                      <button
                                        type="button"
                                        onClick={() => {
                                          const newProps = { ...step.properties, [prop.name]: `{${step.loop_var}}` };
                                          onUpdateStep(idx, { properties: newProps });
                                        }}
                                        className="text-[9px] bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-100 rounded px-1 font-bold"
                                        title={`Use Loop Variable ${step.loop_var}`}
                                      >
                                        {step.loop_var} (Loop)
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                              <div className="flex items-center space-x-1">
                                <input
                                  type="text"
                                  className="flex-1 px-2.5 py-1 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500 font-mono"
                                  placeholder={prop.required ? "Required (literal or {var})" : "Optional"}
                                  value={step.properties?.[prop.name] || ""}
                                  onChange={(e) => {
                                    const newProps = { ...step.properties, [prop.name]: e.target.value };
                                    onUpdateStep(idx, { properties: newProps });
                                  }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Relationship Step Builder */}
                  {step.action === "create_relationship" && (
                    (() => {
                      const allowedRels = tbox.relationships.filter(
                        r => r.from_class === step.from_class && r.to_class === step.to_class
                      );
                      
                      return (
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase">Relationship Name</label>
                            <select
                              className="w-full mt-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:border-indigo-500"
                              value={step.relationship_name}
                              onChange={(e) => onUpdateStep(idx, { relationship_name: e.target.value })}
                            >
                              {allowedRels.length === 0 ? (
                                <option value="">-- No matching relationships --</option>
                              ) : (
                                allowedRels.map(r => (
                                  <option key={r.id} value={r.name}>{r.name}</option>
                                ))
                              )}
                            </select>
                          </div>
                          <div />
                          
                          <div>
                            <div className="flex justify-between items-center">
                              <label className="block text-[10px] font-bold text-slate-400 uppercase">From Class</label>
                            </div>
                            <select
                              className="w-full mt-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:border-indigo-500"
                              value={step.from_class}
                              onChange={(e) => {
                                const newFrom = e.target.value;
                                const validRels = tbox.relationships.filter(
                                  r => r.from_class === newFrom && r.to_class === step.to_class
                                );
                                onUpdateStep(idx, { 
                                  from_class: newFrom, 
                                  relationship_name: validRels.length > 0 ? validRels[0].name : "" 
                                });
                              }}
                            >
                              {tbox.classes.map(c => (
                                  <option key={c.name} value={c.name}>{c.name}</option>
                              ))}
                            </select>
                            {/* Variables pills */}
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {editorParameters.map(p => (
                                <button
                                  key={p.name}
                                  type="button"
                                  onClick={() => onUpdateStep(idx, { from_uuid: `{${p.name}}` })}
                                  className="text-[9px] bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-100 rounded px-1"
                                >
                                  {p.name}
                                </button>
                              ))}
                              {step.loop_over && step.loop_var && (
                                <button
                                  type="button"
                                  onClick={() => onUpdateStep(idx, { from_uuid: `{${step.loop_var}}` })}
                                  className="text-[9px] bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-100 rounded px-1 font-bold"
                                >
                                  {step.loop_var} (Loop)
                                </button>
                              )}
                              {editorSteps.slice(0, idx).map(prev => (
                                <button
                                  key={prev.step_id}
                                  type="button"
                                  onClick={() => onUpdateStep(idx, { from_uuid: `{${prev.step_id}.uuid}` })}
                                  className="text-[9px] bg-amber-50 text-amber-600 hover:bg-amber-100 border border-amber-100 rounded px-1"
                                >
                                  {prev.step_id}
                                </button>
                              ))}
                            </div>
                            <div className="flex items-center space-x-1 mt-1.5">
                              <input
                                type="text"
                                className="flex-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500 font-mono"
                                placeholder="From UUID (e.g. {step_1.uuid})"
                                value={step.from_uuid || ""}
                                onChange={(e) => onUpdateStep(idx, { from_uuid: e.target.value })}
                              />
                              <button
                                type="button"
                                onClick={() => openNodeSelector(step.from_class || "", (uuid) => onUpdateStep(idx, { from_uuid: uuid }))}
                                className="px-2 py-1.5 border border-slate-300 bg-white hover:bg-slate-50 rounded-lg text-slate-500"
                              >
                                <Search className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between items-center">
                              <label className="block text-[10px] font-bold text-slate-400 uppercase">To Class</label>
                            </div>
                            <select
                              className="w-full mt-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:border-indigo-500"
                              value={step.to_class}
                              onChange={(e) => {
                                const newTo = e.target.value;
                                const validRels = tbox.relationships.filter(
                                  r => r.from_class === step.from_class && r.to_class === newTo
                                );
                                onUpdateStep(idx, { 
                                  to_class: newTo, 
                                  relationship_name: validRels.length > 0 ? validRels[0].name : "" 
                                });
                              }}
                            >
                              {tbox.classes.map(c => (
                                <option key={c.name} value={c.name}>{c.name}</option>
                              ))}
                            </select>
                            {/* Variables pills */}
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {editorParameters.map(p => (
                                <button
                                  key={p.name}
                                  type="button"
                                  onClick={() => onUpdateStep(idx, { to_uuid: `{${p.name}}` })}
                                  className="text-[9px] bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-100 rounded px-1"
                                >
                                  {p.name}
                                </button>
                              ))}
                              {step.loop_over && step.loop_var && (
                                <button
                                  type="button"
                                  onClick={() => onUpdateStep(idx, { to_uuid: `{${step.loop_var}}` })}
                                  className="text-[9px] bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-100 rounded px-1 font-bold"
                                >
                                  {step.loop_var} (Loop)
                                </button>
                              )}
                              {editorSteps.slice(0, idx).map(prev => (
                                <button
                                  key={prev.step_id}
                                  type="button"
                                  onClick={() => onUpdateStep(idx, { to_uuid: `{${prev.step_id}.uuid}` })}
                                  className="text-[9px] bg-amber-50 text-amber-600 hover:bg-amber-100 border border-amber-100 rounded px-1"
                                >
                                  {prev.step_id}
                                </button>
                              ))}
                            </div>
                            <div className="flex items-center space-x-1 mt-1.5">
                              <input
                                type="text"
                                className="flex-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500 font-mono"
                                placeholder="To UUID (e.g. {step_2.uuid})"
                                value={step.to_uuid || ""}
                                onChange={(e) => onUpdateStep(idx, { to_uuid: e.target.value })}
                              />
                              <button
                                type="button"
                                onClick={() => openNodeSelector(step.to_class || "", (uuid) => onUpdateStep(idx, { to_uuid: uuid }))}
                                className="px-2 py-1.5 border border-slate-300 bg-white hover:bg-slate-50 rounded-lg text-slate-500"
                              >
                                <Search className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })()
                  )}

                  {/* Run Sub-Workflow Step Builder */}
                  {step.action === "run_workflow" && (
                    <div className="space-y-3 text-xs">
                      <div className="grid grid-cols-1 gap-2">
                        <div>
                          <label className="block text-[10px] font-bold text-slate-400 uppercase">Sub-Workflow Name</label>
                          <select
                            className="w-full mt-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:border-indigo-500 font-mono"
                            value={step.workflow_name || ""}
                            onChange={(e) => onUpdateStep(idx, { workflow_name: e.target.value, parameters: {} })}
                          >
                            <option value="">-- Select Sub-Workflow --</option>
                            {workflows.filter(w => w.name !== editorName).map(w => (
                              <option key={w.name} value={w.name}>{w.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                      
                      {/* Sub-workflow parameters mapping */}
                      {step.workflow_name && (() => {
                        const targetWf = workflows.find(w => w.name === step.workflow_name);
                        if (!targetWf || !targetWf.parameters || targetWf.parameters.length === 0) {
                          return <div className="text-[10px] text-slate-400 italic">No parameters required for this sub-workflow.</div>;
                        }
                        return (
                          <div>
                            <span className="block text-[10px] font-bold text-slate-400 uppercase mb-2">Parameter Mappings</span>
                            <div className="bg-white border border-slate-200 rounded-lg p-3 space-y-3">
                              {targetWf.parameters.map(param => (
                                <div key={param.name} className="flex flex-col space-y-1">
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-semibold text-slate-700 truncate font-mono">
                                      {param.name} {param.required && <span className="text-rose-500">*</span>}
                                    </span>
                                    {/* Param pills */}
                                    <div className="flex flex-wrap gap-1">
                                      {editorParameters.map(p => (
                                        <button
                                          key={p.name}
                                          type="button"
                                          onClick={() => {
                                            const newParams = { ...step.parameters, [param.name]: `{${p.name}}` };
                                            onUpdateStep(idx, { parameters: newParams });
                                          }}
                                          className="text-[9px] bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-100 rounded px-1"
                                        >
                                          {p.name}
                                        </button>
                                      ))}
                                      {step.loop_over && step.loop_var && (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const newParams = { ...step.parameters, [param.name]: `{${step.loop_var}}` };
                                            onUpdateStep(idx, { parameters: newParams });
                                          }}
                                          className="text-[9px] bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-100 rounded px-1 font-bold"
                                        >
                                          {step.loop_var} (Loop)
                                        </button>
                                      )}
                                      {editorSteps.slice(0, idx).map(prev => (
                                        <button
                                          key={prev.step_id}
                                          type="button"
                                          onClick={() => {
                                            const newParams = { ...step.parameters, [param.name]: `{${prev.step_id}.uuid}` };
                                            onUpdateStep(idx, { parameters: newParams });
                                          }}
                                          className="text-[9px] bg-amber-50 text-amber-600 hover:bg-amber-100 border border-amber-100 rounded px-1"
                                        >
                                          {prev.step_id}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                  <input
                                    type="text"
                                    className="w-full px-2.5 py-1 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500 font-mono"
                                    placeholder={param.required ? "Required" : "Optional"}
                                    value={step.parameters?.[param.name] || ""}
                                    onChange={(e) => {
                                      const newParams = { ...step.parameters, [param.name]: e.target.value };
                                      onUpdateStep(idx, { parameters: newParams });
                                    }}
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}
                </div>
              );
            })() : (
              <div className="border border-slate-200 border-dashed rounded-xl p-8 text-center text-slate-400 bg-slate-50">
                <Settings className="h-10 w-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-medium">No Step Selected</p>
                <p className="text-xs text-slate-400 mt-1">Click any step node in the visual flowchart above to configure it.</p>
              </div>
            )}
          </div>

          <div className="flex space-x-2 pt-4 border-t border-slate-100">
            <button
              onClick={() => {
                onAddStep("create_node");
                setActiveStepIdx(editorSteps.length);
              }}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 text-slate-600 font-semibold text-xs transition-colors"
            >
              <Plus className="h-4 w-4 text-indigo-500" />
              <span>Add Node Step</span>
            </button>
            <button
              onClick={() => {
                onAddStep("create_relationship");
                setActiveStepIdx(editorSteps.length);
              }}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 text-slate-600 font-semibold text-xs transition-colors"
            >
              <Plus className="h-4 w-4 text-amber-500" />
              <span>Add Link Step</span>
            </button>
            <button
              onClick={() => {
                onAddStep("run_workflow");
                setActiveStepIdx(editorSteps.length);
              }}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 text-slate-600 font-semibold text-xs transition-colors"
            >
              <Plus className="h-4 w-4 text-emerald-500" />
              <span>Add Sub-Workflow</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
