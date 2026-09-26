CREATE INDEX IF NOT EXISTS idx_lifeweave_activity_external_session
ON workbench.t_lifeweave_activity (workspace_key, item_id, (payload->>'sessionId'), (payload->>'nativeSessionId'))
WHERE kind = 'external_development_binding';
