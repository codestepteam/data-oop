import { Activity, Database, Cable, Link2, Zap, Trash2, Gauge } from "lucide-react";
import type { TBoxClass, TBoxRelationship, ConnectorDef, SourceBinding, ViewDef, TriggerDef } from "../../types";

interface SchemaOverviewProps {
  classes: TBoxClass[];
  relationships: TBoxRelationship[];
  properties: { name: string; datatype: string }[];
  connectors?: ConnectorDef[];
  sourceBindings?: SourceBinding[];
  views?: ViewDef[];
  triggers?: TriggerDef[];
  onDeleteTrigger: (className: string, name: string) => Promise<boolean>;
}

/** Read-only overview of the live TBox: classes, relationships, sources, views, triggers. */
export function SchemaOverview({
  classes,
  relationships,
  properties,
  connectors,
  sourceBindings,
  views,
  triggers,
  onDeleteTrigger,
}: SchemaOverviewProps) {
  return (
    <>
      {/* Grid of Classes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {classes.map((cls) => (
          <div key={cls.name} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
            <div className="bg-slate-50 border-b border-slate-200 p-4">
              <div className="flex justify-between items-start">
                <h3 className="font-bold text-slate-900 text-base m-0">{cls.name}</h3>
                <span className="bg-indigo-50 text-indigo-700 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-indigo-100">
                  Class
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-2 italic">{cls.description || "No description provided."}</p>
            </div>
            <div className="p-4 flex-1 space-y-3">
              <div>
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Properties ({cls.properties.length})</h4>
                {cls.properties.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No properties attached.</p>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {cls.properties.map((prop) => (
                      <div key={prop.name} className="py-2 flex items-center justify-between">
                        <div>
                          <span className="text-sm font-semibold text-slate-800">{prop.name}</span>
                          <span className="text-xs text-slate-400 ml-1.5">({prop.datatype})</span>
                        </div>
                        <div className="flex space-x-1.5">
                          {prop.required && (
                            <span className="bg-rose-50 text-rose-700 text-[10px] font-bold px-1.5 py-0.5 rounded border border-rose-100">
                              Req
                            </span>
                          )}
                          {prop.unique && (
                            <span className="bg-amber-50 text-amber-700 text-[10px] font-bold px-1.5 py-0.5 rounded border border-amber-100">
                              Uniq
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Relationships and Properties Pool */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Allowed Relationships */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Activity className="h-5 w-5 text-violet-500" />
            <span>Allowed Relationships ({relationships.length})</span>
          </h3>
          {relationships.length === 0 ? (
            <p className="text-sm text-slate-400 italic">No relationships defined.</p>
          ) : (
            <div className="space-y-3">
              {relationships.map((rel) => (
                <div key={rel.id} className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-900">{rel.from_class}</span>
                      <span className="text-xs font-mono bg-violet-100 text-violet-800 px-2 py-0.5 rounded-md border border-violet-200">
                        -{rel.name}-&gt;
                      </span>
                      <span className="text-sm font-bold text-slate-900">{rel.to_class}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">ID: {rel.id}</p>
                  </div>
                  {rel.required && (
                    <span className="bg-rose-50 text-rose-700 text-xs font-bold px-2 py-0.5 rounded border border-rose-100">
                      Required
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Global Properties Definitions */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Database className="h-5 w-5 text-sky-500" />
            <span>Global Property Definitions ({properties.length})</span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {properties.map((prop) => (
              <div key={prop.name} className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-sm flex items-center space-x-2">
                <span className="font-semibold text-slate-800">{prop.name}</span>
                <span className="text-xs text-slate-400">({prop.datatype})</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* External RDB Connectors & Source Bindings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connectors */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Cable className="h-5 w-5 text-cyan-500" />
            <span>External RDB Connectors ({(connectors ?? []).length})</span>
          </h3>
          {(connectors ?? []).length === 0 ? (
            <p className="text-sm text-slate-400 italic">No connectors defined.</p>
          ) : (
            <div className="space-y-3">
              {(connectors ?? []).map((conn) => (
                <div key={conn.name} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-900">{conn.name}</span>
                    <span className="text-xs font-mono bg-cyan-100 text-cyan-800 px-2 py-0.5 rounded-md border border-cyan-200">
                      {conn.kind}
                    </span>
                  </div>
                  {conn.dsn_ref && (
                    <p className="text-xs text-slate-500 mt-1">
                      DSN env: <span className="font-mono">{conn.dsn_ref}</span>
                    </p>
                  )}
                  {conn.description && (
                    <p className="text-xs text-slate-400 mt-1 italic">{conn.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Source Bindings */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
            <Database className="h-5 w-5 text-amber-500" />
            <span>Source Bindings ({(sourceBindings ?? []).length})</span>
          </h3>
          {(sourceBindings ?? []).length === 0 ? (
            <p className="text-sm text-slate-400 italic">No source bindings configured.</p>
          ) : (
            <div className="space-y-3">
              {(sourceBindings ?? []).map((b) => (
                <div key={b.class_name} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-900">{b.class_name}</span>
                      <span className="text-xs text-slate-400">←</span>
                      <span className="text-xs font-mono bg-amber-100 text-amber-800 px-2 py-0.5 rounded-md border border-amber-200">
                        {b.connector_name}
                      </span>
                    </div>
                    <span className="text-[10px] font-semibold text-slate-500 uppercase">{b.materialization}</span>
                  </div>
                  <p className="text-[11px] font-mono text-slate-500 mt-2 line-clamp-2 break-all">{b.sql}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {b.key_columns.map((k) => (
                      <span key={k} className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                        key: {k}
                      </span>
                    ))}
                    {b.refresh_interval_hours != null && (
                      <span className="text-[10px] text-slate-500 px-1.5 py-0.5">⟳ {b.refresh_interval_hours}h</span>
                    )}
                  </div>
                  {b.links.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {b.links.map((link, i) => (
                        <div key={i} className="flex items-center space-x-1 text-[11px] text-slate-600">
                          <Link2 className="h-3 w-3 text-emerald-500" />
                          <span className="font-mono">
                            {link.direction === "out"
                              ? `${b.class_name} -${link.relationship_name}→ ${link.to_class}`
                              : `${link.to_class} -${link.relationship_name}→ ${b.class_name}`}
                          </span>
                          <span className="text-slate-400">({link.local_key}={link.target_property})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* On-demand Views (data stays in RDB; graph stores only the query spec) */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
          <Gauge className="h-5 w-5 text-violet-500" />
          <span>On-demand Views ({(views ?? []).length})</span>
        </h3>
        {(views ?? []).length === 0 ? (
          <p className="text-sm text-slate-400 italic">No views defined.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {(views ?? []).map((v) => (
              <div key={v.name} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-slate-900">{v.name}</span>
                    <span className="text-xs text-slate-400">on</span>
                    <span className="text-xs font-mono text-slate-600">{v.class_name}</span>
                  </div>
                  {v.key_column && (
                    <span className="text-[10px] font-mono bg-violet-100 text-violet-800 px-2 py-0.5 rounded-md border border-violet-200">
                      key: {v.key_column}
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-2 mt-1">
                  <span className="text-xs text-slate-400">←</span>
                  <span className="text-xs font-mono bg-amber-100 text-amber-800 px-2 py-0.5 rounded-md border border-amber-200">
                    {v.connector_name}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {v.ttl_seconds != null ? `cache ${v.ttl_seconds}s` : "live"}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-slate-500 mt-2 line-clamp-2 break-all">{v.sql}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(v.params ?? []).map((p) => (
                    <span key={p.name} className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                      {p.name}{p.required ? "*" : ""}
                    </span>
                  ))}
                </div>
                {v.description && (
                  <p className="text-xs text-slate-400 mt-1 italic">{v.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Triggers (class-level callbacks: on create/update -> run workflow) */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h3 className="font-bold text-slate-950 text-base mb-4 flex items-center space-x-2">
          <Zap className="h-5 w-5 text-rose-500" />
          <span>Triggers ({(triggers ?? []).length})</span>
          <span className="text-xs font-normal text-slate-400">— on create/update, run a workflow</span>
        </h3>
        {(triggers ?? []).length === 0 ? (
          <p className="text-sm text-slate-400 italic">No triggers registered.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {(triggers ?? []).map((t) => (
              <div
                key={`${t.class_name}:${t.name}`}
                className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-start justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center space-x-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-900">{t.name}</span>
                    {!t.enabled && (
                      <span className="text-[10px] uppercase font-semibold text-slate-400 border border-slate-300 rounded px-1">
                        disabled
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-1 text-[12px] text-slate-600 mt-1 flex-wrap">
                    <span className="font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">{t.class_name}</span>
                    <span className="text-slate-400">on</span>
                    <span className="font-mono bg-rose-100 text-rose-800 px-1.5 py-0.5 rounded border border-rose-200">{t.event}</span>
                    <span className="text-slate-400">→</span>
                    <span className="font-mono bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded border border-indigo-200">{t.workflow_name}</span>
                  </div>
                  {t.condition && (
                    <p className="text-[11px] text-slate-500 mt-1">
                      if <span className="font-mono">{t.condition}</span>
                    </p>
                  )}
                  {t.parameter_map && Object.keys(t.parameter_map).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {Object.entries(t.parameter_map).map(([k, v]) => (
                        <span key={k} className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                          {k}={String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                  {t.description && <p className="text-[11px] text-slate-400 mt-1 italic">{t.description}</p>}
                </div>
                <button
                  onClick={() => onDeleteTrigger(t.class_name, t.name)}
                  className="ml-2 shrink-0 text-slate-400 hover:text-rose-600"
                  title="Delete trigger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
