import { useState, useCallback, useEffect } from "react";
import { apiFetch } from "../api";
import type { Workflow, WorkflowStep, WorkflowParameter, TBoxClass, TBoxRelationship, RunResult } from "../types";

export function useWorkflow(tbox: { classes: TBoxClass[]; relationships: TBoxRelationship[] }, onWorkflowRunSuccess?: () => void) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);

  // Editor states
  const [editorName, setEditorName] = useState("");
  const [editorDesc, setEditorDesc] = useState("");
  const [editorSteps, setEditorSteps] = useState<WorkflowStep[]>([]);
  const [editorParameters, setEditorParameters] = useState<WorkflowParameter[]>([]);

  // Execution states
  const [runParams, setRunParams] = useState<Record<string, string>>({});
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);

  // Inline error surfaced to the editor (replaces alert()).
  const [actionError, setActionError] = useState<string | null>(null);
  const clearActionError = useCallback(() => setActionError(null), []);

  // DSL states
  const [dslCode, setDslCode] = useState("");
  const [generatingDsl, setGeneratingDsl] = useState(false);

  const fetchDslPreview = useCallback(async (
    name: string,
    steps: WorkflowStep[],
    parameters: WorkflowParameter[],
    desc: string
  ) => {
    if (!name) {
      setDslCode("# Name your workflow to generate code");
      return;
    }
    setGeneratingDsl(true);
    try {
      const res = await apiFetch("/api/workflows/dsl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          steps,
          parameters,
          description: desc
        })
      });
      if (res.ok) {
        const data = await res.json();
        setDslCode(data.dsl);
      } else {
        const errData = await res.json();
        setDslCode(`# Error generating DSL:\n# ${errData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error(err);
      setDslCode(`# Error generating DSL:\n# ${err}`);
    } finally {
      setGeneratingDsl(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDslPreview(editorName, editorSteps, editorParameters, editorDesc);
    }, 300);
    return () => clearTimeout(timer);
  }, [editorName, editorSteps, editorParameters, editorDesc, fetchDslPreview]);

  // Parameter types state from backend
  const [parameterTypes, setParameterTypes] = useState<string[]>([]);

  useEffect(() => {
    apiFetch("/api/workflows/parameter-types")
      .then(res => res.json())
      .then(data => setParameterTypes(data))
      .catch(err => console.error("Error fetching parameter types", err));
  }, []);

  useEffect(() => {
    setRunParams(prev => {
      const updated: Record<string, string> = {};
      editorParameters.forEach(p => {
        updated[p.name] = prev[p.name] || "";
      });
      return updated;
    });
  }, [editorParameters]);

  const fetchWorkflows = useCallback(async () => {
    setLoadingWorkflows(true);
    try {
      const res = await apiFetch("/api/workflows");
      const data = await res.json();
      setWorkflows(data);
    } catch (err) {
      console.error("Error fetching workflows", err);
    } finally {
      setLoadingWorkflows(false);
    }
  }, []);

  const addStep = useCallback((action: "create_node" | "create_relationship" | "run_workflow") => {
    const stepId = `step_${editorSteps.length + 1}`;
    if (action === "create_node") {
      setEditorSteps(steps => [
        ...steps,
        {
          step_id: stepId,
          action: "create_node",
          class_name: tbox.classes[0]?.name || "",
          properties: {},
        },
      ]);
    } else if (action === "create_relationship") {
      setEditorSteps(steps => [
        ...steps,
        {
          step_id: stepId,
          action: "create_relationship",
          from_class: tbox.classes[0]?.name || "",
          from_uuid: "",
          relationship_name: tbox.relationships[0]?.name || "",
          to_class: tbox.classes[0]?.name || "",
          to_uuid: "",
        },
      ]);
    } else {
      setEditorSteps(steps => [
        ...steps,
        {
          step_id: stepId,
          action: "run_workflow",
          workflow_name: "",
          parameters: {},
        },
      ]);
    }
  }, [editorSteps, tbox]);

  const removeStep = useCallback((index: number) => {
    setEditorSteps(steps => steps.filter((_, i) => i !== index));
  }, []);

  const updateStep = useCallback((index: number, fields: Partial<WorkflowStep>) => {
    setEditorSteps(steps =>
      steps.map((step, i) => {
        if (i !== index) return step;
        return { ...step, ...fields } as WorkflowStep;
      })
    );
  }, []);

  const persistWorkflow = useCallback(async (parametersToSave: WorkflowParameter[], showAlert = true) => {
    if (!editorName) {
      if (showAlert) setActionError("Workflow name is required");
      return false;
    }
    try {
      const payload = {
        name: editorName,
        description: editorDesc,
        steps: editorSteps,
        parameters: parametersToSave,
      };
      const res = await apiFetch("/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setActionError(`Workflow save failed: ${data.detail || res.statusText}`);
        return false;
      }
      setActionError(null);
      setSelectedWorkflow(prev => {
        if (prev && prev.name !== editorName) return prev;
        return {
          ...(prev || {}),
          name: editorName,
          description: editorDesc,
          steps: editorSteps,
          parameters: parametersToSave,
        } as Workflow;
      });
      await fetchWorkflows();
      return true;
    } catch (err) {
      console.error(err);
      setActionError(`Workflow save failed: ${err}`);
      return false;
    }
  }, [editorName, editorDesc, editorSteps, fetchWorkflows]);

  const addParameter = useCallback((newParam: WorkflowParameter) => {
    if (editorParameters.some(p => p.name === newParam.name)) {
      setActionError("Parameter already exists");
      return false;
    }
    setActionError(null);
    setEditorParameters(params => [...params, newParam]);
    return true;
  }, [editorParameters]);

  const removeParameter = useCallback((name: string) => {
    setEditorParameters(params => params.filter(p => p.name !== name));
  }, []);

  const saveEditedParam = useCallback(async (idx: number, updatedParam: WorkflowParameter) => {
    if (editorParameters.some((p, i) => i !== idx && p.name === updatedParam.name)) {
      setActionError("Parameter already exists");
      return false;
    }
    const updated = [...editorParameters];
    updated[idx] = updatedParam;
    setEditorParameters(updated);
    if (!editorName) return true;
    return persistWorkflow(updated, false);
  }, [editorParameters, editorName, persistWorkflow]);

  const loadWorkflowIntoEditor = useCallback((wf: Workflow) => {
    setEditorName(wf.name);
    setEditorDesc(wf.description || "");
    setEditorSteps(wf.steps);
    setEditorParameters(wf.parameters || []);
    setSelectedWorkflow(wf);
    setRunResult(null);
  }, []);

  const handleSaveWorkflow = useCallback(async () => {
    await persistWorkflow(editorParameters, true);
  }, [editorParameters, persistWorkflow]);

  const handleRunWorkflow = useCallback(async () => {
    if (!selectedWorkflow) return;
    setRunning(true);
    setRunResult(null);

    // Parse array parameters from JSON strings to real arrays
    const parsedParams = { ...runParams };
    const parameterDefs = editorParameters.length > 0 ? editorParameters : (selectedWorkflow.parameters || []);
    parameterDefs.forEach(p => {
      if (p.type === "array") {
        try {
          const val = runParams[p.name];
          if (typeof val === "string" && val.trim().startsWith("[")) {
            parsedParams[p.name] = JSON.parse(val);
          }
        } catch (e) {
          console.error("Failed to parse array parameter", p.name, e);
        }
      }
    });

    try {
      const res = await apiFetch(`/api/workflows/${selectedWorkflow.name}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parameters: parsedParams }),
      });
      const data = await res.json();
      setRunResult(data);
      if (onWorkflowRunSuccess) {
        onWorkflowRunSuccess();
      }
    } catch (err) {
      console.error(err);
      setRunResult({ error: String(err) });
    } finally {
      setRunning(false);
    }
  }, [selectedWorkflow, runParams, editorParameters, onWorkflowRunSuccess]);

  const resetEditor = useCallback(() => {
    setEditorName("");
    setEditorDesc("");
    setEditorSteps([]);
    setEditorParameters([]);
    setSelectedWorkflow(null);
    setRunResult(null);
    setActionError(null);
  }, []);

  return {
    workflows,
    loadingWorkflows,
    selectedWorkflow,
    editorName,
    setEditorName,
    editorDesc,
    setEditorDesc,
    editorSteps,
    setEditorSteps,
    editorParameters,
    setEditorParameters,
    runParams,
    setRunParams,
    runResult,
    setRunResult,
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
    dslCode,
    generatingDsl,
    parameterTypes,
    resetEditor,
    actionError,
    clearActionError,
  };
}
