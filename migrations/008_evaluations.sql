CREATE TABLE workbench.t_lifeweave_evaluation (
  id text PRIMARY KEY,
  workspace_key text NOT NULL CHECK (workspace_key IN ('personal', 'team')),
  item_id text NOT NULL,
  target_kind text NOT NULL CHECK (target_kind IN ('system', 'capability')),
  candidate_id text,
  candidate_version text,
  repeat_of text REFERENCES workbench.t_lifeweave_evaluation(id),
  title text NOT NULL,
  instruction text NOT NULL,
  criteria text NOT NULL,
  state text NOT NULL DEFAULT 'planned' CHECK (state IN ('planned', 'running', 'assessed')),
  run_id text UNIQUE REFERENCES workbench.t_lifeweave_run(id),
  outcome text CHECK (outcome IN ('passed', 'failed', 'inconclusive')),
  assessment text,
  evidence_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  assessed_at timestamptz,
  CONSTRAINT ck_lifeweave_evaluation_target CHECK (
    (target_kind='system' AND candidate_id IS NULL AND candidate_version IS NULL) OR
    (target_kind='capability' AND candidate_id IS NOT NULL AND candidate_version IS NOT NULL)
  ),
  CONSTRAINT fk_lifeweave_evaluation_candidate FOREIGN KEY (workspace_key, candidate_id)
    REFERENCES workbench.t_lifeweave_capability(workspace_key, id)
);
CREATE INDEX ix_lifeweave_evaluation_workspace_created
  ON workbench.t_lifeweave_evaluation(workspace_key, created_at DESC);
CREATE INDEX ix_lifeweave_evaluation_repeat_of
  ON workbench.t_lifeweave_evaluation(repeat_of) WHERE repeat_of IS NOT NULL;
