import { useState, useEffect } from "react";
import { RefreshCw, Plus, Activity, Database, Cable, Link2, Zap, Trash2, AlertTriangle, Gauge } from "lucide-react";
import type {
  TBoxClass,
  TBoxInterface,
  TBoxRelationship,
  ConnectorDef,
  SourceBinding,
  MetricDef,
  TriggerDef,
  TriggerGraphReport,
} from "../types";
import type { TriggerInput } from "../hooks/useTBox";

interface TBoxSchemaTabProps {
  tbox: {
    classes: TBoxClass[];
    interfaces: TBoxInterface[];
    properties: any[];
    relationships: TBoxRelationship[];
    constraints: any[];
    connectors?: ConnectorDef[];
    source_bindings?: SourceBinding[];
    metrics?: MetricDef[];
    triggers?: TriggerDef[];
  };
  loading: boolean;
  onRefresh: () => void;
  onCreateClass: (name: string, label: string, desc: string) => Promise<boolean>;
  onCreateProperty: (name: string, datatype: string, desc: string) => Promise<boolean>;
  onAttachProperty: (className: string, propName: string, req: boolean, uniq: boolean) => Promise<boolean>;
  onCreateRelationship: (id: string, name: string, fromClass: string, toClass: string, req: boolean) => Promise<boolean>;
  onCreateTrigger: (input: TriggerInput) => Promise<{ ok: boolean; error?: string; cycles?: string[][] }>;
  onDeleteTrigger: (className: string, name: string) => Promise<boolean>;
  onValidateTriggers: (candidate?: TriggerInput) => Promise<TriggerGraphReport | null>;
}

