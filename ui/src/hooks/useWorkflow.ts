import { useState, useCallback } from "react";
import type { Workflow, WorkflowStep, WorkflowParameter, TBoxClass, TBoxRelationship } from "../types";

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
  const [runResult, setRunResult] = useState<any | null>(null);
  const [running, setRunning] = useState(false);

  const fetchWorkflows = useCallback(async () => {
    setLoadingWorkflows(true);
    try {
      const res = await fetch("/api/workflows");
      const data = await res.json();
      setWorkflows(data);
    } catch (err) {
      console.error("Error fetching workflows", err);
    } finally {
      setLoadingWorkflows(false);
    }
  }, []);

  const addStep = useCallback((action: "create_node" | "create_relationship") => {
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
    } else {
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

  const addParameter = useCallback((newParam: WorkflowParameter) => {
    if (editorParameters.some(p => p.name === newParam.name)) {
      alert("Parameter already exists");
      return false;
    }
    setEditorParameters(params => [...params, newParam]);
    return true;
  }, [editorParameters]);

  const removeParameter = useCallback((name: string) => {
    setEditorParameters(params => params.filter(p => p.name !== name));
  }, []);

  const saveEditedParam = useCallback((idx: number, updatedParam: WorkflowParameter) => {
    if (editorParameters.some((p, i) => i !== idx && p.name === updatedParam.name)) {
      alert("Parameter already exists");
      return false;
    }
    setEditorParameters(params => {
      const updated = [...params];
      updated[idx] = updatedParam;
      return updated;
    });
    return true;
  }, [editorParameters]);

  const loadWorkflowIntoEditor = useCallback((wf: Workflow) => {
    setEditorName(wf.name);
    setEditorDesc(wf.description || "");
    setEditorSteps(wf.steps);
    setEditorParameters(wf.parameters || []);
    setSelectedWorkflow(wf);

    const params: Record<string, string> = {};
    if (wf.parameters && wf.parameters.length > 0) {
      wf.parameters.forEach((p) => {
        params[p.name] = "";
      });
    } else {
      const stepStr = JSON.stringify(wf.steps);
      const regex = /\{([^}]+)\}/g;
      let match;
      while ((match = regex.exec(stepStr)) !== null) {
        const path = match[1];
        if (!path.includes(".")) {
          params[path] = "";
        }
      }
    }
    setRunParams(params);
    setRunResult(null);
  }, []);

  const handleSaveWorkflow = useCallback(async () => {
    if (!editorName) return alert("Workflow name is required");
    try {
      const res = await fetch("/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editorName,
          description: editorDesc,
          steps: editorSteps,
          parameters: editorParameters,
        }),
      });
      if (res.ok) {
        alert("Workflow saved successfully!");
        await fetchWorkflows();
      }
    } catch (err) {
      console.error(err);
    }
  }, [editorName, editorDesc, editorSteps, editorParameters, fetchWorkflows]);

  const handleRunWorkflow = useCallback(async () => {
    if (!selectedWorkflow) return;
    setRunning(true);
    setRunResult(null);

    // Parse array parameters from JSON strings to real arrays
    const parsedParams = { ...runParams };
    selectedWorkflow.parameters?.forEach(p => {
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
      const res = await fetch(`/api/workflows/${selectedWorkflow.name}/run`, {
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
  }, [selectedWorkflow, runParams, onWorkflowRunSuccess]);

  const generatePythonDSL = useCallback(() => {
    if (!editorName) return "# Name your workflow to generate code";
    let codeStr = `from data_oop import connect_and_load_tbox_to_falkor, save_workflow, run_workflow
from falkordb import FalkorDB

# 1. Connect to FalkorDB
db = FalkorDB(host="localhost", port=6380)
graph = db.select_graph("data_oop")

# 2. Define Workflow Steps
steps = [\n`;

    editorSteps.forEach((step) => {
      codeStr += `    {\n`;
      codeStr += `        "step_id": "${step.step_id}",\n`;
      codeStr += `        "action": "${step.action}",\n`;
      if (step.action === "create_node") {
        codeStr += `        "class_name": "${step.class_name}",\n`;
        codeStr += `        "properties": {\n`;
        if (step.properties) {
          Object.entries(step.properties).forEach(([k, v]) => {
            codeStr += `            "${k}": "${v}",\n`;
          });
        }
        codeStr += `        }\n`;
      } else {
        codeStr += `        "from_class": "${step.from_class}",\n`;
        codeStr += `        "from_uuid": "${step.from_uuid}",\n`;
        codeStr += `        "relationship_name": "${step.relationship_name}",\n`;
        codeStr += `        "to_class": "${step.to_class}",\n`;
        codeStr += `        "to_uuid": "${step.to_uuid}"\n`;
      }
      if (step.if_present) {
        codeStr += `        "if_present": "${step.if_present}",\n`;
      }
      if (step.loop_over) {
        codeStr += `        "loop_over": "${step.loop_over}",\n`;
        codeStr += `        "loop_var": "${step.loop_var || "item"}",\n`;
      }
      codeStr += `    },\n`;
    });

    codeStr += `]

# 3. Parameters Definition
parameters = [\n`;
    editorParameters.forEach(p => {
      codeStr += `    { "name": "${p.name}", "type": "${p.type}", "required": ${p.required ? 'True' : 'False'}, "description": "${p.description}" },\n`;
    });
    codeStr += `]

# 4. Save Workflow to DB
save_workflow(
    graph=graph,
    name="${editorName}",
    steps=steps,
    parameters=parameters,
    description="${editorDesc || ''}"
)

# 5. Execute Workflow
results = run_workflow(
    graph=graph,
    name="${editorName}",
    parameters={
`;
    const paramsList: string[] = [];
    if (editorParameters.length > 0) {
      editorParameters.forEach(p => paramsList.push(p.name));
    } else {
      const stepStr = JSON.stringify(editorSteps);
      const regex = /\{([^}]+)\}/g;
      let match;
      while ((match = regex.exec(stepStr)) !== null) {
        const path = match[1];
        if (!path.includes(".") && !paramsList.includes(path)) {
          paramsList.push(path);
        }
      }
    }
    
    paramsList.forEach(p => {
      codeStr += `        "${p}": "YOUR_${p.toUpperCase()}_VALUE",\n`;
    });

    codeStr += `    }
)
print("Execution Results:", results)
`;
    return codeStr;
  }, [editorName, editorDesc, editorSteps, editorParameters]);

  const resetEditor = useCallback(() => {
    setEditorName("");
    setEditorDesc("");
    setEditorSteps([]);
    setEditorParameters([]);
    setSelectedWorkflow(null);
    setRunResult(null);
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
    generatePythonDSL,
    resetEditor,
  };
}
