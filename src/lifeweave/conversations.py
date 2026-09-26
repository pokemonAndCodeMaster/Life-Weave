"""Durable web conversation with bounded, transactional product actions."""
import asyncio
import json
import logging
from psycopg.types.json import Jsonb

from .conversation_models import Decision, TurnCreate
from .conversation_repository import ConversationRepository, wire
from .repository import ConcurrentUpdateError


def snapshot(value):
    return json.loads(json.dumps(value,ensure_ascii=False,default=str))


def research_support(conversations, workspace, item_id):
    current = conversations.outputs.read(workspace,item_id)['current'] if conversations.outputs else None
    return snapshot({'personalModel':conversations.repository.profile(workspace),
                     'previousOutput':{k:current[k] for k in ('id','version','content','runId')} if current else None})


class Conversations:
    def __init__(self, db, work, runtime, continuation, sources, interpreter, development=None):
        self.db, self.work, self.runtime = db, work, runtime
        self.continuation, self.sources, self.interpreter = continuation, sources, interpreter
        self.repository = ConversationRepository(db)
        self.development = development
        self.tasks = {}
        self.outputs = None

    def create(self, workspace, body):
        if body.itemId:
            self.work.get_item(workspace,body.itemId)
        return self.repository.create(workspace,body)

    def read(self, workspace, cid):
        conversation = wire(self.repository.get(workspace,cid))
        conversation['turns'] = [wire(t) for t in self.repository.turns(workspace,cid)]
        return conversation

    async def submit(self, workspace, cid, body):
        conversation = self.repository.get(workspace,cid)
        item_id = body.itemId or conversation['item_id']
        if item_id:
            self.work.get_item(workspace,item_id)
        if body.runId:
            run = self.runtime.get_run(workspace,body.runId)
            if run['item_id'] != item_id:
                raise ValueError('所引用成果不属于本次事项')
        for research_id in body.researchItemIds:
            self.work.get_item(workspace,research_id)
            if not self.outputs or not self.outputs.read(workspace,research_id)['current']:
                raise ValueError('附带的研究事项还没有可读成果')
        row = self.repository.enqueue(workspace,cid,body)
        if row['status'] == 'queued' and row['id'] not in self.tasks:
            task = asyncio.create_task(self.process(workspace,cid,row['id']))
            self.tasks[row['id']] = task
            task.add_done_callback(lambda _task: self.tasks.pop(row['id'],None))
        return wire(row)

    def prepare(self, workspace, cid, turn):
        history = self.repository.turns(workspace,cid)
        discovery = self.continuation.discover(workspace,turn['body'])
        candidates = discovery['items'][:20]
        current = self.work.get_item(workspace,turn['item_id']) if turn['item_id'] else None
        current_context = self.work.current_context_snapshot(workspace,current['id']) if current else {'versionId':None,'content':{}}
        recommendations = self.sources.recommend(workspace,current or {'title':turn['body']},current_context,turn['body'])
        docs = recommendations['documents'][:10]
        documents = []
        remaining = 40000
        for doc in docs:
            full = self.sources.library.document(workspace,doc['sourceId'],doc['path'])
            excerpt = full['content'][:min(remaining,20000)]
            documents.append({**full,'content':excerpt,'excerpt':len(excerpt)<len(full['content'])})
            remaining -= len(excerpt)
            if remaining <= 0:
                break
        runs = self.runtime.list_runs(workspace,item_id=current['id'],limit=5,offset=0)[0] if current else []
        previous = []
        for run in runs:
            result = str((run.get('result_payload') or {}).get('report') or run.get('result') or '')
            previous.append({'id':run['id'],'state':run['state'],'result':result[:2000],
                             'excerpt':len(result)>2000,'error':run.get('error')})
        external = []
        if current:
            rows = self.work.repository.list_activities(workspace, current['id'])
            external = [{'id':row['id'], 'createdAt':row['createdAt'], 'summary':row['body'],
                         'phase':row['payload'].get('phase'), 'sessionId':row['payload'].get('sessionId'),
                         'observedGit':row['payload'].get('observedGit'),
                         'declaredInputs':row['payload'].get('declaredInputs', []),
                         'reportedChecks':row['payload'].get('reportedChecks', []),
                         'provenance':'阶段与检查由外部会话上报；Git 状态由服务观测'}
                        for row in rows if row['kind'] in {'external_development_start', 'external_development_event'}][:10]
        research = []
        research_ids = list(dict.fromkeys(([current['id']] if current else []) + turn['request'].get('researchItemIds',[])))
        remaining_research = 120000
        for index,item_id in enumerate(research_ids):
            output = self.outputs.read(workspace,item_id)['current'] if self.outputs else None
            if not output:
                continue
            if item_id == (current or {}).get('id') and turn['run_id']:
                versions=self.outputs.read(workspace,item_id)['versions']
                output=next((o for o in versions if o['runId']==turn['run_id']),output)
            # Reserve a fair excerpt for every explicitly selected paper, even
            # when the current report consumes its entire 60k allowance.
            limit=min(remaining_research,60000) if item_id==(current or {}).get('id') else min(20000,remaining_research//(len(research_ids)-index))
            content=output['content'][:limit]
            remaining_research-=len(content)
            research.append({'kind':'research','itemId':item_id,'runId':output['runId'],'title':output['title'],
                'version':output['version'],'content':content,'excerpt':len(content)<len(output['content']),
                'url':f'/lifeweave/{workspace}/items/{item_id}/outputs','acceptedKnowledge':False})
        context = {'workspace':workspace,'user':turn['body'],'mode':turn['mode'],
                   'anchor':turn['request'].get('anchor'),'runId':turn['run_id'],
                   'currentItem':current,'currentContext':current_context,
                   'profile':self.repository.profile(workspace),'candidates':candidates,
                   'candidateTotal':discovery['total'], 'documents':documents,
                   'documentCandidateTotal':len(recommendations['documents']),
                   'researchOutputs':research,
                   'methods':recommendations['methods'][:10], 'runs':previous,
                   'externalDevelopment':external,
                   'feedback':self.work.execution_feedback(workspace,current['id']) if current else [],
                   'history':[{'body':h['body'][:1500],'reply':(h['reply'] or '')[:1500],'status':h['status'],
                               'itemId':h['item_id'],'receipts':h['receipts']}
                              for h in history if h['id']!=turn['id']][-20:],
                   'historyTotal':len(history)-1,
                   'limits':'相关事项最多20；知识最多10篇/40000字符；当前成果加5篇指定研究共120000字符，截断标记excerpt；最近20轮对话、5次运行摘要和10条外部开发报告，不代表全部历史。'}
        return snapshot(context)

    async def process(self, workspace, cid, tid):
        claimed = self.db.fetch_one("UPDATE workbench.lifeweave_turn SET status='processing',updated_at=now() WHERE id=%s AND workspace=%s AND status='queued' RETURNING *",(tid,workspace))
        if claimed is None:
            return
        try:
            if claimed['mode']=='record':
                context = {}
                decision = Decision(intent='record',reply='这条想法保留原话，之后可以继续讨论。',
                    title=claimed['body'][:80],itemId=None,itemType='other',instruction='',
                    feedback=None,proposedGoal=None,knowledge=None)
            else:
                context = self.prepare(workspace,cid,claimed)
                self.db.execute('UPDATE workbench.lifeweave_turn SET context_snapshot=%s,sources=%s WHERE id=%s',
                                (Jsonb(context),Jsonb([{'title':d['title'],'sourceId':d['sourceId'],'path':d['path'],
                                                      'version':d['version'],'excerpt':d['excerpt']} for d in context['documents']]+[
                                                      {k:r[k] for k in ('kind','itemId','runId','title','version','excerpt','url','acceptedKnowledge')}
                                                      for r in context['researchOutputs']]),tid))
                async def event(_event):
                    # Raw execution diagnostics may contain account paths. They
                    # remain in the protected executor directory, not user chat.
                    pass
                decision = await self.interpreter.interpret(workspace,tid,context,event)
            self.apply(workspace,cid,tid,decision,context)
        except asyncio.CancelledError:
            self.db.execute("UPDATE workbench.lifeweave_turn SET status='cancelled',error='本轮处理已停止，原话已保存',updated_at=now() WHERE id=%s AND status IN ('queued','processing')",(tid,))
            raise
        except Exception as exc:
            logging.exception('对话处理失败: %s',tid)
            self.db.execute("UPDATE workbench.lifeweave_turn SET status='failed',error=%s,updated_at=now() WHERE id=%s AND status IN ('queued','processing')",(str(exc)[:2000],tid))

    def apply(self, workspace, cid, tid, decision, context):
        with self.db.atomic() as conn:
            turn = conn.execute('SELECT * FROM workbench.lifeweave_turn WHERE workspace=%s AND id=%s FOR UPDATE',(workspace,tid)).fetchone()
            if not turn or turn['status']!='processing':
                return
            if turn['mode']=='discuss' and decision.intent not in {'answer','clarify','discuss','feedback'}:
                raise ValueError('本轮限定为讨论，未执行模型提出的写入或委托；请继续说明')
            allowed_items = {c['id'] for c in context.get('candidates',[]) if c['kind']=='item'}
            if turn['item_id']:
                allowed_items.add(turn['item_id'])
            if decision.itemId and decision.itemId not in allowed_items:
                raise ValueError('模型选择了本轮未提供的事项，没有执行该动作')
            # Null deliberately means a new topic for discussion/delegation.
            # Other actions may use the explicitly displayed current scope.
            item_id = decision.itemId if decision.intent in {'discuss','execute'} else decision.itemId or turn['item_id']
            receipts = []
            run_id = None
            actor = 'local-user'
            if decision.intent == 'record':
                idea = self.work.create_entity(workspace,entity_type='idea',title=decision.title,
                        payload={'body':turn['body'],'conversationId':cid,'turnId':tid},actor_id=actor)
                receipts.append({'kind':'idea','id':idea['id'],'title':'已保存想法，未安排执行'})
            elif decision.intent not in {'answer','clarify'}:
                if not item_id:
                    if decision.intent in {'feedback','context','knowledge'}:
                        raise ValueError('需要先关联明确的事项或成果，原话已保存')
                    item = self.work.create_item(workspace,item_type=decision.itemType,title=decision.title,
                        status='open',payload={'originalRequest':turn['body'],'conversationId':cid},actor_id=actor,
                        initial_context={'goal':turn['body']},provenance=[{'conversationId':cid,'turnId':tid}])
                    item_id = item['id']
                    receipts.append({'kind':'item','id':item_id,'itemId':item_id,'title':'已建立持续事项'})
                item = self.work.get_item(workspace,item_id)
                if (decision.intent in {'execute','context','knowledge'} and
                        (context.get('currentItem') or {}).get('id') == item_id and
                        self.work.current_context_snapshot(workspace,item_id)['versionId'] !=
                        context['currentContext']['versionId']):
                    raise ConcurrentUpdateError('解释期间事项背景已更新，请读取新背景后重试；没有执行旧建议')
                if turn['request'].get('runId'):
                    quoted = self.runtime.get_run(workspace,turn['request']['runId'])
                    if quoted['item_id'] != item_id:
                        raise ValueError('引用成果与选择的事项不一致')
                if decision.feedback or decision.intent=='feedback':
                    feedback = self.work.record_feedback(workspace,item_id,body=turn['body'],
                        run_id=turn['request'].get('runId'),request_id=tid,actor_id=actor,
                        anchor=turn['request'].get('anchor'))
                    receipts.append({'kind':'feedback','id':feedback['id'],'itemId':item_id,'title':'纠偏已保存，下一轮会读取'})
                else:
                    discussion = self.work.add_discussion(workspace,item_id=item_id,body=turn['body'],anchor=turn['request'].get('anchor'),
                        payload={'conversationId':cid,'turnId':tid,'assistantReply':decision.reply},actor_id=actor)
                    receipts.append({'kind':'discussion','id':discussion['id'],'itemId':item_id,'title':'讨论已关联事项'})
                if decision.intent=='context':
                    if not decision.proposedGoal:
                        raise ValueError('未形成明确的目标修改建议')
                    own = self.work.repository.context(workspace,item_id)
                    content = {**own['content'],'goal':decision.proposedGoal}
                    proposed = self.work.propose_context(workspace,item_id,base_version=own['version'],
                        title=decision.title,proposed_content=content,provenance=[{'conversationId':cid,'turnId':tid}],actor_id=actor)
                    receipts.append({'kind':'context','id':proposed['id'],'itemId':item_id,'title':'目标修改待审，当前目标尚未改变'})
                if decision.intent=='execute':
                    if item['itemType'] in {'requirement','fix'}:
                        repository_path = turn['request'].get('repositoryPath')
                        if repository_path and self.development:
                            assignment = self.development.create(
                                workspace, item_id=item_id, request_id=tid,
                                instruction=decision.instruction or turn['body'],
                                repository_path=repository_path,
                                acknowledge_excluded_changes=bool(turn['request'].get('acknowledgeExcludedChanges')))
                            run_id = assignment['planRunId']
                            receipts.append({'kind':'development','id':assignment['id'],'itemId':item_id,
                                             'runId':run_id,'title':'开发委托已启动：先形成只读方案'})
                            decision.reply += '\n\n开发委托已启动；第一步是只读方案，之后按审阅结果进入实施。'
                        else:
                            receipts.append({'kind':'development','id':item_id,'itemId':item_id,
                                             'title':'开发任务已关联事项；请选择项目目录后启动，尚未执行代码'})
                            decision.reply += '\n\n开发任务已关联此事项。请打开事项的“开发 Agent”页选择项目仓库并启动；目前尚未执行代码。'
                    else:
                        _, active = self.runtime.list_runs(workspace,item_id=item_id,limit=1,offset=0,
                            states=('queued','claimed','running','pause_requested','cancelling'))
                        if active:
                            raise ValueError('该事项仍有委托进行中，请等待完成或先停止；没有重复发起')
                        current = self.work.current_context_snapshot(workspace,item_id)
                        suggested = self.sources.recommend(workspace,item,current,decision.instruction or turn['body'])['suggested']
                        run = self.runtime.create_run(workspace,item_id=item_id,
                            instruction=decision.instruction or turn['body'],engine='codex',
                            permission='workspace-write',method_id=suggested['methodId'],
                            related_research=context.get('researchOutputs',[]),
                            knowledge_refs=suggested['knowledgeRefs'],actor_id=actor)
                        run_id = run['id']
                        receipts.append({'kind':'run','id':run_id,'runId':run_id,'itemId':item_id,'title':'委托已排队，结果以运行状态为准'})
                if decision.intent=='knowledge':
                    if not self.outputs or not decision.knowledge:
                        raise ValueError('尚未形成可审阅的知识候选')
                    runs,_ = self.runtime.list_runs(workspace,item_id=item_id,limit=1,offset=0,states=('succeeded',))
                    source_run = turn['request'].get('runId') or (runs[0]['id'] if runs else None)
                    if not source_run:
                        raise ValueError('该事项还没有可引用的成功成果')
                    draft = decision.knowledge
                    # Existing targets must have actually been read by the interpreter.
                    target = self.sources.library.file(workspace,'local',draft.path)
                    doc = next((d for d in context.get('documents',[]) if d['sourceId']=='local' and d['path']==draft.path),None)
                    if target.exists() and (not doc or doc['excerpt']):
                        raise ValueError('需要完整读取目标知识原文后再提出修订')
                    revision = self.outputs.propose_from_run(workspace,item_id,source_run,draft.path,draft.content,
                        doc['version'] if doc else 'new',draft.reason,tid)
                    receipts.append({'kind':'knowledge','id':revision['id'],'itemId':item_id,'runId':source_run,'title':'知识修订待审，原文尚未改变'})
            conn.execute('''UPDATE workbench.lifeweave_turn SET status='completed',reply=%s,decision=%s,
                receipts=%s,item_id=%s,run_id=%s,updated_at=now() WHERE id=%s''',
                (decision.reply,Jsonb(decision.model_dump()),Jsonb(receipts),item_id,run_id,tid))
            conn.execute('UPDATE workbench.lifeweave_conversation SET item_id=COALESCE(%s,item_id),updated_at=now() WHERE id=%s',(item_id,cid))

    async def cancel(self, workspace, cid, tid):
        row = self.repository.turn(workspace,cid,tid)
        if row['status'] in {'queued','processing'}:
            self.db.execute("UPDATE workbench.lifeweave_turn SET status='cancelled',error='本轮处理已停止，原话已保存',updated_at=now() WHERE id=%s AND status IN ('queued','processing')",(tid,))
            task = self.tasks.get(tid)
            if task:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
        return wire(self.repository.turn(workspace,cid,tid))

    def recover(self):
        return self.db.execute("UPDATE workbench.lifeweave_turn SET status='failed',error='服务中断了这轮处理，未自动重发；原话已保存，可以重试',updated_at=now() WHERE status IN ('queued','processing')")

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
