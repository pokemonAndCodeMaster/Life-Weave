-- Agent configurations are triggerable views over installed plugin owners.
-- Launch receipts bind one actual owner record to the configuration used then.
CREATE TABLE workbench.lifeweave_agent_config (
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    id varchar(64) NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    configuration jsonb NOT NULL CHECK (jsonb_typeof(configuration) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace, id)
);

CREATE TABLE workbench.lifeweave_agent_launch (
    id varchar(64) PRIMARY KEY,
    workspace varchar(16) NOT NULL CHECK (workspace IN ('personal', 'team')),
    item_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_item(id),
    request_id varchar(128) NOT NULL,
    request_fingerprint varchar(64) NOT NULL,
    agent_id varchar(64) NOT NULL,
    agent_version integer NOT NULL,
    configuration_snapshot jsonb NOT NULL CHECK (jsonb_typeof(configuration_snapshot) = 'object'),
    kind varchar(32) NOT NULL CHECK (kind IN ('managed_development','managed_run','external_session','organization')),
    reference_id varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace, item_id, request_id)
);
CREATE INDEX lifeweave_agent_launch_item ON workbench.lifeweave_agent_launch (workspace, item_id, created_at DESC);
CREATE INDEX lifeweave_agent_launch_agent ON workbench.lifeweave_agent_launch (workspace, agent_id, created_at DESC);
CREATE INDEX lifeweave_agent_launch_reference ON workbench.lifeweave_agent_launch (workspace, kind, reference_id, created_at DESC);
