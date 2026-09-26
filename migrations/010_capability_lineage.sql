ALTER TABLE workbench.t_lifeweave_capability
  ADD COLUMN predecessor_candidate_id text;
ALTER TABLE workbench.t_lifeweave_capability
  ADD CONSTRAINT fk_lifeweave_capability_predecessor
  FOREIGN KEY (workspace_key, predecessor_candidate_id)
  REFERENCES workbench.t_lifeweave_capability(workspace_key, id);
CREATE INDEX ix_lifeweave_capability_predecessor
  ON workbench.t_lifeweave_capability(workspace_key, predecessor_candidate_id)
  WHERE predecessor_candidate_id IS NOT NULL;
