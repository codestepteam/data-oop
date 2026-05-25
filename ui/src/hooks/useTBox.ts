import { useState, useCallback } from "react";
import type { TBoxClass, TBoxInterface, TBoxRelationship } from "../types";

export function useTBox() {
  const [tbox, setTBox] = useState<{
    classes: TBoxClass[];
    interfaces: TBoxInterface[];
    properties: any[];
    relationships: TBoxRelationship[];
    constraints: any[];
  }>({ classes: [], interfaces: [], properties: [], relationships: [], constraints: [] });
  const [loadingTBox, setLoadingTBox] = useState(false);

  const fetchTBox = useCallback(async () => {
    setLoadingTBox(true);
    try {
      const res = await fetch("/api/tbox");
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
      const res = await fetch("/api/tbox/class", {
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
      const res = await fetch("/api/tbox/property", {
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
      const res = await fetch("/api/tbox/property/attach", {
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
      const res = await fetch("/api/tbox/relationship", {
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

  return {
    tbox,
    loadingTBox,
    fetchTBox,
    createClass,
    createProperty,
    attachProperty,
    createRelationship,
  };
}
