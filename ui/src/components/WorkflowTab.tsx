import { useState, useEffect, useMemo } from "react";
import { Plus, Save, Settings } from "lucide-react";
import "@xyflow/react/dist/style.css";
import type { Workflow, WorkflowStep, WorkflowParameter, TBoxClass, TBoxRelationship, RunResult } from "../types";
import { buildFlowEdges, buildFlowNodes, computeStepPositions } from "./workflow/layout";
import { WorkflowList } from "./workflow/WorkflowList";
import { RunPanel } from "./workflow/RunPanel";
import { CodePreview } from "./workflow/CodePreview";
import { ParamManager } from "./workflow/ParamManager";
import { WorkflowCanvas } from "./workflow/WorkflowCanvas";
import { StepConfigurator } from "./workflow/StepConfigurator";

interface WorkflowTabProps {
  tbox: {
    classes: TBoxClass[];
    relationships: TBoxRelationship[];
  };
  workflows: Workflow[];
  loadingWorkflows: boolean;
  selectedWorkflow: Workflow | null;
  editorName: string;
  setEditorName: (v: string) => void;
  editorDesc: string;
  setEditorDesc: (v: string) => void;
  editorSteps: WorkflowStep[];
  editorParameters: WorkflowParameter[];
  runParams: Record<string, string>;
  setRunParams: (v: Record<string, string>) => void;
  runResult: RunResult | null;
  running: boolean;
  onAddStep: (action: "create_node" | "create_relationship" | "run_workflow") => void;
  onRemoveStep: (idx: number) => void;
  onUpdateStep: (idx: number, fields: Partial<WorkflowStep>) => void;
  onAddParameter: (p: WorkflowParameter) => boolean;
  onRemoveParameter: (name: string) => void;
  onSaveEditedParam: (idx: number, p: WorkflowParameter) => boolean | Promise<boolean>;
  onLoadWorkflow: (wf: Workflow) => void;
  onSaveWorkflow: () => void;
  onRunWorkflow: () => void;
  onResetEditor: () => void;
  dslCode: string;
  parameterTypes: string[];
  openNodeSelector: (className: string, callback: (uuid: string) => void) => void;
  actionError: string | null;
  onClearActionError: () => void;
}

