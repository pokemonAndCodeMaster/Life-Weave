import hashlib
import json
from psycopg.types.json import Jsonb
from .repository import ConcurrentUpdateError


def identity(prefix, *parts):
    return prefix+'-'+hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:32]


def wire(row):
    names = {'item_id':'itemId','run_id':'runId','created_at':'createdAt','updated_at':'updatedAt',
             'conversation_id':'conversationId','request_id':'requestId'}
    result = {names.get(k,k):v for k,v in row.items() if k not in {'context_snapshot','request','decision','initial_item_id'}}
    if 'request' in row:
        result['inputContext'] = {key:row['request'].get(key) for key in ('itemId','runId','anchor')}
        result['inputContext']['itemId'] = result['inputContext']['itemId'] or row['item_id']
    return result


class ConversationRepository:
    def __init__(self, db):
        self.db = db

    def get(self, workspace, conversation_id):
        row = self.db.fetch_one('SELECT * FROM workbench.lifeweave_conversation WHERE workspace=%s AND id=%s', (workspace,conversation_id))
        if row is None:
            raise KeyError('对话不存在')
        return row

    def create(self, workspace, body):
        cid = identity('conversation',workspace,body.requestId)
        with self.db.atomic() as conn:
            conn.execute('INSERT INTO workbench.lifeweave_conversation(id,workspace,request_id,title,item_id,initial_item_id) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                         (cid,workspace,body.requestId,body.title,body.itemId,body.itemId))
            row = self.get(workspace,cid)
            if row['initial_item_id'] != body.itemId:
                raise ConcurrentUpdateError('同一请求已用于另一事项')
        return wire(row)

    def list(self, workspace, item_id=None):
        rows = self.db.fetch_all('''SELECT c.* FROM workbench.lifeweave_conversation c WHERE workspace=%s
            AND (%s::text IS NULL OR item_id=%s OR EXISTS (
                SELECT 1 FROM workbench.lifeweave_turn t WHERE t.conversation_id=c.id AND t.item_id=%s))
            ORDER BY updated_at DESC,id''',(workspace,item_id,item_id,item_id))
        return {'items':[wire(r) for r in rows], 'total':len(rows)}

    def turns(self, workspace, cid):
        self.get(workspace,cid)
        return self.db.fetch_all('SELECT * FROM workbench.lifeweave_turn WHERE workspace=%s AND conversation_id=%s ORDER BY created_at,id',(workspace,cid))

    def turn(self, workspace, cid, tid):
        row = self.db.fetch_one('SELECT * FROM workbench.lifeweave_turn WHERE workspace=%s AND conversation_id=%s AND id=%s',(workspace,cid,tid))
        if row is None:
            raise KeyError('消息不存在')
        return row

    def enqueue(self, workspace, cid, body):
        tid = identity('turn',workspace,cid,body.requestId)
        request = body.model_dump()
        with self.db.atomic() as conn:
            conversation = conn.execute('SELECT * FROM workbench.lifeweave_conversation WHERE workspace=%s AND id=%s FOR UPDATE',(workspace,cid)).fetchone()
            if conversation is None:
                raise KeyError('对话不存在')
            prior = conn.execute('SELECT * FROM workbench.lifeweave_turn WHERE workspace=%s AND id=%s',(workspace,tid)).fetchone()
            if prior:
                if prior['request'] != request:
                    raise ConcurrentUpdateError('同一请求标识对应不同内容；请读取已保存消息后再发新消息')
                return prior
            if conn.execute("SELECT 1 FROM workbench.lifeweave_turn WHERE conversation_id=%s AND status IN ('queued','processing')",(cid,)).fetchone():
                raise ConcurrentUpdateError('当前对话仍在处理上一条消息，可以先停止或等待')
            row = conn.execute('''INSERT INTO workbench.lifeweave_turn(id,conversation_id,workspace,request_id,body,mode,request,item_id,run_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (tid,cid,workspace,body.requestId,body.body,body.mode,Jsonb(request),body.itemId or conversation['item_id'],body.runId)).fetchone()
            conn.execute("UPDATE workbench.lifeweave_conversation SET updated_at=now(), title=CASE WHEN title='新的对话' THEN %s ELSE title END WHERE id=%s",(body.body[:80],cid))
        return row

    def profile(self, workspace):
        row = self.db.fetch_one('SELECT version,goals,preferences,updated_at FROM workbench.lifeweave_personal_model WHERE workspace=%s',(workspace,))
        return wire(row) if row else {'version':0,'goals':'','preferences':'','updatedAt':None}

    def save_profile(self, workspace, body):
        with self.db.atomic() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('personal-model-'+workspace,))
            if self.profile(workspace)['version'] != body.version:
                raise ConcurrentUpdateError('方向与偏好已变化，请重新读取后修改')
            conn.execute('''INSERT INTO workbench.lifeweave_personal_model(workspace,goals,preferences) VALUES (%s,%s,%s)
                ON CONFLICT(workspace) DO UPDATE SET goals=excluded.goals,preferences=excluded.preferences,
                version=lifeweave_personal_model.version+1,updated_at=now()''',(workspace,body.goals,body.preferences))
            return self.profile(workspace)
