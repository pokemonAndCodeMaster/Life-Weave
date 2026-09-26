ALTER TABLE workbench.t_lifeweave_evaluation
  DROP CONSTRAINT t_lifeweave_evaluation_run_id_key,
  DROP CONSTRAINT ck_lifeweave_evaluation_target;

ALTER TABLE workbench.t_lifeweave_evaluation
  ADD COLUMN plugin_id text,
  ADD COLUMN plugin_version text,
  ADD COLUMN plugin_call_id text REFERENCES workbench.lifeweave_plugin_call(id),
  ADD CONSTRAINT ck_lifeweave_evaluation_target CHECK (
    (target_kind='system' AND candidate_id IS NULL AND candidate_version IS NULL
      AND plugin_id IS NULL AND plugin_version IS NULL AND plugin_call_id IS NULL) OR
    (target_kind='capability' AND candidate_id IS NOT NULL AND candidate_version IS NOT NULL
      AND plugin_id IS NULL AND plugin_version IS NULL AND plugin_call_id IS NULL) OR
    (target_kind='plugin' AND candidate_id IS NULL AND candidate_version IS NULL
      AND plugin_id IS NOT NULL AND plugin_version IS NOT NULL AND plugin_call_id IS NOT NULL)
  );

ALTER TABLE workbench.t_lifeweave_evaluation
  DROP CONSTRAINT t_lifeweave_evaluation_target_kind_check,
  ADD CONSTRAINT t_lifeweave_evaluation_target_kind_check
    CHECK (target_kind IN ('system', 'capability', 'plugin'));

CREATE INDEX ix_lifeweave_evaluation_plugin_history
  ON workbench.t_lifeweave_evaluation(workspace_key, plugin_id, plugin_version, created_at DESC)
  WHERE plugin_id IS NOT NULL;
