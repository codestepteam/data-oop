export interface TBoxProperty {
  name: string;
  datatype: string;
  description: string;
  required: boolean;
  unique: boolean;
  nullable: boolean;
  default: any;
  source_kind: string;
  source_id: string;
}

export interface TBoxClass {
  name: string;
  label: string | null;
  description: string | null;
  properties: TBoxProperty[];
  interfaces: string[];
}

export interface TBoxInterface {
  name: string;
  description: string | null;
  properties: any[];
}

export interface TBoxRelationship {
  id: string;
  name: string;
  from_class: string;
  to_class: string;
  min_count: number;
  max_count: number | null;
  required: boolean;
  description: string | null;
}

export interface WorkflowStep {
  step_id: string;
  action: "create_node" | "create_relationship";
  class_name?: string;
  properties?: Record<string, any>;
  uuid?: string;
  from_class?: string;
  from_uuid?: string;
  relationship_name?: string;
  to_class?: string;
  to_uuid?: string;
  if_present?: string;
  loop_over?: string;
  loop_var?: string;
}

export interface WorkflowParameter {
  name: string;
  type: string;
  array_item_type?: string;  // "string", "integer", "boolean", "uuid"
  array_item_class?: string; // target class name if item_type is "uuid"
  required: boolean;
  description: string;
}

export interface Workflow {
  name: string;
  steps: WorkflowStep[];
  parameters?: WorkflowParameter[];
  description: string | null;
  uuid?: string;
}

export interface ValidationIssue {
  id: string;
  code: string;
  severity: "info" | "warning" | "error";
  className: string | null;
  instanceUuid: string | null;
  propertyName: string | null;
  relationshipName: string | null;
  message: string;
}

export interface ValidationRun {
  id: string;
  status: string;
  started_at: string;
  checked_instance_count: number;
  error_count: number;
  warning_count: number;
}
