import { useState } from "react";
import type { TBoxClass } from "../../types";

interface DefineRelationshipModalProps {
  classes: TBoxClass[];
  onClose: () => void;
  onCreateRelationship: (id: string, name: string, fromClass: string, toClass: string, req: boolean) => Promise<boolean>;
}

/** Modal form to define an allowed relationship between two classes. */
export function DefineRelationshipModal({ classes, onClose, onCreateRelationship }: DefineRelationshipModalProps) {
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [fromClass, setFromClass] = useState("");
  const [toClass, setToClass] = useState("");
  const [required, setRequired] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await onCreateRelationship(id, name, fromClass, toClass, required);
    if (ok) onClose();
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl border border-slate-200">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Define Relationship</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Relationship ID (e.g. rel_team_organized_event)</label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
              value={id}
              onChange={(e) => setId(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Relationship Name (e.g. ORGANIZED)</label>
            <input
              type="text"
              required
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">From Class</label>
              <select
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                value={fromClass}
                onChange={(e) => setFromClass(e.target.value)}
              >
                <option value="">-- From --</option>
                {classes.map(c => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">To Class</label>
              <select
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 bg-white"
                value={toClass}
                onChange={(e) => setToClass(e.target.value)}
              >
                <option value="">-- To --</option>
                {classes.map(c => (
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
                checked={required}
                onChange={(e) => setRequired(e.target.checked)}
              />
              <span>Required Relationship</span>
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
              className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700"
            >
              Define
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