export function TBoxSchemaTab({
  tbox,
  loading,
  onRefresh,
  onCreateClass,
  onCreateProperty,
  onAttachProperty,
  onCreateRelationship,
  onCreateTrigger,
  onDeleteTrigger,
  onValidateTriggers
}: TBoxSchemaTabProps) {
  // Modals visibility
  const [showCreateClass, setShowCreateClass] = useState(false);
  const [showCreateProp, setShowCreateProp] = useState(false);
  const [showAttachProp, setShowAttachProp] = useState(false);
  const [showCreateRel, setShowCreateRel] = useState(false);

  // Class form
  const [newClassName, setNewClassName] = useState("");
  const [newClassLabel, setNewClassLabel] = useState("");
  const [newClassDesc, setNewClassDesc] = useState("");

  // Property form
  const [newPropName, setNewPropName] = useState("");
  const [newPropDatatype, setNewPropDatatype] = useState("string");
  const [newPropDesc, setNewPropDesc] = useState("");

  // Attach form
  const [attachClassName, setAttachClassName] = useState("");
  const [attachPropName, setAttachPropName] = useState("");
  const [attachRequired, setAttachRequired] = useState(false);
  const [attachUnique, setAttachUnique] = useState(false);

  // Relationship form
  const [newRelId, setNewRelId] = useState("");
  const [newRelName, setNewRelName] = useState("");
  const [newRelFrom, setNewRelFrom] = useState("");
  const [newRelTo, setNewRelTo] = useState("");
  const [newRelRequired, setNewRelRequired] = useState(false);

  // Trigger form
  const [showCreateTrigger, setShowCreateTrigger] = useState(false);
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

  // Workflow names power the trigger's "run this workflow" dropdown.
  useEffect(() => {
    if (!showCreateTrigger) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/workflows");
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
  }, [showCreateTrigger]);

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

  const resetTriggerForm = () => {
    setTrgClass("");
    setTrgName("");
    setTrgEvent("create");
    setTrgWorkflow("");
    setTrgCondition("");
    setTrgOrder(0);
    setTrgDesc("");
    setTrgParams([]);
    setTrgError(null);
    setTrgReport(null);
  };

  const handleTriggerPreview = async () => {
    setTrgError(null);
    if (!trgClass || !trgName || !trgWorkflow) {
      setTrgError("Class, name and workflow are required to validate.");
      return;
    }
    const report = await onValidateTriggers(triggerInput());
    setTrgReport(report);
  };

  const handleTriggerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTrgError(null);
    const result = await onCreateTrigger(triggerInput());
    if (result.ok) {
      setShowCreateTrigger(false);
      resetTriggerForm();
      return;
    }
    if (result.cycles && result.cycles.length > 0) {
      setTrgError(
        `Trigger cycle detected: ${result.cycles.map((c) => c.join(" → ")).join("; ")}`
      );
    } else {
      setTrgError(result.error || "Failed to create trigger.");
    }
  };

  const handleClassSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onCreateClass(newClassName, newClassLabel || newClassName, newClassDesc);
    if (ok) {
      setShowCreateClass(false);
      setNewClassName("");
      setNewClassLabel("");
      setNewClassDesc("");
    }
  };

  const handlePropertySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onCreateProperty(newPropName, newPropDatatype, newPropDesc);
    if (ok) {
      setShowCreateProp(false);
      setNewPropName("");
      setNewPropDesc("");
    }
  };

  const handleAttachSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onAttachProperty(attachClassName, attachPropName, attachRequired, attachUnique);
    if (ok) {
      setShowAttachProp(false);
      setAttachClassName("");
      setAttachPropName("");
      setAttachRequired(false);
      setAttachUnique(false);
    }
  };

  const handleRelationshipSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onCreateRelationship(newRelId, newRelName, newRelFrom, newRelTo, newRelRequired);
    if (ok) {
      setShowCreateRel(false);
      setNewRelId("");
      setNewRelName("");
      setNewRelFrom("");
      setNewRelTo("");
      setNewRelRequired(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 m-0">TBox Definitions</h2>
          <p className="text-sm text-slate-500 mt-1">Current Class, Interface, Property and Relationship schemas.</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={onRefresh}
            className="flex items-center space-x-1 px-3 py-1.5 border border-slate-300 rounded-lg text-sm font-medium bg-slate-50 text-slate-700 hover:bg-slate-100"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowCreateClass(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            <span>Create Class</span>
          </button>
          <button
            onClick={() => setShowCreateProp(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700"
          >
            <Plus className="h-4 w-4" />
            <span>Create Property</span>
          </button>
          <button
            onClick={() => setShowAttachProp(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700"
          >
            <Plus className="h-4 w-4" />
            <span>Attach Prop</span>
          </button>
          <button
            onClick={() => setShowCreateRel(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700"
          >
            <Plus className="h-4 w-4" />
            <span>Define Relation</span>
          </button>
          <button
            onClick={() => { resetTriggerForm(); setShowCreateTrigger(true); }}
            className="flex items-center space-x-1 px-3 py-1.5 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700"
          >
            <Zap className="h-4 w-4" />
            <span>Add Trigger</span>
          </button>
        </div>
      </div>

      {/* Create Class Modal Overlay */}
      {showCreateClass && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">Create TBox Class</h3>
            <form onSubmit={handleClassSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Class Name (e.g. SalesChannel)</label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  value={newClassName}
                  onChange={(e) => setNewClassName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Label (e.g. SalesChannel)</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  value={newClassLabel}
                  onChange={(e) => setNewClassLabel(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Description</label>
                <textarea
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  rows={3}
                  value={newClassDesc}
                  onChange={(e) => setNewClassDesc(e.target.value)}
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateClass(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-slate-50 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Property Modal Overlay */}
      {showCreateProp && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">Create TBox Property</h3>
            <form onSubmit={handlePropertySubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Property Name (e.g. channel_code)</label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  value={newPropName}
                  onChange={(e) => setNewPropName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Datatype</label>
                <select
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                  value={newPropDatatype}
                  onChange={(e) => setNewPropDatatype(e.target.value)}
                >
                  <option value="string">string</option>
                  <option value="integer">integer</option>
                  <option value="float">float</option>
                  <option value="boolean">boolean</option>
                  <option value="date">date</option>
                  <option value="datetime">datetime</option>
                  <option value="email">email</option>
                  <option value="url">url</option>
                  <option value="phone">phone</option>
                  <option value="uuid">uuid</option>
                  <option value="json">json</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Description</label>
                <textarea
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  rows={3}
                  value={newPropDesc}
                  onChange={(e) => setNewPropDesc(e.target.value)}
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateProp(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-slate-50 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Attach Property Modal Overlay */}
      {showAttachProp && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">Attach Property to Class</h3>
            <form onSubmit={handleAttachSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Class</label>
                <select
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                  value={attachClassName}
                  onChange={(e) => setAttachClassName(e.target.value)}
                >
                  <option value="">-- Select Class --</option>
                  {tbox.classes.map(c => (
                    <option key={c.name} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Property</label>
                <select
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                  value={attachPropName}
                  onChange={(e) => setAttachPropName(e.target.value)}
                >
                  <option value="">-- Select Property --</option>
                  {tbox.properties.map(p => (
                    <option key={p.name} value={p.name}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex space-x-4 pt-2">
                <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                    checked={attachRequired}
                    onChange={(e) => setAttachRequired(e.target.checked)}
                  />
                  <span>Required</span>
                </label>
                <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                    checked={attachUnique}
                    onChange={(e) => setAttachUnique(e.target.checked)}
                  />
                  <span>Unique</span>
                </label>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAttachProp(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-slate-50 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700"
                >
                  Attach
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Define Relationship Modal Overlay */}
      {showCreateRel && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">Define Relationship</h3>
            <form onSubmit={handleRelationshipSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Relationship ID (e.g. rel_team_organized_event)</label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  value={newRelId}
                  onChange={(e) => setNewRelId(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Relationship Name (e.g. ORGANIZED)</label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  value={newRelName}
                  onChange={(e) => setNewRelName(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">From Class</label>
                  <select
                    required
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                    value={newRelFrom}
                    onChange={(e) => setNewRelFrom(e.target.value)}
                  >
                    <option value="">-- From --</option>
                    {tbox.classes.map(c => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">To Class</label>
                  <select
                    required
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                    value={newRelTo}
                    onChange={(e) => setNewRelTo(e.target.value)}
                  >
                    <option value="">-- To --</option>
                    {tbox.classes.map(c => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    className="rounded text-violet-600 focus:ring-violet-500 h-4 w-4"
                    checked={newRelRequired}
                    onChange={(e) => setNewRelRequired(e.target.checked)}
                  />
                  <span>Required Relationship</span>
                </label>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateRel(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-slate-50 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700"
                >
                  Define
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Grid of Classes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tbox.classes.map((cls) => (
          <div key={cls.name} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
            <div className="bg-slate-50 border-b border-slate-200 p-4">
              <div className="flex justify-between items-start">
                <h3 className="font-bold text-slate-900 text-base m-0">{cls.name}</h3>
                <span className="bg-indigo-50 text-indigo-700 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-indigo-100">
                  Class
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-2 italic">{cls.description || "No description provided."}</p>
            </div>
            <div className="p-4 flex-1 space-y-3">
              <div>
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Properties ({cls.properties.length})</h4>
                {cls.properties.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No properties attached.</p>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {cls.properties.map((prop) => (
                      <div key={prop.name} className="py-2 flex items-center justify-between">
                        <div>
                          <span className="text-sm font-semibold text-slate-800">{prop.name}</span>
                          <span className="text-xs text-slate-400 ml-1.5">({prop.datatype})</span>
                        </div>
                        <div className="flex space-x-1.5">
                          {prop.required && (
                            <span className="bg-rose-50 text-rose-700 text-[10px] font-bold px-1.5 py-0.5 rounded border border-rose-100">
                              Req
                            </span>
                          )}
                          {prop.unique && (
                            <span className="bg-amber-50 text-amber-700 text-[10px] font-bold px-1.5 py-0.5 rounded border border-amber-100">
                              Uniq
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Relationships and Properties Pool */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Allowed Relationships */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Activity className="h-5 w-5 text-violet-500" />
            <span>Allowed Relationships ({tbox.relationships.length})</span>
          </h3>
          {tbox.relationships.length === 0 ? (
            <p className="text-sm text-slate-400 italic">No relationships defined.</p>
          ) : (
            <div className="space-y-3">
              {tbox.relationships.map((rel) => (
                <div key={rel.id} className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-900">{rel.from_class}</span>
                      <span className="text-xs font-mono bg-violet-100 text-violet-800 px-2 py-0.5 rounded-md border border-violet-200">
                        -{rel.name}-&gt;
                      </span>
                      <span className="text-sm font-bold text-slate-900">{rel.to_class}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">ID: {rel.id}</p>
                  </div>
                  {rel.required && (
                    <span className="bg-rose-50 text-rose-700 text-xs font-bold px-2 py-0.5 rounded border border-rose-100">
                      Required
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Global Properties Definitions */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Database className="h-5 w-5 text-sky-500" />
            <span>Global Property Definitions ({tbox.properties.length})</span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {tbox.properties.map((prop) => (
              <div key={prop.name} className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-sm flex items-center space-x-2">
                <span className="font-semibold text-slate-800">{prop.name}</span>
                <span className="text-xs text-slate-400">({prop.datatype})</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* External RDB Connectors & Source Bindings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connectors */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Cable className="h-5 w-5 text-cyan-500" />
            <span>External RDB Connectors ({(tbox.connectors ?? []).length})</span>
          </h3>
          {(tbox.connectors ?? []).length === 0 ? (
            <p className="text-sm text-slate-400 italic">No connectors defined.</p>
          ) : (
            <div className="space-y-3">
              {(tbox.connectors ?? []).map((conn) => (
                <div key={conn.name} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-900">{conn.name}</span>
                    <span className="text-xs font-mono bg-cyan-100 text-cyan-800 px-2 py-0.5 rounded-md border border-cyan-200">
                      {conn.kind}
                    </span>
                  </div>
                  {conn.dsn_ref && (
                    <p className="text-xs text-slate-500 mt-1">
                      DSN env: <span className="font-mono">{conn.dsn_ref}</span>
                    </p>
                  )}
                  {conn.description && (
                    <p className="text-xs text-slate-400 mt-1 italic">{conn.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Source Bindings */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Database className="h-5 w-5 text-amber-500" />
            <span>Source Bindings ({(tbox.source_bindings ?? []).length})</span>
          </h3>
          {(tbox.source_bindings ?? []).length === 0 ? (
            <p className="text-sm text-slate-400 italic">No source bindings configured.</p>
          ) : (
            <div className="space-y-3">
              {(tbox.source_bindings ?? []).map((b) => (
                <div key={b.class_name} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-900">{b.class_name}</span>
                      <span className="text-xs text-slate-400">←</span>
                      <span className="text-xs font-mono bg-amber-100 text-amber-800 px-2 py-0.5 rounded-md border border-amber-200">
                        {b.connector_name}
                      </span>
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase">{b.materialization}</span>
                  </div>
                  <p className="text-[11px] font-mono text-slate-500 mt-2 line-clamp-2 break-all">{b.sql}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {b.key_columns.map((k) => (
                      <span key={k} className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                        key: {k}
                      </span>
                    ))}
                    {b.refresh_interval_hours != null && (
                      <span className="text-[10px] text-slate-500 px-1.5 py-0.5">⟳ {b.refresh_interval_hours}h</span>
                    )}
                  </div>
                  {b.links.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {b.links.map((link, i) => (
                        <div key={i} className="flex items-center space-x-1 text-[11px] text-slate-600">
                          <Link2 className="h-3 w-3 text-emerald-500" />
                          <span className="font-mono">
                            {link.direction === "out"
                              ? `${b.class_name} -${link.relationship_name}→ ${link.to_class}`
                              : `${link.to_class} -${link.relationship_name}→ ${b.class_name}`}
                          </span>
                          <span className="text-slate-400">({link.local_key}={link.target_property})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* On-demand Metrics (value stays in RDB; graph stores only the query spec) */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
          <Gauge className="h-5 w-5 text-violet-500" />
          <span>On-demand Metrics ({(tbox.metrics ?? []).length})</span>
        </h3>
        {(tbox.metrics ?? []).length === 0 ? (
          <p className="text-sm text-slate-400 italic">No metrics defined.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {(tbox.metrics ?? []).map((m) => (
              <div key={m.name} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-slate-900">{m.name}</span>
                    <span className="text-xs text-slate-400">on</span>
                    <span className="text-xs font-mono text-slate-600">{m.class_name}</span>
                  </div>
                  <span className="text-[10px] font-mono bg-violet-100 text-violet-800 px-2 py-0.5 rounded-md border border-violet-200">
                    {m.result_kind}
                  </span>
                </div>
                <div className="flex items-center space-x-2 mt-1">
                  <span className="text-xs text-slate-400">←</span>
                  <span className="text-xs font-mono bg-amber-100 text-amber-800 px-2 py-0.5 rounded-md border border-amber-200">
                    {m.connector_name}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {m.ttl_seconds != null ? `cache ${m.ttl_seconds}s` : "live"}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-slate-500 mt-2 line-clamp-2 break-all">{m.sql}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {Object.entries(m.param_map).map(([k, v]) => (
                    <span key={k} className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                      {k}={v}
                    </span>
                  ))}
                </div>
                {m.description && (
                  <p className="text-xs text-slate-400 mt-1 italic">{m.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Triggers (class-level callbacks: on create/update -> run workflow) */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
          <Zap className="h-5 w-5 text-rose-500" />
          <span>Triggers ({(tbox.triggers ?? []).length})</span>
          <span className="text-xs font-normal text-slate-400">— on create/update, run a workflow</span>
        </h3>
        {(tbox.triggers ?? []).length === 0 ? (
          <p className="text-sm text-slate-400 italic">No triggers registered.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {(tbox.triggers ?? []).map((t) => (
              <div
                key={`${t.class_name}:${t.name}`}
                className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-start justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center space-x-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-900">{t.name}</span>
                    {!t.enabled && (
                      <span className="text-[10px] uppercase font-semibold text-slate-400 border border-slate-300 rounded px-1">
                        disabled
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-1 text-[12px] text-slate-600 mt-1 flex-wrap">
                    <span className="font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">{t.class_name}</span>
                    <span className="text-slate-400">on</span>
                    <span className="font-mono bg-rose-100 text-rose-800 px-1.5 py-0.5 rounded border border-rose-200">{t.event}</span>
                    <span className="text-slate-400">→</span>
                    <span className="font-mono bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded border border-indigo-200">{t.workflow_name}</span>
                  </div>
                  {t.condition && (
                    <p className="text-[11px] text-slate-500 mt-1">
                      if <span className="font-mono">{t.condition}</span>
                    </p>
                  )}
                  {t.parameter_map && Object.keys(t.parameter_map).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {Object.entries(t.parameter_map).map(([k, v]) => (
                        <span key={k} className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                          {k}={String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                  {t.description && <p className="text-[11px] text-slate-400 mt-1 italic">{t.description}</p>}
                </div>
                <button
                  onClick={() => onDeleteTrigger(t.class_name, t.name)}
                  className="ml-2 shrink-0 text-slate-400 hover:text-rose-600"
                  title="Delete trigger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Trigger Modal */}
      {showCreateTrigger && (
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
            <form onSubmit={handleTriggerSubmit} className="space-y-4">
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
                    {tbox.classes.map((c) => (
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
                  onClick={handleTriggerPreview}
                  className="px-3 py-2 border border-slate-300 rounded-lg text-sm font-medium bg-slate-50 text-slate-700 hover:bg-slate-100"
                >
                  Validate
                </button>
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={() => { setShowCreateTrigger(false); resetTriggerForm(); }}
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
      )}
    </div>
  );
}
