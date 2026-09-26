ALTER TABLE workbench.lifeweave_development_assignment
    ADD COLUMN execution_scope varchar(16) NOT NULL DEFAULT 'implement'
        CHECK (execution_scope IN ('plan_only', 'implement'));

ALTER TABLE workbench.lifeweave_development_assignment
    DROP CONSTRAINT lifeweave_development_assignment_status_check;
ALTER TABLE workbench.lifeweave_development_assignment
    ADD CONSTRAINT lifeweave_development_assignment_status_check CHECK (status IN (
        'planning', 'reviewing', 'plan_ready', 'implementing', 'awaiting_acceptance',
        'blocked', 'failed', 'cancelled'
    ));
