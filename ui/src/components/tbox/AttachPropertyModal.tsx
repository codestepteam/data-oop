import { useState } from "react";
import type { TBoxClass } from "../../types";

interface AttachPropertyModalProps {
  classes: TBoxClass[];
  properties: { name: string }[];
  onClose: () => void;
  onAttachProperty: (className: string, propName: string, req: boolean, uniq: boolean) => Promise<boolean>;
}

/** Modal form to attach a global property to a class as required/unique. */
export function AttachPropertyModal({ classes, properties, onClose, onAttachProperty }: AttachPropertyModalProps) {
  const [className, setClassName] = useState("");
  const [propName, setPropName] = useState("");
  const [required, setRequired] = useState(false);
  const [unique, setUnique] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onAttachProperty(className, propName, required, unique);
    if (ok) onClose();
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Attach Property to Class</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Class</label>
            <select
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
              value={className}
              onChange={(e) => setClassName(e.target.value)}
            >
              <option value="">-- Select Class --</option>
              {classes.map(c => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Property</label>
            <select
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
              value={propName}
              onChange={(e) => setPropName(e.target.value)}
            >
              <option value="">-- Select Property --</option>
              {properties.map(p => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="flex space-x-4 pt-2">
            <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                checked={required}
                onChange={(e) => setRequired(e.target.checked)}
              />
              <span>Required</span>
            </label>
            <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                className="rounded text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                checked={unique}
                onChange={(e) => setUnique(e.target.checked)}
              />
              <span>Unique</span>
            </label>
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
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700"
            >
              Attach
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
