import { Search, Trash } from "lucide-react";
import type { TBoxClass, TBoxRelationship, Workflow, WorkflowParameter, WorkflowStep } from "../../types";

interface StepConfiguratorProps {
  step: WorkflowStep;
  idx: number;
  classes: TBoxClass[];
  relationships: TBoxRelationship[];
  workflows: Workflow[];
  editorName: string;
  editorParameters: WorkflowParameter[];
  editorSteps: WorkflowStep[];
  expanded: boolean;
  onToggleExpanded: () => void;
  onUpdateStep: (idx: number, fields: Partial<WorkflowStep>) => void;
  onRemoveStep: (idx: number) => void;
  onDeselect: () => void;
  openNodeSelector: (className: string, callback: (uuid: string) => void) => void;
}

/** Configuration panel for the currently-selected step (node / link / sub-workflow). */
export function StepConfigurator({
  step,
  idx,
  classes,
  relationships,
  workflows,
  editorName,
  editorParameters,
  editorSteps,
  expanded,
  onToggleExpanded,
  onUpdateStep,
  onRemoveStep,
  onDeselect,
  openNodeSelector,
}: StepConfiguratorProps) {
  return (
    <div className="border border-slate-200 rounded-xl p-4 bg-slate-50 space-y-4 relative">
      <button
        onClick={() => {
          onRemoveStep(idx);
          onDeselect();
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
          onClick={onToggleExpanded}
          className="text-[10px] bg-slate-200 text-slate-700 hover:bg-slate-300 px-2 py-0.5 rounded transition-colors font-semibold"
        >
          {expanded ? "Hide Advanced Settings" : "⚙️ Advanced Settings"}
        </button>
        {(step.if_present || step.loop_over) && (
          <span className="text-[9px] bg-amber-100 text-amber-800 border border-amber-200 rounded px-1.5 py-0.5 font-bold">
            {step.if_present ? "Conditional" : ""} {step.loop_over ? "Looped" : ""}
          </span>
        )}
      </div>

      {/* Collapsible Advanced Settings Panel */}
      {expanded && (
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
                {editorParameters.map(p => (
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
                {classes.map(c => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <div className="flex justify-between items-center">
                <label className="block text-[10px] font-bold text-slate-400 uppercase">Custom UUID (Optional)</label>
                {/* Variable pills for Custom UUID */}
                {(editorParameters.length > 0 || (step.loop_over && step.loop_var) || idx > 0) && (
                  <div className="flex flex-wrap gap-1">
                    {editorParameters.map(p => (
                      <button
                        key={p.name}
                        type="button"
                        onClick={() => onUpdateStep(idx, { uuid: `{${p.name}}` })}
                        className="text-[9px] bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-100 rounded px-1 cursor-pointer"
                      >
                        {p.name}
                      </button>
                    ))}
                    {step.loop_over && step.loop_var && (
                      <button
                        type="button"
                        onClick={() => onUpdateStep(idx, { uuid: `{${step.loop_var}}` })}
                        className="text-[9px] bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-100 rounded px-1 font-bold cursor-pointer"
                      >
                        {step.loop_var} (Loop)
                      </button>
                    )}
                    {editorSteps.slice(0, idx).map(prev => (
                      <button
                        key={prev.step_id}
                        type="button"
                        onClick={() => onUpdateStep(idx, { uuid: `{${prev.step_id}.uuid}` })}
                        className="text-[9px] bg-amber-50 text-amber-600 hover:bg-amber-100 border border-amber-100 rounded px-1 cursor-pointer"
                      >
                        {prev.step_id}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center space-x-1 mt-1">
                <input
                  type="text"
                  className="flex-1 px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:border-indigo-500 font-mono"
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
              {classes.find(c => c.name === step.class_name)?.properties.map(prop => (
                <div key={prop.name} className="flex flex-col space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700 truncate">
                      {prop.name} {prop.required && <span className="text-rose-500">*</span>}
                    </span>
                    {/* Param quick pills */}
                    {(editorParameters.length > 0 || (step.loop_over && step.loop_var) || idx > 0) && (
                      <div className="flex flex-wrap gap-1">
                        {editorParameters.map(p => (
                          <button
                            key={p.name}
                            type="button"
                            onClick={() => {
                              const newProps = { ...step.properties, [prop.name]: `{${p.name}}` };
                              onUpdateStep(idx, { properties: newProps });
                            }}
                            className="text-[9px] bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-100 rounded px-1 cursor-pointer"
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
                            className="text-[9px] bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-100 rounded px-1 font-bold cursor-pointer"
                            title={`Use Loop Variable ${step.loop_var}`}
                          >
                            {step.loop_var} (Loop)
                          </button>
                        )}
                        {editorSteps.slice(0, idx).map(prev => (
                          <button
                            key={prev.step_id}
                            type="button"
                            onClick={() => {
                              const newProps = { ...step.properties, [prop.name]: `{${prev.step_id}.uuid}` };
                              onUpdateStep(idx, { properties: newProps });
                            }}
                            className="text-[9px] bg-amber-50 text-amber-600 hover:bg-amber-100 border border-amber-100 rounded px-1 cursor-pointer font-medium"
                            title={`Use ${prev.step_id} UUID`}
                          >
                            {prev.step_id}
                          </button>
                        ))}
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
          const allowedRels = relationships.filter(
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
                    const validRels = relationships.filter(
                      r => r.from_class === newFrom && r.to_class === step.to_class
                    );
                    onUpdateStep(idx, {
                      from_class: newFrom,
                      relationship_name: validRels.length > 0 ? validRels[0].name : ""
                    });
                  }}
                >
                  {classes.map(c => (
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
                    const validRels = relationships.filter(
                      r => r.from_class === step.from_class && r.to_class === newTo
                    );
                    onUpdateStep(idx, {
                      to_class: newTo,
                      relationship_name: validRels.length > 0 ? validRels[0].name : ""
                    });
                  }}
                >
                  {classes.map(c => (
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
}
