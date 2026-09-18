CREATE TABLE workbench.library_source (
  id text PRIMARY KEY, workspace text NOT NULL REFERENCES workbench.t_gongzuo_workspace(key),
  title text NOT NULL, root text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace,root)
);
CREATE TABLE workbench.document_revision (
  id text PRIMARY KEY, workspace text NOT NULL REFERENCES workbench.t_gongzuo_workspace(key),
  source_id text NOT NULL, path text NOT NULL, base_version text NOT NULL,
  before_content text NOT NULL, content text NOT NULL, reason text NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','accepted','rejected')),
  created_at timestamptz NOT NULL DEFAULT now(), accepted_at timestamptz
);
CREATE INDEX document_revision_subject ON workbench.document_revision(workspace,source_id,path,created_at);
CREATE TABLE workbench.linear_binding (
  workspace text NOT NULL REFERENCES workbench.t_gongzuo_workspace(key),
  issue_id text NOT NULL, item_id varchar(64) NOT NULL REFERENCES workbench.t_gongzuo_item(id),
  remote_snapshot jsonb NOT NULL, synced_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(workspace,issue_id), UNIQUE(workspace,item_id)
);
CREATE TABLE workbench.linear_publication (
  id text PRIMARY KEY, workspace text NOT NULL, item_id varchar(64) NOT NULL,
  issue_id text NOT NULL, body text NOT NULL, remote_comment_id text,
  status text NOT NULL CHECK(status IN ('prepared','sending','confirmed','uncertain')),
  created_at timestamptz NOT NULL DEFAULT now(), confirmed_at timestamptz
);
