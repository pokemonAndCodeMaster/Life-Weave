"""Store a readable manual deliverable and its review evidence atomically."""
import hashlib
import json
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from .models import WorkspaceKey

router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['results'])


class ManualResult(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1, max_length=500_000)
    verification: str = Field(min_length=1, max_length=20_000)
    environment: str = Field(min_length=1, max_length=2000)


@router.post('/items/{item_id}/manual-results', status_code=201)
def save_result(request: Request, workspace: WorkspaceKey, item_id: str, body: ManualResult):
    db = request.app.state.database_manager.postgres()
    digest = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
    identity = hashlib.sha256((workspace + item_id + digest).encode()).hexdigest()[:24]
    artifact_id, evidence_id = 'result-' + identity, 'evidence-' + identity
    with db.transaction() as conn:
        item = conn.execute('SELECT id FROM workbench.t_lifeweave_item WHERE id=%s AND workspace_key=%s FOR UPDATE', (item_id, workspace)).fetchone()
        if not item:
            raise HTTPException(404, '工作事项不存在')
        payload = {'kind':'手工成果','body':body.content,'summary':body.verification,'artifactVersion':digest}
        conn.execute("INSERT INTO workbench.t_lifeweave_entity(id,workspace_key,entity_type,title,payload,created_by,updated_by) VALUES(%s,%s,'artifact',%s,%s,'local-user','local-user') ON CONFLICT(id) DO NOTHING", (artifact_id,workspace,body.title,Jsonb(payload)))
        conn.execute("INSERT INTO workbench.t_lifeweave_relation(id,workspace_key,from_kind,from_id,to_kind,to_id,relation_type,created_by) VALUES(%s,%s,'item',%s,'entity',%s,'produces','local-user') ON CONFLICT DO NOTHING", ('relation-'+identity, workspace,item_id,artifact_id))
        conn.execute("INSERT INTO workbench.t_lifeweave_evidence(id,workspace_key,item_id,artifact_ref,artifact_version,environment_ref,summary,payload,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'local-user') ON CONFLICT(id) DO NOTHING", (evidence_id,workspace,item_id,artifact_id,digest,body.environment,body.verification,Jsonb({'title':body.title,'body':body.content})))
    return {'artifactId':artifact_id,'evidenceId':evidence_id,'version':digest}
