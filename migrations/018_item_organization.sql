CREATE TABLE IF NOT EXISTS workbench.t_lifeweave_organization_proposal (
    id varchar(64) PRIMARY KEY,
    workspace_key varchar(32) NOT NULL REFERENCES workbench.t_lifeweave_workspace(key),
    request_id varchar(128) NOT NULL,
    request_fingerprint varchar(64) NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','applied','undone')),
    reason text NOT NULL DEFAULT '',
    changes jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(changes)='array'),
    groups jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(groups)='array'),
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(warnings)='array'),
    receipt jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(receipt)='object'),
    created_by varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    applied_by varchar(128),
    applied_at timestamptz,
    undone_by varchar(128),
    undone_at timestamptz,
    UNIQUE (workspace_key, request_id)
);
CREATE INDEX IF NOT EXISTS idx_lifeweave_organization_proposal_workspace_created
    ON workbench.t_lifeweave_organization_proposal(workspace_key,created_at DESC);
