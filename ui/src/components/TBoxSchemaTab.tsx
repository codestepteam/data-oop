import { useState } from "react";
import { RefreshCw, Plus, Zap } from "lucide-react";
import type {
  TBoxClass,
  TBoxInterface,
  TBoxRelationship,
  ConnectorDef,
  SourceBinding,
  ViewDef,
  TriggerDef,
  TriggerGraphReport,
} from "../types";
import type { TriggerInput } from "../hooks/useTBox";
import { CreateClassModal } from "./tbox/CreateClassModal";
import { CreatePropertyModal } from "./tbox/CreatePropertyModal";
import { AttachPropertyModal } from "./tbox/AttachPropertyModal";
import { DefineRelationshipModal } from "./tbox/DefineRelationshipModal";
import { CreateTriggerModal } from "./tbox/CreateTriggerModal";
import { SchemaOverview } from "./tbox/SchemaOverview";

interface TBoxSchemaTabProps {
  tbox: {
    classes: TBoxClass[];
    interfaces: TBoxInterface[];
    properties: { name: string; datatype: string }[];
    relationships: TBoxRelationship[];
    constraints: unknown[];
    connectors?: ConnectorDef[];
    source_bindings?: SourceBinding[];
    views?: ViewDef[];
    triggers?: TriggerDef[];
  };
  loading: boolean;
  onRefresh: () => void;
  onCreateClass: (name: string, label: string, desc: string) => Promise<boolean>;
  onCreateProperty: (name: string, datatype: string, desc: string) => Promise<boolean>;
  onAttachProperty: (className: string, propName: string, req: boolean, uniq: boolean) => Promise<boolean>;
  onCreateRelationship: (id: string, name: string, fromClass: string, toClass: string, req: boolean) => Promise<boolean>;
  onCreateTrigger: (input: TriggerInput) => Promise<{ ok: boolean; error?: string; cycles?: string[][] }>;
  onDeleteTrigger: (className: string, name: string) => Promise<boolean>;
  onValidateTriggers: (candidate?: TriggerInput) => Promise<TriggerGraphReport | null>;
}

export function TBoxSchemaTab({
  tbox,
  loading,
  onRefresh,
  onCreateClass,
  onCreateProperty,
  onAttachProperty,
  onCreateRelationship,
  onCreateTrigger,
  onDeleteTrigger,
  onValidateTriggers
}: TBoxSchemaTabProps) {
  const [showCreateClass, setShowCreateClass] = useState(false);
  const [showCreateProp, setShowCreateProp] = useState(false);
  const [showAttachProp, setShowAttachProp] = useState(false);
  const [showCreateRel, setShowCreateRel] = useState(false);
  const [showCreateTrigger, setShowCreateTrigger] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-slate-200">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 m-0">TBox Definitions</h2>
          <p className="text-sm text-slate-500 mt-1">Current Class, Interface, Property and Relationship schemas.</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={onRefresh}
            className="flex items-center space-x-1 px-3 py-1.5 border border-slate-300 rounded-lg text-sm font-medium bg-slate-50 text-slate-700 hover:bg-slate-100"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowCreateClass(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            <span>Create Class</span>
          </button>
          <button
            onClick={() => setShowCreateProp(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-sky-600 text-white rounded-lg text-sm font-medium hover:bg-sky-700"
          >
            <Plus className="h-4 w-4" />
            <span>Create Property</span>
          </button>
          <button
            onClick={() => setShowAttachProp(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700"
          >
            <Plus className="h-4 w-4" />
            <span>Attach Prop</span>
          </button>
          <button
            onClick={() => setShowCreateRel(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700"
          >
            <Plus className="h-4 w-4" />
            <span>Define Relation</span>
          </button>
          <button
            onClick={() => setShowCreateTrigger(true)}
            className="flex items-center space-x-1 px-3 py-1.5 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700"
          >
            <Zap className="h-4 w-4" />
            <span>Add Trigger</span>
          </button>
        </div>
      </div>

      {showCreateClass && (
        <CreateClassModal onClose={() => setShowCreateClass(false)} onCreateClass={onCreateClass} />
      )}
      {showCreateProp && (
        <CreatePropertyModal onClose={() => setShowCreateProp(false)} onCreateProperty={onCreateProperty} />
      )}
      {showAttachProp && (
        <AttachPropertyModal
          classes={tbox.classes}
          properties={tbox.properties}
          onClose={() => setShowAttachProp(false)}
          onAttachProperty={onAttachProperty}
        />
      )}
      {showCreateRel && (
        <DefineRelationshipModal
          classes={tbox.classes}
          onClose={() => setShowCreateRel(false)}
          onCreateRelationship={onCreateRelationship}
        />
      )}
      {showCreateTrigger && (
        <CreateTriggerModal
          classes={tbox.classes}
          onClose={() => setShowCreateTrigger(false)}
          onCreateTrigger={onCreateTrigger}
          onValidateTriggers={onValidateTriggers}
        />
      )}

      <SchemaOverview
        classes={tbox.classes}
        relationships={tbox.relationships}
        properties={tbox.properties}
        connectors={tbox.connectors}
        sourceBindings={tbox.source_bindings}
        views={tbox.views}
        triggers={tbox.triggers}
        onDeleteTrigger={onDeleteTrigger}
      />
    </div>
  );
}
