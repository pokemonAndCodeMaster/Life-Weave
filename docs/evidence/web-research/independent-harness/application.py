import os, json, asyncio
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
ROOT=Path('/home/yyh/project/lifeweave')
HERE=ROOT/'.runtime/independent-web-review'
manifest=HERE/'manifest.json'
if manifest.exists():
    data=json.loads(manifest.read_text())
else:
    name='test_lifeweave_review_'+uuid4().hex[:12]
    with psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname='postgres',autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    data={'database':name,'root':str(HERE),'port':8013,'candidate':'0e574e4c27b03fdb60a1a819c964e824b265128f','controlledInterpreter':True}
    manifest.write_text(json.dumps(data))
os.environ['LIFEWEAVE_DB_NAME']=data['database']
os.environ['LIFEWEAVE_LOCAL_WORKER']='0'
os.environ['LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT']=str(HERE/'personal')
os.environ['LIFEWEAVE_TEAM_KNOWLEDGE_ROOT']=str(HERE/'team')
from src.cli import migrate
from src.api.app import create_app
from src.lifeweave.conversation_models import Decision
migrate(); app=create_app()
for field in ('local_workers','task_sources','research_outputs'):
    getattr(app.state,field).root=HERE
app.state.lifeweave_runtime_service.runtime_root=HERE/'.runtime/runs'
app.state.root=HERE
class ControlledInterpreter:
    async def interpret(self, workspace, tid, context, event):
        text=context['user']
        if '等待受控中断' in text: await asyncio.sleep(120)
        if '受控解释失败' in text: raise ValueError('独立验证：解释器故障')
        intent='execute' if '委托' in text else 'context' if '改目标' in text else 'answer'
        return Decision(intent=intent,reply='独立受控协议结果；不是实际 AI 回答。',title=text[:80],itemId=(context.get('currentItem') or {}).get('id'),itemType='research',instruction=text,feedback=None,proposedGoal='独立复核新目标' if intent=='context' else None,knowledge=None)
app.state.conversations.interpreter=ControlledInterpreter()
if __name__=='__main__':
    data['pid']=os.getpid();manifest.write_text(json.dumps(data))
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8013)
