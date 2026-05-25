import { useState, useEffect } from "react";
import { Database } from "lucide-react";

// Hooks
import { useTBox } from "./hooks/useTBox";
import { useValidation } from "./hooks/useValidation";
import { useWorkflow } from "./hooks/useWorkflow";

// Components
import { TBoxSchemaTab } from "./components/TBoxSchemaTab";
import { ValidationTab } from "./components/ValidationTab";
import { WorkflowTab } from "./components/WorkflowTab";
import { NodeSelectorModal } from "./components/NodeSelectorModal";

export default function App() {
  const [activeTab, setActiveTab] = useState<"tbox" | "validation" | "workflow">(() => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get("tab");
    if (tab === "tbox" || tab === "validation" || tab === "workflow") {
      return tab;
    }
    return "tbox";
  });

  // Sync tab with URL search parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("tab") !== activeTab) {
      params.set("tab", activeTab);
      const newUrl = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState({}, "", newUrl);
    }
  }, [activeTab]);

  // Custom Hooks
  const {
    tbox,
    loadingTBox,
    fetchTBox,
    createClass,
    createProperty,
    attachProperty,
    createRelationship,
  } = useTBox();

  const {
    validationRun,
    validationIssues,
    validating,
    aboxCounts,
    aboxNodes,
    fetchLatestValidation,
    fetchAboxData,
    runValidation,
  } = useValidation();

  const {
    workflows,
    loadingWorkflows,
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
    fetchWorkflows,
    addStep,
    removeStep,
    updateStep,
    addParameter,
    removeParameter,
    saveEditedParam,
    loadWorkflowIntoEditor,
    handleSaveWorkflow,
    handleRunWorkflow,
    generatePythonDSL,
    resetEditor,
  } = useWorkflow(tbox, fetchAboxData);

  // Shared Node Selector Modal state
  const [showSelectorModal, setShowSelectorModal] = useState(false);
  const [selectorTargetClass, setSelectorTargetClass] = useState("");
  const [selectorCallback, setSelectorCallback] = useState<((uuid: string) => void) | null>(null);

  const openNodeSelector = (className: string, callback: (uuid: string) => void) => {
    setSelectorTargetClass(className);
    setSelectorCallback(() => callback);
    setShowSelectorModal(true);
  };

  const handleSelectNode = (uuid: string) => {
    if (selectorCallback) {
      selectorCallback(uuid);
    }
    setShowSelectorModal(false);
  };

  useEffect(() => {
    fetchTBox();
    fetchLatestValidation();
    fetchAboxData();
    fetchWorkflows();
  }, [fetchTBox, fetchLatestValidation, fetchAboxData, fetchWorkflows]);

  const handleTabChange = (tab: "tbox" | "validation" | "workflow") => {
    setActiveTab(tab);
    if (tab === "tbox") {
      fetchTBox();
    } else if (tab === "validation") {
      fetchLatestValidation();
      fetchAboxData();
    } else if (tab === "workflow") {
      fetchWorkflows();
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      {/* Header */}
      <header className="bg-slate-900 text-white shadow-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Database className="h-8 w-8 text-indigo-400" />
          <div>
            <h1 className="text-xl font-bold tracking-tight leading-none m-0 text-white">Data OOP Studio</h1>
            <p className="text-xs text-slate-400 mt-1">Live FalkorDB TBox & Workflows Explorer</p>
          </div>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => handleTabChange("tbox")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === "tbox" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            TBox Schema
          </button>
          <button
            onClick={() => handleTabChange("validation")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === "validation" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            Validation & ABox
          </button>
          <button
            onClick={() => handleTabChange("workflow")}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === "workflow" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            Workflow Builder
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {activeTab === "tbox" && (
          <TBoxSchemaTab
            tbox={tbox}
            loading={loadingTBox}
            onRefresh={fetchTBox}
            onCreateClass={createClass}
            onCreateProperty={createProperty}
            onAttachProperty={attachProperty}
            onCreateRelationship={createRelationship}
          />
        )}

        {activeTab === "validation" && (
          <ValidationTab
            validationRun={validationRun}
            validationIssues={validationIssues}
            validating={validating}
            aboxCounts={aboxCounts}
            aboxNodes={aboxNodes}
            onRunValidation={runValidation}
            onRefreshStats={fetchAboxData}
          />
        )}

        {activeTab === "workflow" && (
          <WorkflowTab
            tbox={tbox}
            workflows={workflows}
            loadingWorkflows={loadingWorkflows}
            selectedWorkflow={selectedWorkflow}
            editorName={editorName}
            setEditorName={setEditorName}
            editorDesc={editorDesc}
            setEditorDesc={setEditorDesc}
            editorSteps={editorSteps}
            editorParameters={editorParameters}
            runParams={runParams}
            setRunParams={setRunParams}
            runResult={runResult}
            running={running}
            onAddStep={addStep}
            onRemoveStep={removeStep}
            onUpdateStep={updateStep}
            onAddParameter={addParameter}
            onRemoveParameter={removeParameter}
            onSaveEditedParam={saveEditedParam}
            onLoadWorkflow={loadWorkflowIntoEditor}
            onSaveWorkflow={handleSaveWorkflow}
            onRunWorkflow={handleRunWorkflow}
            onResetEditor={resetEditor}
            generatePythonDSL={generatePythonDSL}
            openNodeSelector={openNodeSelector}
          />
        )}
      </main>

      {/* Shared ABox Node Selector Modal */}
      <NodeSelectorModal
        isOpen={showSelectorModal}
        targetClass={selectorTargetClass}
        onClose={() => setShowSelectorModal(false)}
        onSelect={handleSelectNode}
      />
    </div>
  );
}