export function WorkflowTab({
  tbox,
  workflows,
  selectedWorkflow,
  editorName,
  setEditorName,
  editorDesc,
  setEditorDesc,
  editorSteps,
  editorParameters,
  runParams,
  setRunParams,
  runResult,
  running,
  onAddStep,
  onRemoveStep,
  onUpdateStep,
  onAddParameter,
  onRemoveParameter,
  onSaveEditedParam,
  onLoadWorkflow,
  onSaveWorkflow,
  onRunWorkflow,
  onResetEditor,
  dslCode,
  parameterTypes,
  openNodeSelector,
  actionError,
  onClearActionError
}: WorkflowTabProps) {
  // Collapsible advanced-settings flag per step index
  const [expandedSettings, setExpandedSettings] = useState<Record<number, boolean>>({});

  // Currently selected step in the visual canvas
  const [activeStepIdx, setActiveStepIdx] = useState<number | null>(null);

  // Custom node positions when dragged, reset when switching workflow
  const [customPositions, setCustomPositions] = useState<Record<string, { x: number; y: number }>>({});
  useEffect(() => {
    setCustomPositions({});
  }, [selectedWorkflow?.name]);

  // Derived React Flow layout — memoized so the DAG math runs only when inputs change
  const positions = useMemo(() => computeStepPositions(editorSteps), [editorSteps]);
  const flowEdges = useMemo(() => buildFlowEdges(editorSteps), [editorSteps]);
  const flowNodes = useMemo(
    () => buildFlowNodes(editorSteps, activeStepIdx, positions, customPositions),
    [editorSteps, activeStepIdx, positions, customPositions]
  );

  const activeStep = activeStepIdx !== null ? editorSteps[activeStepIdx] : undefined;

  const handleAddStep = (action: "create_node" | "create_relationship" | "run_workflow") => {
    onAddStep(action);
    setActiveStepIdx(editorSteps.length);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left Panel: Saved Workflows + Run + Code previews */}
      <div className="lg:col-span-3 space-y-6">
        <WorkflowList
          workflows={workflows}
          selectedWorkflow={selectedWorkflow}
          onLoadWorkflow={onLoadWorkflow}
          onResetEditor={onResetEditor}
        />

        {selectedWorkflow && (
          <RunPanel
            selectedWorkflow={selectedWorkflow}
            runParams={runParams}
            setRunParams={setRunParams}
            runResult={runResult}
            running={running}
            onRunWorkflow={onRunWorkflow}
            openNodeSelector={openNodeSelector}
          />
        )}

        <CodePreview dslCode={dslCode} editorSteps={editorSteps} />
      </div>

      {/* Middle Panel: Visual step-by-step editor */}
      <div className="lg:col-span-9 space-y-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="font-bold text-slate-900 text-base m-0">Workflow Steps Builder</h3>
            <div className="flex space-x-2">
              <button
                onClick={onSaveWorkflow}
                className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-semibold hover:bg-indigo-700"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Save Workflow</span>
              </button>
            </div>
          </div>

          {actionError && (
            <div className="mb-4 flex items-start justify-between space-x-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-2.5">
              <span>{actionError}</span>
              <button
                type="button"
                onClick={onClearActionError}
                className="shrink-0 text-rose-400 hover:text-rose-700 font-bold"
                title="Dismiss"
              >
                ×
              </button>
            </div>
          )}

          <div className="space-y-4 mb-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Workflow Name</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 font-mono"
                  placeholder="e.g. create_sales_channel"
                  value={editorName}
                  onChange={(e) => setEditorName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Description</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500"
                  placeholder="Optional description"
                  value={editorDesc}
                  onChange={(e) => setEditorDesc(e.target.value)}
                />
              </div>
            </div>
          </div>

          <ParamManager
            classes={tbox.classes}
            editorParameters={editorParameters}
            parameterTypes={parameterTypes}
            onAddParameter={onAddParameter}
            onRemoveParameter={onRemoveParameter}
            onSaveEditedParam={onSaveEditedParam}
          />

          {/* Pipeline Canvas & Steps Builder */}
          <div className="space-y-4">
            <WorkflowCanvas
              editorSteps={editorSteps}
              flowNodes={flowNodes}
              flowEdges={flowEdges}
              onSelectStep={setActiveStepIdx}
              onMoveNode={(stepId, position) =>
                setCustomPositions((prev) => ({ ...prev, [stepId]: position }))
              }
            />

            {/* Selected Step Configurator */}
            {activeStep && activeStepIdx !== null ? (
              <StepConfigurator
                step={activeStep}
                idx={activeStepIdx}
                classes={tbox.classes}
                relationships={tbox.relationships}
                workflows={workflows}
                editorName={editorName}
                editorParameters={editorParameters}
                editorSteps={editorSteps}
                expanded={!!expandedSettings[activeStepIdx]}
                onToggleExpanded={() =>
                  setExpandedSettings({ ...expandedSettings, [activeStepIdx]: !expandedSettings[activeStepIdx] })
                }
                onUpdateStep={onUpdateStep}
                onRemoveStep={onRemoveStep}
                onDeselect={() => setActiveStepIdx(null)}
                openNodeSelector={openNodeSelector}
              />
            ) : (
              <div className="border border-slate-200 border-dashed rounded-xl p-8 text-center text-slate-400 bg-slate-50">
                <Settings className="h-10 w-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-medium">No Step Selected</p>
                <p className="text-xs text-slate-400 mt-1">Click any step node in the visual flowchart above to configure it.</p>
              </div>
            )}
          </div>

          <div className="flex space-x-2 pt-4 border-t border-slate-100">
            <button
              onClick={() => handleAddStep("create_node")}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 text-slate-600 font-semibold text-xs transition-colors"
            >
              <Plus className="h-4 w-4 text-indigo-500" />
              <span>Add Node Step</span>
            </button>
            <button
              onClick={() => handleAddStep("create_relationship")}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 text-slate-600 font-semibold text-xs transition-colors"
            >
              <Plus className="h-4 w-4 text-amber-500" />
              <span>Add Link Step</span>
            </button>
            <button
              onClick={() => handleAddStep("run_workflow")}
              className="flex-1 flex items-center justify-center space-x-1.5 py-2.5 border border-slate-300 rounded-xl hover:bg-slate-50 text-slate-600 font-semibold text-xs transition-colors"
            >
              <Plus className="h-4 w-4 text-emerald-500" />
              <span>Add Sub-Workflow</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
