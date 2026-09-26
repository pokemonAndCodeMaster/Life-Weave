-- Existing assignments predate composite-call completion. Reconcile only
-- terminal stages whose assignment progression proves the outcome.
WITH proven AS (
    SELECT call.id, run.id AS run_id, run.finished_at,
      CASE
        WHEN run.state='succeeded' AND (
          (call.operation='plan' AND assignment.review_run_id IS NOT NULL)
          OR (call.operation='plan' AND assignment.review_mode='self'
              AND assignment.implementation_run_id IS NOT NULL)
          OR (call.operation='review' AND assignment.review_decision='pass'
              AND assignment.implementation_run_id IS NOT NULL)
          OR (call.operation='implement' AND assignment.status='awaiting_acceptance')
        ) THEN 'succeeded'
        WHEN run.state='cancelled' AND assignment.status='cancelled' THEN 'interrupted'
        ELSE 'failed'
      END AS stage_outcome
    FROM workbench.lifeweave_plugin_call AS call
    JOIN workbench.lifeweave_development_assignment AS assignment
      ON assignment.id=call.assignment_id AND assignment.workspace=call.workspace
    JOIN workbench.t_lifeweave_run AS run
      ON run.id=call.output_ref->>'runId' AND run.workspace=call.workspace
    WHERE call.plugin_id='lifeweave.development' AND call.state='accepted'
      AND run.state IN ('succeeded','failed','unavailable','cancelled','paused')
      AND ((call.operation='plan' AND assignment.plan_run_id=run.id)
        OR (call.operation='review' AND assignment.review_run_id=run.id)
        OR (call.operation='implement' AND assignment.implementation_run_id=run.id))
      AND (assignment.status IN ('blocked','failed','cancelled','awaiting_acceptance')
           OR assignment.review_run_id IS NOT NULL
           OR assignment.implementation_run_id IS NOT NULL)
)
UPDATE workbench.lifeweave_plugin_call AS call
SET run_id=proven.run_id, state=proven.stage_outcome,
    output_ref=call.output_ref || jsonb_build_object('stageOutcome', proven.stage_outcome,
                                                    'reconciledFrom', 'assignment-stage'),
    finished_at=GREATEST(call.started_at, proven.finished_at)
FROM proven WHERE call.id=proven.id;
