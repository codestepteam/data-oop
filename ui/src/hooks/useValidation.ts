import { useState, useCallback } from "react";
import type { ValidationRun, ValidationIssue } from "../types";

export function useValidation() {
  const [validationRun, setValidationRun] = useState<ValidationRun | null>(null);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [validating, setValidating] = useState(false);

  const [aboxCounts, setAboxCounts] = useState<{ label: string; count: number }[]>([]);
  const [aboxNodes, setAboxNodes] = useState<any[]>([]);

  const fetchLatestValidation = useCallback(async () => {
    try {
      const res = await fetch("/api/validation/latest");
      const data = await res.json();
      setValidationRun(data.run);
      setValidationIssues(data.issues);
    } catch (err) {
      console.error("Error fetching validation", err);
    }
  }, []);

  const fetchAboxData = useCallback(async () => {
    try {
      const res = await fetch("/api/abox/nodes");
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
      const res = await fetch("/api/validation", { method: "POST" });
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
