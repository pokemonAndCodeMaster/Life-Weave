CREATE TABLE workbench.lifeweave_conversation (
 id text PRIMARY KEY,
 workspace text NOT NULL CHECK (workspace IN ('personal','team')),
 request_id text NOT NULL,
 title text NOT NULL,
 item_id text,
 initial_item_id text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(workspace,request_id)
);
CREATE TABLE workbench.lifeweave_turn (
 id text PRIMARY KEY,
 conversation_id text NOT NULL REFERENCES workbench.lifeweave_conversation(id),
 workspace text NOT NULL CHECK (workspace IN ('personal','team')),
 request_id text NOT NULL,
 body text NOT NULL,
 mode text NOT NULL CHECK (mode IN ('auto','record','discuss','execute')),
 status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','processing','completed','failed','cancelled')),
 request jsonb NOT NULL,
 reply text NOT NULL DEFAULT '',
 decision jsonb,
 receipts jsonb NOT NULL DEFAULT '[]',
 sources jsonb NOT NULL DEFAULT '[]',
 context_snapshot jsonb NOT NULL DEFAULT '{}',
 item_id text,
 run_id text,
 error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(conversation_id,request_id)
);
CREATE UNIQUE INDEX lifeweave_turn_one_pending ON workbench.lifeweave_turn(conversation_id) WHERE status IN ('queued','processing');
CREATE INDEX lifeweave_turn_conversation ON workbench.lifeweave_turn(conversation_id,created_at,id);
CREATE TABLE workbench.lifeweave_personal_model (
 workspace text PRIMARY KEY CHECK (workspace IN ('personal','team')),
 version integer NOT NULL DEFAULT 1,
 goals text NOT NULL DEFAULT '',
 preferences text NOT NULL DEFAULT '',
 updated_at timestamptz NOT NULL DEFAULT now()
);
