import { CheckCircle, AlertTriangle, RefreshCw } from "lucide-react";
import type { ValidationRun, ValidationIssue, AboxCount, AboxNode } from "../types";

interface ValidationTabProps {
  validationRun: ValidationRun | null;
  validationIssues: ValidationIssue[];
  validating: boolean;
  aboxCounts: AboxCount[];
  aboxNodes: AboxNode[];
  onRunValidation: () => void;
  onRefreshStats: () => void;
}

export function ValidationTab({
  validationRun,
  validationIssues,
  validating,
  aboxCounts,
  aboxNodes,
  onRunValidation,
  onRefreshStats
}: ValidationTabProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Validation Trigger Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between">
          <div>
            <h3 className="font-bold text-slate-900 text-lg mb-2">ABox Validation</h3>
            <p className="text-sm text-slate-500">Run constraint validation checks on active ABox instances against the TBox model.</p>
            
            {validationRun && (
              <div className="mt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Latest Run Status:</span>
                  <span className={`flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                    validationRun.status === "passed" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-rose-50 text-rose-700 border border-rose-200"
                  }`}>
                    {validationRun.status === "passed" ? <CheckCircle className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                    <span>{validationRun.status.toUpperCase()}</span>
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Checked Instances:</span>
                  <span className="font-semibold">{validationRun.checked_instance_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Errors found:</span>
                  <span className={`font-semibold ${validationRun.error_count > 0 ? "text-rose-600" : "text-slate-700"}`}>
                    {validationRun.error_count}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Warnings found:</span>
                  <span className={`font-semibold ${validationRun.warning_count > 0 ? "text-amber-600" : "text-slate-700"}`}>
                    {validationRun.warning_count}
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="mt-8">
            <button
              onClick={onRunValidation}
              disabled={validating}
              className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:bg-slate-300 transition-colors"
            >
              <RefreshCw className={`h-4 w-4 ${validating ? "animate-spin" : ""}`} />
              <span>{validating ? "Validating..." : "Run Validation"}</span>
            </button>
          </div>
        </div>

        {/* ABox Instance Stats */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 lg:col-span-2">
          <h3 className="font-bold text-slate-900 text-lg mb-4 flex items-center justify-between">
            <span>ABox Node Count Summary</span>
            <button onClick={onRefreshStats} className="p-1 hover:bg-slate-100 rounded-lg text-slate-500">
              <RefreshCw className="h-4 w-4" />
            </button>
          </h3>
          {aboxCounts.length === 0 ? (
            <p className="text-sm text-slate-400 italic">No ABox nodes exist in the graph yet.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {aboxCounts.map((c) => (
                <div key={c.label} className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                  <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">{c.label}</span>
                  <span className="block text-2xl font-extrabold text-slate-900 mt-1">{c.count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Validation Issues Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="font-bold text-slate-950 text-lg m-0">Validation Issues ({validationIssues.length})</h3>
        </div>
        {validationIssues.length === 0 ? (
          <div className="p-8 text-center text-slate-400 italic">
            <CheckCircle className="h-12 w-12 text-emerald-400 mx-auto mb-3" />
            <span>No validation issues found. Graph is clean!</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                  <th className="px-6 py-3">Severity</th>
                  <th className="px-6 py-3">Code</th>
                  <th className="px-6 py-3">Class/Instance</th>
                  <th className="px-6 py-3">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-sm">
                {validationIssues.map((issue) => (
                  <tr key={issue.id} className="hover:bg-slate-50/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-bold border ${
                        issue.severity === "error" ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-amber-50 text-amber-700 border-amber-200"
                      }`}>
                        {issue.severity === "error" ? <AlertTriangle className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3 text-amber-500" />}
                        <span>{issue.severity.toUpperCase()}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-slate-500">
                      {issue.code}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-semibold text-slate-900">{issue.className || "-"}</span>
                      {issue.instanceUuid && (
                        <span className="block text-xs text-slate-400 font-mono mt-0.5">{issue.instanceUuid}</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-600 font-medium">
                      {issue.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ABox Instance Preview */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="font-bold text-slate-900 text-lg m-0">ABox Node Preview (Latest 100)</h3>
        </div>
        {aboxNodes.length === 0 ? (
          <div className="p-8 text-center text-slate-400 italic">No ABox nodes found.</div>
        ) : (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {aboxNodes.map((node) => (
              <div key={node.uuid} className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-bold bg-slate-200 text-slate-700 px-2 py-0.5 rounded">
                    {node.label}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">{node.uuid}</span>
                </div>
                <div className="space-y-1 mt-3">
                  {Object.entries(node.properties || {}).map(([key, val]) => (
                    <div key={key} className="text-xs flex justify-between">
                      <span className="text-slate-400">{key}:</span>
                      <span className="text-slate-800 font-semibold truncate max-w-[150px]">{String(val)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
