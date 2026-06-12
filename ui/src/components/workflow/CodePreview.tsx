import { useState } from "react";
import { Code } from "lucide-react";
import type { WorkflowStep } from "../../types";

interface CodePreviewProps {
  dslCode: string;
  editorSteps: WorkflowStep[];
}

/** Collapsible Python-DSL + JSON preview of the current editor state. */
export function CodePreview({ dslCode, editorSteps }: CodePreviewProps) {
  const [showCodePreview, setShowCodePreview] = useState(false);

  return (
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
              <pre className="whitespace-pre-wrap">{dslCode}</pre>
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
  );
}
