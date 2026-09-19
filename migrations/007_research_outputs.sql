-- Provenance and retry identity for reviewed knowledge derived from run results.
-- document_revision remains the only owner of review state and text differences.
CREATE TABLE workbench.research_knowledge_candidate (
    revision_id text PRIMARY KEY REFERENCES workbench.document_revision(id),
    workspace text NOT NULL REFERENCES workbench.t_lifeweave_workspace(key),
    item_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_item(id),
    run_id varchar(64) NOT NULL REFERENCES workbench.t_lifeweave_run(id),
    run_version text NOT NULL,
    request_id text NOT NULL,
    request_fingerprint text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(workspace, item_id, request_id)
);
CREATE INDEX research_knowledge_item ON workbench.research_knowledge_candidate(workspace, item_id, created_at);
