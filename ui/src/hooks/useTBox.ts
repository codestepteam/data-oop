import { useState, useCallback } from "react";
import { apiFetch } from "../api";
import type {
  TBoxClass,
  TBoxInterface,
  TBoxProperty,
  TBoxRelationship,
  ConnectorDef,
  SourceBinding,
  ViewDef,
  TriggerDef,
  TriggerGraphReport,
} from "../types";

export interface TriggerInput {
  class_name: string;
  name: string;
  event: "create" | "update";
  workflow_name: string;
  condition?: string | null;
  enabled?: boolean;
  order?: number;
  description?: string | null;
  parameter_map?: Record<string, string>;
}

export function useTBox() {
  const [tbox, setTBox] = useState<{
    classes: TBoxClass[];
    interfaces: TBoxInterface[];
    properties: TBoxProperty[];
    relationships: TBoxRelationship[];
    constraints: unknown[];
    connectors?: ConnectorDef[];
    source_bindings?: SourceBinding[];
    views?: ViewDef[];
    triggers?: TriggerDef[];
  }>({ classes: [], interfaces: [], properties: [], relationships: [], constraints: [] });
  const [loadingTBox, setLoadingTBox] = useState(false);

  const fetchTBox = useCallback(async () => {
    setLoadingTBox(true);
    try {
      const res = await apiFetch("/api/tbox");
      const data = await res.json();
      setTBox(data);
    } catch (err) {
      console.error("Error fetching TBox", err);
    } finally {
      setLoadingTBox(false);
    }
  }, []);

  const createClass = useCallback(async (name: string, label: string, description: string) => {
    try {
      const res = await apiFetch("/api/tbox/class", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, label, description }),
      });
      if (res.ok) {
        await fetchTBox();
        return true;
      }
    } catch (err) {
      console.error(err);
    }
    return false;
  }, [fetchTBox]);

  const createProperty = useCallback(async (name: string, datatype: string, description: string) => {
    try {
      const res = await apiFetch("/api/tbox/property", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, datatype, description }),
      });
      if (res.ok) {
        await fetchTBox();
        return true;
      }
    } catch (err) {
      console.error(err);
    }
    return false;
  }, [fetchTBox]);

  const attachProperty = useCallback(async (className: string, propertyName: string, required: boolean, unique: boolean) => {
    try {
      const res = await apiFetch("/api/tbox/property/attach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_name: className,
          property_name: propertyName,
          required,
          unique,
        }),
      });
      if (res.ok) {
        await fetchTBox();
        return true;
      }
    } catch (err) {
      console.error(err);
    }
    return false;
  }, [fetchTBox]);

  const createRelationship = useCallback(async (id: string, name: string, fromClass: string, toClass: string, required: boolean) => {
    try {
      const res = await apiFetch("/api/tbox/relationship", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id,
          name,
          from_class: fromClass,
          to_class: toClass,
          required,
        }),
      });
      if (res.ok) {
        await fetchTBox();
        return true;
      }
    } catch (err) {
      console.error(err);
    }
    return false;
  }, [fetchTBox]);

  // Analyse the trigger graph for cycles/divergence WITHOUT saving. Pass a
  // prospective trigger to preview the effect of adding it.
  const validateTriggers = useCallback(
    async (candidate?: TriggerInput): Promise<TriggerGraphReport | null> => {
      try {
        const res = await apiFetch("/api/tbox/triggers/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: candidate ? JSON.stringify(candidate) : "null",
        });
        if (res.ok) return (await res.json()) as TriggerGraphReport;
      } catch (err) {
        console.error(err);
      }
      return null;
    },
    []
  );

  const createTrigger = useCallback(
    async (input: TriggerInput): Promise<{ ok: boolean; error?: string; cycles?: string[][] }> => {
      try {
        const res = await apiFetch("/api/tbox/trigger", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        });
        if (res.ok) {
          await fetchTBox();
          return { ok: true };
        }
        // 409 -> cycle; detail carries {message, cycles}
        const data = await res.json().catch(() => null);
        const detail = data?.detail;
        if (detail && typeof detail === "object") {
          return { ok: false, error: detail.message, cycles: detail.cycles };
        }
        return { ok: false, error: typeof detail === "string" ? detail : "Failed to create trigger" };
      } catch (err) {
        console.error(err);
        return { ok: false, error: String(err) };
      }
    },
    [fetchTBox]
  );

  const deleteTrigger = useCallback(
    async (className: string, name: string): Promise<boolean> => {
      try {
        const res = await apiFetch("/api/tbox/trigger/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ class_name: className, name }),
        });
        if (res.ok) {
          await fetchTBox();
          return true;
        }
      } catch (err) {
        console.error(err);
      }
      return false;
    },
    [fetchTBox]
  );

  return {
    tbox,
    loadingTBox,
    fetchTBox,
    createClass,
    createProperty,
    attachProperty,
    createRelationship,
    createTrigger,
    deleteTrigger,
    validateTriggers,
  };
}
