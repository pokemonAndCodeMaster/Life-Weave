-- A plan is fixed before a development assignment starts. Calls are observed
-- facts; they do not replace the existing assignment, Run, or event owners.
CREATE TABLE workbench.lifeweave_plugin_plan (
    id varchar(64) PRIMARY KEY,
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    item_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_item(id),
    assignment_id varchar(64) NOT NULL REFERENCES workbench.lifeweave_development_assignment(id),
    version integer NOT NULL CHECK (version > 0),
    previous_id varchar(64) REFERENCES workbench.lifeweave_plugin_plan(id),
    reason text,
    steps jsonb NOT NULL CHECK (jsonb_typeof(steps) = 'array'),
    bindings jsonb NOT NULL CHECK (jsonb_typeof(bindings) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace, assignment_id, version)
);

CREATE TABLE workbench.lifeweave_plugin_call (
    id varchar(64) PRIMARY KEY,
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    item_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_item(id),
    assignment_id varchar(64),
    run_id varchar(64),
    plan_id varchar(64) REFERENCES workbench.lifeweave_plugin_plan(id),
    step_id varchar(80),
    parent_call_id varchar(64) REFERENCES workbench.lifeweave_plugin_call(id),
    plugin_id varchar(160) NOT NULL,
    plugin_version varchar(128) NOT NULL,
    implementation_digest varchar(64) NOT NULL,
    operation varchar(80) NOT NULL,
    state varchar(24) NOT NULL CHECK (state IN ('started', 'accepted', 'succeeded', 'failed', 'interrupted')),
    input_ref jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(input_ref) = 'object'),
    output_ref jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(output_ref) = 'object'),
    error text,
    observed_by varchar(32) NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX lifeweave_plugin_call_item ON workbench.lifeweave_plugin_call (workspace, item_id, started_at DESC);
CREATE INDEX lifeweave_plugin_call_plugin ON workbench.lifeweave_plugin_call (workspace, plugin_id, plugin_version, started_at DESC);
CREATE INDEX lifeweave_plugin_call_run ON workbench.lifeweave_plugin_call (workspace, run_id, started_at);
CREATE INDEX lifeweave_plugin_call_parent ON workbench.lifeweave_plugin_call (parent_call_id);
CREATE UNIQUE INDEX lifeweave_plugin_call_worker_run ON workbench.lifeweave_plugin_call
    (workspace, run_id, plugin_id, operation) WHERE run_id IS NOT NULL AND observed_by = 'worker-report';

CREATE TABLE workbench.lifeweave_plugin_setting (
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    plugin_id varchar(160) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    config_version integer NOT NULL DEFAULT 1 CHECK (config_version > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace, plugin_id)
);
