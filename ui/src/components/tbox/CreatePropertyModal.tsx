import { useState } from "react";

interface CreatePropertyModalProps {
  onClose: () => void;
  onCreateProperty: (name: string, datatype: string, desc: string) => Promise<boolean>;
}

const DATATYPES = ["string", "integer", "float", "boolean", "date", "datetime", "email", "url", "phone", "uuid", "json"];

/** Modal form to create a global TBox PropertyDef. */
export function CreatePropertyModal({ onClose, onCreateProperty }: CreatePropertyModalProps) {
  const [name, setName] = useState("");
  const [datatype, setDatatype] = useState("string");
  const [desc, setDesc] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onCreateProperty(name, datatype, desc);
    if (ok) onClose();
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Create TBox Property</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Property Name (e.g. channel_code)</label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Datatype</label>
            <select
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
              value={datatype}
              onChange={(e) => setDatatype(e.target.value)}
            >
              {DATATYPES.map((dt) => (
                <option key={dt} value={dt}>{dt}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Description</label>
            <textarea
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
              rows={3}
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
            />
          </div>
          <div className="flex justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={onClose}
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
  );
}
