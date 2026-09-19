-- Rename identifiers in place; FK targets and all row contents retain their identity.
-- Applied migrations 001-004 intentionally retain their original names/checksums.
DO $$
DECLARE entry record;
BEGIN
  FOR entry IN
    SELECT c.relname AS table_name, con.conname
    FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='workbench' AND con.conname LIKE '%gongzuo%'
  LOOP
    EXECUTE format('ALTER TABLE workbench.%I RENAME CONSTRAINT %I TO %I',
      entry.table_name, entry.conname, replace(entry.conname,'gongzuo','lifeweave'));
  END LOOP;
  FOR entry IN SELECT tablename FROM pg_tables
    WHERE schemaname='workbench' AND tablename LIKE 't_gongzuo_%'
  LOOP
    EXECUTE format('ALTER TABLE workbench.%I RENAME TO %I',
      entry.tablename, replace(entry.tablename,'gongzuo','lifeweave'));
  END LOOP;
  FOR entry IN SELECT indexname FROM pg_indexes
    WHERE schemaname='workbench' AND indexname LIKE '%gongzuo%'
  LOOP
    EXECUTE format('ALTER INDEX workbench.%I RENAME TO %I',
      entry.indexname, replace(entry.indexname,'gongzuo','lifeweave'));
  END LOOP;
  FOR entry IN SELECT sequencename FROM pg_sequences
    WHERE schemaname='workbench' AND sequencename LIKE '%gongzuo%'
  LOOP
    EXECUTE format('ALTER SEQUENCE workbench.%I RENAME TO %I',
      entry.sequencename, replace(entry.sequencename,'gongzuo','lifeweave'));
  END LOOP;
END $$;
