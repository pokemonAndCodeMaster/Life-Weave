CREATE TABLE workbench.lifeweave_development_assignment (
    id varchar(64) PRIMARY KEY,
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    item_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_item(id),
    request_id varchar(128) NOT NULL,
    request_fingerprint varchar(64) NOT NULL,
    instruction text NOT NULL,
    agent_id varchar(64) NOT NULL,
    agent_version varchar(128) NOT NULL,
    engine varchar(24) NOT NULL CHECK (engine IN ('codex', 'opencode')),
    model varchar(256),
    repository_path text NOT NULL,
    repository_revision varchar(128) NOT NULL,
    working_tree_excluded boolean NOT NULL DEFAULT false,
    context_version_id varchar(64) NOT NULL,
    method_id varchar(64),
    knowledge_refs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(knowledge_refs) = 'array'),
    input_versions jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_versions) = 'array'),
    review_mode varchar(24) NOT NULL CHECK (review_mode IN ('independent', 'self')),
    status varchar(32) NOT NULL CHECK (status IN (
        'planning', 'reviewing', 'implementing', 'awaiting_acceptance',
        'blocked', 'failed', 'cancelled'
    )),
    plan_run_id varchar(64) REFERENCES workbench.t_lifeweave_run(id),
    review_run_id varchar(64) REFERENCES workbench.t_lifeweave_run(id),
    implementation_run_id varchar(64) REFERENCES workbench.t_lifeweave_run(id),
    plan text,
    plan_sha256 varchar(64),
    review text,
    review_decision varchar(24),
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace, item_id, request_id)
);

CREATE INDEX lifeweave_development_assignment_item
    ON workbench.lifeweave_development_assignment (workspace, item_id, created_at DESC);
CREATE INDEX lifeweave_development_assignment_active
    ON workbench.lifeweave_development_assignment (status, updated_at)
    WHERE status IN ('planning', 'reviewing', 'implementing');
