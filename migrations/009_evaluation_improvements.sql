ALTER TABLE workbench.t_lifeweave_evaluation
  ADD COLUMN improvement_id varchar(64)
  REFERENCES workbench.t_lifeweave_entity(id);
