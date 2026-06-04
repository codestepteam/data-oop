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

export interface ConnectorDef {
  name: string;
  kind: "postgres" | "mysql" | "bigquery";
  dsn_ref: string;
  description: string | null;
  metadata: Record<string, any>;
}

export interface SourceLink {
  relationship_name: string;
  to_class: string;
  local_key: string;
  target_property: string;
  direction: "out" | "in";
}

export interface SourceBinding {
  class_name: string;
  connector_name: string;
  sql: string;
  key_columns: string[];
  column_map: Record<string, string>;
  materialization: "materialized" | "virtual";
  refresh_interval_hours: number | null;
  links: SourceLink[];
}

export interface ViewParam {
  name: string;
  required: boolean;
}

export interface ViewDef {
  name: string;
  class_name: string;
  connector_name: string;
  sql: string;
  params: ViewParam[];
  key_column: string | null;
  ttl_seconds: number | null;
  description: string | null;
}

export interface TriggerDef {
  class_name: string;
  name: string;
  event: "create" | "update";
  workflow_name: string;
  condition: string | null;
  enabled: boolean;
  order: number;
  description: string | null;
  parameter_map: Record<string, string>;
}

export interface TriggerGraphReport {
  valid: boolean;
  cycles: string[][];
  unbounded: string[];
  unresolved: string[];
  missing_workflows: string[];
}

export interface WorkflowStep {
  step_id: string;
  action: "create_node" | "create_relationship" | "run_workflow" | "fetch_view";
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
  workflow_name?: string;
  view_name?: string;
  parameters?: Record<string, any>;
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
