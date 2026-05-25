import React, { useState, useEffect } from "react";
import { X, Search, RefreshCw } from "lucide-react";

interface NodeSelectorModalProps {
  isOpen: boolean;
  targetClass: string;
  onClose: () => void;
  onSelect: (uuid: string) => void;
}

export function NodeSelectorModal({ isOpen, targetClass, onClose, onSelect }: NodeSelectorModalProps) {
  const [nodes, setNodes] = useState<{ uuid: string; display_name: string; properties: any }[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (isOpen && targetClass) {
      fetchNodes();
    }
  }, [isOpen, targetClass]);

  const fetchNodes = async () => {
    setLoading(true);
    setSearch("");
    try {
      const res = await fetch(`/api/abox/nodes/${targetClass}`);
      const data = await res.json();
      setNodes(data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const filteredNodes = nodes.filter(node => 
    node.display_name.toLowerCase().includes(search.toLowerCase()) ||
    node.uuid.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-lg w-full p-6 shadow-xl border border-slate-200 flex flex-col max-h-[500px]">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-slate-900">
            Select {targetClass} Node
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        
        {/* Search Bar */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            className="w-full pl-9 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
            placeholder="Search by name, uuid..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Nodes List */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {loading ? (
            <div className="py-8 text-center text-sm text-slate-400 flex items-center justify-center space-x-2">
              <RefreshCw className="h-4 w-4 animate-spin text-indigo-500" />
              <span>Loading nodes...</span>
            </div>
          ) : filteredNodes.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-400 italic">
              No {targetClass} nodes found.
            </div>
          ) : (
            filteredNodes.map((node) => (
              <button
                key={node.uuid}
                onClick={() => onSelect(node.uuid)}
                className="w-full text-left p-3 border border-slate-200 hover:border-indigo-500 hover:bg-indigo-50/20 rounded-lg transition-colors flex justify-between items-center"
              >
                <div>
                  <span className="block text-sm font-semibold text-slate-900">{node.display_name}</span>
                  <span className="block text-[10px] text-slate-400 font-mono mt-0.5">{node.uuid}</span>
                </div>
                <span className="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100 uppercase">
                  Select
                </span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
