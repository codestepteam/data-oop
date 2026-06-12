import { useState, useCallback } from "react";
import { apiFetch } from "../api";
import type { ValidationRun, ValidationIssue, AboxCount, AboxNode } from "../types";

export function useValidation() {
  const [validationRun, setValidationRun] = useState<ValidationRun | null>(null);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [validating, setValidating] = useState(false);

  const [aboxCounts, setAboxCounts] = useState<AboxCount[]>([]);
  const [aboxNodes, setAboxNodes] = useState<AboxNode[]>([]);

  const fetchLatestValidation = useCallback(async () => {
    try {
      const res = await apiFetch("/api/validation/latest");
      const data = await res.json();
      setValidationRun(data.run);
      setValidationIssues(data.issues);
    } catch (err) {
      console.error("Error fetching validation", err);
    }
  }, []);

  const fetchAboxData = useCallback(async () => {
    try {
      const res = await apiFetch("/api/abox/nodes");
      const data = await res.json();
      setAboxCounts(data.counts || []);
      setAboxNodes(data.nodes || []);
    } catch (err) {
      console.error("Error fetching ABox data", err);
    }
  }, []);

  const runValidation = useCallback(async () => {
    setValidating(true);
    try {
      const res = await apiFetch("/api/validation", { method: "POST" });
      await res.json();
      await fetchLatestValidation();
    } catch (err) {
      console.error("Error running validation", err);
    } finally {
      setValidating(false);
    }
  }, [fetchLatestValidation]);

  return {
    validationRun,
    validationIssues,
    validating,
    aboxCounts,
    aboxNodes,
    fetchLatestValidation,
    fetchAboxData,
    runValidation,
  };
}
