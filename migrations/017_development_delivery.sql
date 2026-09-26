CREATE TABLE workbench.lifeweave_development_delivery (
    id varchar(64) PRIMARY KEY,
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    assignment_id varchar(64) NOT NULL UNIQUE REFERENCES workbench.lifeweave_development_assignment(id),
    run_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_run(id),
    base_revision varchar(128) NOT NULL,
    artifact_sha256 varchar(64) NOT NULL,
    manifest jsonb NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    integration_commit varchar(128),
    integration_checked_at timestamptz,
    integration_current_head boolean,
    decision varchar(16) CHECK (decision IN ('accepted', 'rejected')),
    decision_scope varchar(24) CHECK (decision_scope IN ('patch', 'integrated')),
    decision_reason text,
    decision_request_id varchar(128),
    decided_by varchar(128),
    decided_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE workbench.lifeweave_development_assignment
    DROP CONSTRAINT lifeweave_development_assignment_status_check;
ALTER TABLE workbench.lifeweave_development_assignment
    ADD CONSTRAINT lifeweave_development_assignment_status_check CHECK (status IN (
        'planning', 'reviewing', 'plan_ready', 'implementing', 'awaiting_acceptance',
        'delivery_failed', 'accepted', 'rejected', 'blocked', 'failed', 'cancelled'
    ));
