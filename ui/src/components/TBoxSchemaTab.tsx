import { useState } from "react";
import { RefreshCw, Plus, Activity, Database, Cable, Link2 } from "lucide-react";
import type {
  TBoxClass,
  TBoxInterface,
  TBoxRelationship,
  ConnectorDef,
  SourceBinding,
} from "../types";

interface TBoxSchemaTabProps {
  tbox: {
    classes: TBoxClass[];
    interfaces: TBoxInterface[];
    properties: any[];
    relationships: TBoxRelationship[];
    constraints: any[];
    connectors?: ConnectorDef[];
    source_bindings?: SourceBinding[];
  };
  loading: boolean;
  onRefresh: () => void;
  onCreateClass: (name: string, label: string, desc: string) => Promise<boolean>;
  onCreateProperty: (name: string, datatype: string, desc: string) => Promise<boolean>;
  onAttachProperty: (className: string, propName: string, req: boolean, uniq: boolean) => Promise<boolean>;
  onCreateRelationship: (id: string, name: string, fromClass: string, toClass: string, req: boolean) => Promise<boolean>;
}

export function TBoxSchemaTab({
  tbox,
  loading,
  onRefresh,
  onCreateClass,
  onCreateProperty,
  onAttachProperty,
  onCreateRelationship
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
    </div>
  );
}
