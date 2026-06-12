import { useState } from "react";
import { Plus, Settings, Trash, Variable } from "lucide-react";
import type { TBoxClass, WorkflowParameter } from "../../types";

interface ParamManagerProps {
  classes: TBoxClass[];
  editorParameters: WorkflowParameter[];
  parameterTypes: string[];
  onAddParameter: (p: WorkflowParameter) => boolean;
  onRemoveParameter: (name: string) => void;
  onSaveEditedParam: (idx: number, p: WorkflowParameter) => boolean | Promise<boolean>;
}

/** Declared input-parameter schema editor (list + add form + inline edit). */
export function ParamManager({
  classes,
  editorParameters,
  parameterTypes,
  onAddParameter,
  onRemoveParameter,
  onSaveEditedParam,
}: ParamManagerProps) {
  // Add-parameter form state
  const [newParamName, setNewParamName] = useState("");
  const [newParamType, setNewParamType] = useState("string");
  const [newParamDesc, setNewParamDesc] = useState("");
  const [newParamRequired, setNewParamRequired] = useState(true);
  const [newParamItemType, setNewParamItemType] = useState("string");
  const [newParamItemClass, setNewParamItemClass] = useState("");

  // Inline-edit form state
  const [editingParamIdx, setEditingParamIdx] = useState<number | null>(null);
  const [editParamName, setEditParamName] = useState("");
  const [editParamType, setEditParamType] = useState("string");
  const [editParamDesc, setEditParamDesc] = useState("");
  const [editParamRequired, setEditParamRequired] = useState(true);
  const [editParamItemType, setEditParamItemType] = useState("string");
  const [editParamItemClass, setEditParamItemClass] = useState("");

  const handleAddParam = () => {
    if (!newParamName) return;
    const ok = onAddParameter({
      name: newParamName,
      type: newParamType,
      required: newParamRequired,
      description: newParamDesc,
      array_item_type: newParamType === "array" ? newParamItemType : undefined,
      array_item_class: newParamType === "array" && newParamItemType === "uuid" ? newParamItemClass || classes[0]?.name : undefined,
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
    setEditParamItemClass(p.array_item_class || (classes[0]?.name || ""));
  };

  const handleSaveEditParam = async (idx: number) => {
    if (!editParamName) return;
    const ok = await onSaveEditedParam(idx, {
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
                          {parameterTypes.map(t => (
                            <option key={t} value={t}>{t}</option>
                          ))}
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
                              {classes.map(c => (
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
            {parameterTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
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
                  {classes.map(c => (
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
  );
}
