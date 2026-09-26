"""Real migrations, HTTP and persistence, in a disposable database only."""
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import sleep
import json
import os
import subprocess
import pytest
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def database_client(tmp_path_factory):
    if os.environ.get('LIFEWEAVE_TEST_DB') != '1':
        pytest.skip('LIFEWEAVE_TEST_DB=1 enables disposable PostgreSQL integration tests')
    from src.api.app import create_app
    from src.cli import migrate
    root = tmp_path_factory.mktemp('live-app')
    name = 'test_lifeweave_' + uuid4().hex[:12]
    connection = psycopg.connect(host=str(ROOT/'.runtime/postgres/socket'), port=55440, user='lifeweave', dbname='postgres', autocommit=True)
    connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('LIFEWEAVE_DB_NAME', name)
        patch.setenv('LIFEWEAVE_LOCAL_WORKER', '0')
        patch.setenv('LIFEWEAVE_PERSONAL_KNOWLEDGE_ROOT', str(root/'personal'))
        patch.setenv('LIFEWEAVE_TEAM_KNOWLEDGE_ROOT', str(root/'team'))
        try:
            migrate()
            app = create_app()
            app.state.task_sources.root = root
            app.state.local_workers.root = root
            with TestClient(app) as active:
                yield active
        finally:
            connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            connection.close()


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    yield from database_client(tmp_path_factory)


@pytest.fixture
def dedicated_client(tmp_path_factory):
    yield from database_client(tmp_path_factory)


def post(client, route, body, status=201):
    response = client.post('/api/lifeweave/personal'+route, json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_current_project_knowledge_uses_one_read_only_source_and_live_versions(dedicated_client, tmp_path):
    client = dedicated_client
    project = tmp_path / 'project'
    (project / 'docs/history').mkdir(parents=True)
    (project / 'docs/current-sources.json').write_text(json.dumps({
        'id': 'lifeweave-project', 'title': 'LifeWeave 项目',
        'paths': ['README.md', 'docs/status.md'],
    }), encoding='utf-8')
    (project / 'README.md').write_text('# LifeWeave\n[状态](docs/status.md)', encoding='utf-8')
    status = project / 'docs/status.md'
    status.write_text('# 当前状态\n开发事项可接续。', encoding='utf-8')
    (project / 'docs/history/old.md').write_text('# 旧状态\n过期判断', encoding='utf-8')
    client.app.state.library.project_root = project
    base = '/api/lifeweave/personal/library'
    sources = client.get(base + '/sources').json()
    assert next(row for row in sources if row['id'] == 'lifeweave-project')['writable'] is False
    catalog = client.get(base + '/documents', params={'sourceId': 'lifeweave-project'}).json()
    assert {row['path'] for row in catalog['items']} == {'README.md', 'docs/status.md'}
    assert client.get(base + '/documents', params={'sourceId': 'nonexistent'}).status_code == 404
    assert client.get(base + '/document', params={'sourceId': 'lifeweave-project',
                                                  'path': 'docs/history/old.md'}).status_code == 409
    first = client.get(base + '/document', params={'sourceId': 'lifeweave-project',
                                                   'path': 'docs/status.md'}).json()
    first_snapshot = client.app.state.task_sources.snapshot('personal', None,
                                                             ['lifeweave-project:docs/status.md'])[0]
    assert first_snapshot['content'] == first['content']
    assert first_snapshot['version'] == first['version']
    status.write_text('# 当前状态\n开发事项和知识更新可接续。', encoding='utf-8')
    updated = client.get(base + '/document', params={'sourceId': 'lifeweave-project',
                                                     'path': 'docs/status.md'}).json()
    assert updated['version'] != first['version']
    assert '知识更新' in updated['content']
    assert client.get('/api/lifeweave/team/library/document', params={
        'sourceId': 'lifeweave-project', 'path': 'docs/status.md'}).status_code == 200


def test_external_development_reports_real_git_state_without_creating_a_run(dedicated_client, tmp_path):
    client = dedicated_client
    project = tmp_path / 'code'
    project.mkdir()
    subprocess.run(['git', '-C', str(project), 'init', '-q'], check=True)
    (project / 'feature.txt').write_text('before\n')
    subprocess.run(['git', '-C', str(project), 'add', 'feature.txt'], check=True)
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '-qm', 'baseline'], check=True)
    item = post(client, '/items', {'itemType': 'fix', 'title': '修复项目知识入口',
                                   'payload': {'goal': '从知识页读取当前项目规范'}})
    route = f"/items/{item['id']}/external-development/sessions"
    body = {'requestId': 'external-start-one', 'repositoryPath': str(project),
            'summary': '在当前会话准备项目知识入口', 'knowledgeRefs': ['lifeweave-project:docs/status.md']}
    started = post(client, route, body)
    assert started['event']['kind'] == 'external_development_start'
    assert started['event']['payload']['observedGit']['repositoryPath'] == str(project)
    assert started['event']['payload']['declaredInputs'][0]['version']
    assert client.get('/api/lifeweave/team' + route).status_code == 404
    assert post(client, route, body)['sessionId'] == started['sessionId']
    assert client.post('/api/lifeweave/personal' + route, json={**body, 'summary': '不同内容'}).status_code == 409
    (project / 'feature.txt').write_text('after\n')
    events = route + '/' + started['sessionId'] + '/events'
    report = {'requestId': 'external-check-one', 'phase': 'verification',
              'summary': '实际运行一次检查', 'checks': ['pytest: passed']}
    verified = post(client, events, report)
    assert verified['payload']['observedGit']['changedPaths'] == ['feature.txt']
    assert verified['payload']['reportedChecks'] == ['pytest: passed']
    assert post(client, events, report)['id'] == verified['id']
    assert client.post('/api/lifeweave/personal' + events, json={**report, 'summary': '另一个判断'}).status_code == 409
    assert client.post('/api/lifeweave/team' + events, json={**report, 'requestId': 'team-request'}).status_code == 404
    post(client, events, {'requestId': 'external-finish-one', 'phase': 'finished', 'summary': '记录真实结果'})
    assert client.post('/api/lifeweave/personal' + events, json={**report, 'requestId': 'later'}).status_code == 409
    listing = client.get('/api/lifeweave/personal' + route).json()['items']
    assert len(listing) == 3
    continuation = client.get(f"/api/lifeweave/personal/items/{item['id']}/continuation").json()
    assert not continuation['runs']
    assert [entry['payload']['phase'] for entry in continuation['externalDevelopment']] == [
        'finished', 'verification', 'started']
    assert continuation['externalDevelopment'][1]['payload']['observedGit']['changedPaths'] == ['feature.txt']
    assert continuation['externalDevelopment'][1]['payload']['reportedChecks'] == ['pytest: passed']
    assert client.get(f"/api/lifeweave/team/items/{item['id']}/continuation").status_code == 404
    conversation = post(client, '/conversations', {
        'requestId': 'external-conversation', 'title': '继续项目知识入口', 'itemId': item['id']})
    prepared = client.app.state.conversations.prepare('personal', conversation['id'], {
        'id': 'unused-turn', 'body': '继续项目知识入口', 'item_id': item['id'],
        'request': {}, 'run_id': None, 'mode': 'discuss'})
    assert [entry['phase'] for entry in prepared['externalDevelopment']] == [
        'finished', 'verification', 'started']
    assert prepared['externalDevelopment'][1]['observedGit']['changedPaths'] == ['feature.txt']


def test_evaluation_tasks_use_frozen_candidate_and_accepted_run_evidence(dedicated_client):
    client = dedicated_client
    item = post(client, '/items', {'itemType': 'research', 'title': '评测攻略整理',
                                   'payload': {'goal': '交付可核验的攻略'}})
    candidate = post(client, '/capabilities', {
        'title': '攻略研究候选', 'target': 'skill',
        'content': '---\nname: game-research\ndescription: 研究游戏攻略\n---\n\n# 任务\n解释依据',
        'desiredBehavior': '解释策略和证据', 'validationPlan': '以真实任务与人工证据评估',
    })
    evaluation = post(client, '/evaluations', {
        'itemId': item['id'], 'targetKind': 'capability', 'candidateId': candidate['id'],
        'title': '攻略研究验证', 'instruction': '整理本轮攻略',
        'criteria': '说明阵容选择的依据、来源与不确定性',
    })
    assert evaluation['candidateVersion'] == candidate['version']
    assert client.get('/api/lifeweave/team/evaluations/'+evaluation['id']).status_code == 404
    assert client.post('/api/lifeweave/team/evaluations/'+evaluation['id']+'/start', json={}).status_code == 404
    knowledge_root = client.app.state.library.roots['personal']
    knowledge_root.mkdir(parents=True, exist_ok=True)
    (knowledge_root/'攻略依据.md').write_text('# 攻略依据\n\n核对游戏版本。', encoding='utf-8')
    method_id = client.app.state.task_sources.catalog('personal')['items'][0]['id']
    started = client.post('/api/lifeweave/personal/evaluations/'+evaluation['id']+'/start',
                          json={'engine': 'codex', 'directory': str(ROOT), 'methodId': method_id,
                                'knowledgeRefs': ['local:攻略依据.md']})
    assert started.status_code == 200, started.text
    run_id = started.json()['runId']
    run = client.get('/api/lifeweave/personal/runs/'+run_id).json()
    assert run['state'] == 'queued'
    assert run['capabilityCandidateId'] == candidate['id']
    assert '说明阵容选择的依据' in run['instruction']
    assert run['repositoryPath'] == str(ROOT)
    assert run['environmentSnapshot']['selectedInputs'] == {
        'methodId': method_id, 'knowledgeRefs': ['local:攻略依据.md']}
    assert any(entry['id'] == method_id for entry in run['capabilities'])
    assert started.json()['run']['selectedInputs']['knowledgeRefs'] == ['local:攻略依据.md']
    ordinary_run = post(client, '/runs', {
        'itemId': item['id'], 'instruction': '沿同一能力继续整理攻略', 'engine': 'codex',
        'capabilityCandidateId': candidate['id'],
    }, 202)
    client.app.state.database_manager.postgres().execute(
        "UPDATE workbench.t_lifeweave_run SET created_at='2026-09-26 00:00:00+00' WHERE id = ANY(%s)",
        ([run_id, ordinary_run['id']],),
    )
    candidate_runs = client.get('/api/lifeweave/personal/runs', params={
        'candidateId': candidate['id'], 'limit': 1,
    }).json()
    assert candidate_runs['total'] == 2
    assert len(candidate_runs['items']) == 1
    assert candidate_runs['items'][0]['id'] == max(run_id, ordinary_run['id'])
    next_page = client.get('/api/lifeweave/personal/runs', params={
        'candidateId': candidate['id'], 'limit': 1, 'offset': 1,
    }).json()
    assert {candidate_runs['items'][0]['id'], next_page['items'][0]['id']} == {run_id, ordinary_run['id']}
    empty_page = client.get('/api/lifeweave/personal/runs', params={
        'candidateId': candidate['id'], 'limit': 1, 'offset': 2,
    }).json()
    assert empty_page['items'] == [] and empty_page['total'] == 2
    assert client.get('/api/lifeweave/team/runs', params={'candidateId': candidate['id']}).json()['total'] == 0
    assert client.post('/api/lifeweave/personal/evaluations/'+evaluation['id']+'/start', json={}).status_code == 409
    assessment = {'outcome': 'passed', 'assessment': '符合原定标准', 'evidenceId': 'missing'}
    assert client.post('/api/lifeweave/personal/evaluations/'+evaluation['id']+'/assess', json=assessment).status_code == 409
    db = client.app.state.database_manager.postgres()
    db.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded', finished_at=now() WHERE id=%s", (run_id,))
    assert client.post('/api/lifeweave/personal/evaluations/'+evaluation['id']+'/assess', json=assessment).status_code == 409
    evidence = post(client, '/items/'+item['id']+'/evidence', {
        'artifactRef': '评测报告', 'artifactVersion': 'v1', 'environmentRef': '受控集成测试',
        'summary': '已人工核对标准', 'runId': run_id,
    })
    post(client, '/evidence/'+evidence['id']+'/review', {'status': 'accepted', 'reason': '符合标准'}, 200)
    manually_verified = client.post('/api/lifeweave/personal/capabilities/'+candidate['id']+'/verify', json={
        'runId': run_id, 'evidenceId': evidence['id'], 'result': 'accepted',
        'assessment': '人工确认本次运行',
    })
    assert manually_verified.status_code == 200, manually_verified.text
    assert client.post('/api/lifeweave/personal/capabilities/'+candidate['id']+'/publish',
                       json={'version': candidate['version']}).status_code == 409
    assessment['evidenceId'] = evidence['id']
    result = client.post('/api/lifeweave/personal/evaluations/'+evaluation['id']+'/assess', json=assessment)
    assert result.status_code == 200, result.text
    assert result.json()['outcome'] == 'passed'
    assert client.get('/api/lifeweave/personal/capabilities/'+candidate['id']).json()['status'] == 'verified'
    assert client.post('/api/lifeweave/personal/evaluations/'+evaluation['id']+'/assess', json=assessment).status_code == 409

    system = post(client, '/evaluations', {
        'itemId': item['id'], 'targetKind': 'system', 'title': '整件事评测',
        'instruction': '交付攻略', 'criteria': '从入口到结果可接续',
    })
    system_run = client.post('/api/lifeweave/personal/evaluations/'+system['id']+'/start', json={}).json()['runId']
    db.execute("UPDATE workbench.t_lifeweave_run SET state='failed', finished_at=now() WHERE id=%s", (system_run,))
    failed = client.post('/api/lifeweave/personal/evaluations/'+system['id']+'/assess',
                         json={'outcome': 'failed', 'assessment': '未形成可读成果'})
    assert failed.status_code == 200 and failed.json()['outcome'] == 'failed'
    improvement_url = '/api/lifeweave/personal/evaluations/'+system['id']+'/improvement'
    improvement_body = {'targetKind': 'harness', 'problem': '未形成可读成果',
                        'desiredBehavior': '保存可读成果和过程',
                        'validationPlan': '沿同一事项与标准重新评测'}
    assert client.post('/api/lifeweave/team/evaluations/'+system['id']+'/improvement',
                       json=improvement_body).status_code == 404
    improved = client.post(improvement_url, json=improvement_body)
    assert improved.status_code == 200, improved.text
    improvement_id = improved.json()['improvementId']
    assert client.post(improvement_url, json=improvement_body).json()['improvementId'] == improvement_id
    entity = client.get('/api/lifeweave/personal/entities/'+improvement_id).json()
    assert entity['payload']['sourceEvaluationId'] == system['id']
    assert entity['payload']['sourceRunId'] == system_run
    assert entity['payload']['validationPlan'] == improvement_body['validationPlan']
    assert any(relation['fromId'] == item['id'] and relation['toId'] == improvement_id
               for relation in client.get('/api/lifeweave/personal/state').json()['relations'])
    listing = client.get('/api/lifeweave/personal/evaluations').json()
    assert listing['total'] == 2 and {row['outcome'] for row in listing['items']} == {'passed', 'failed'}
    copied = {
        'itemId': item['id'], 'targetKind': 'system', 'repeatOf': system['id'],
        'title': '整件事评测 · 再评', 'instruction': '交付攻略', 'criteria': '从入口到结果可接续',
    }
    assert client.post('/api/lifeweave/personal/evaluations', json={**copied, 'criteria': '降低原标准'}).status_code == 409
    repeated = post(client, '/evaluations', copied)
    assert repeated['previous']['outcome'] == 'failed'
    assert repeated['criteria'] == system['criteria'] and repeated['runId'] is None

    candidate_case = {
        'itemId': item['id'], 'targetKind': 'capability', 'candidateId': candidate['id'],
        'title': '攻略研究再评', 'instruction': evaluation['instruction'],
        'criteria': evaluation['criteria'], 'repeatOf': evaluation['id'],
    }
    second = post(client, '/evaluations', candidate_case)
    second_run = client.post('/api/lifeweave/personal/evaluations/'+second['id']+'/start', json={}).json()['runId']
    db.execute("UPDATE workbench.t_lifeweave_run SET state='failed', finished_at=now() WHERE id=%s", (second_run,))
    failed_candidate = client.post('/api/lifeweave/personal/evaluations/'+second['id']+'/assess',
                                   json={'outcome': 'failed', 'assessment': '未达到来源要求'})
    assert failed_candidate.status_code == 200
    publish_url = '/api/lifeweave/personal/capabilities/'+candidate['id']+'/publish'
    assert client.post(publish_url, json={'version': candidate['version']}).status_code == 409

    unrelated = post(client, '/evaluations', {
        'itemId': item['id'], 'targetKind': 'capability', 'candidateId': candidate['id'],
        'title': '更容易但不同的问题', 'instruction': '只给一个建议', 'criteria': '至少给出一个建议',
    })
    unrelated_run = client.post('/api/lifeweave/personal/evaluations/'+unrelated['id']+'/start', json={}).json()['runId']
    db.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded', finished_at=now() WHERE id=%s", (unrelated_run,))
    unrelated_proof = post(client, '/items/'+item['id']+'/evidence', {
        'artifactRef': '简单建议', 'artifactVersion': 'v1', 'environmentRef': '受控集成测试',
        'summary': '更容易的任务通过', 'runId': unrelated_run,
    })
    post(client, '/evidence/'+unrelated_proof['id']+'/review', {'status': 'accepted', 'reason': '符合较低标准'}, 200)
    unrelated_result = client.post('/api/lifeweave/personal/evaluations/'+unrelated['id']+'/assess',
                                   json={'outcome': 'passed', 'assessment': '简单任务通过',
                                         'evidenceId': unrelated_proof['id']})
    assert unrelated_result.status_code == 200, unrelated_result.text
    assert client.post(publish_url, json={'version': candidate['version']}).status_code == 409

    third = post(client, '/evaluations', {**candidate_case, 'title': '攻略研究第三次评测', 'repeatOf': second['id']})
    third_run = client.post('/api/lifeweave/personal/evaluations/'+third['id']+'/start', json={}).json()['runId']
    db.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded', finished_at=now() WHERE id=%s", (third_run,))
    proof = post(client, '/items/'+item['id']+'/evidence', {
        'artifactRef': '第三次评测报告', 'artifactVersion': 'v2', 'environmentRef': '受控集成测试',
        'summary': '再次核对通过', 'runId': third_run,
    })
    post(client, '/evidence/'+proof['id']+'/review', {'status': 'accepted', 'reason': '标准均满足'}, 200)
    passed_again = client.post('/api/lifeweave/personal/evaluations/'+third['id']+'/assess',
                               json={'outcome': 'passed', 'assessment': '已补齐来源', 'evidenceId': proof['id']})
    assert passed_again.status_code == 200
    knowledge_service = client.app.state.lifeweave_knowledge_service
    evaluation_service = client.app.state.lifeweave_evaluations
    original_gate = knowledge_service.evaluation_gate
    gate_entered, release_gate, create_entered = Event(), Event(), Event()

    def held_gate(workspace, candidate_id, version):
        gate_entered.set()
        assert release_gate.wait(5)
        original_gate(workspace, candidate_id, version)

    def create_during_publish():
        create_entered.set()
        return evaluation_service.create('personal', {
            **candidate_case, 'title': '发布并发新任务', 'repeatOf': third['id'],
        })

    knowledge_service.evaluation_gate = held_gate
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            publication = workers.submit(knowledge_service.publish, 'personal', candidate['id'],
                                         candidate['version'], 'admin')
            assert gate_entered.wait(5)
            simultaneous_create = workers.submit(create_during_publish)
            assert create_entered.wait(5)
            sleep(0.2)
            assert not simultaneous_create.done()  # candidate lock spans gate and publication
            release_gate.set()
            assert publication.result(timeout=5)['status'] == 'published'
            with pytest.raises(ValueError, match='只能评测试验中的能力候选'):
                simultaneous_create.result(timeout=5)
    finally:
        release_gate.set()
        knowledge_service.evaluation_gate = original_gate
    published = client.post(publish_url, json={'version': candidate['version']})
    assert published.status_code == 200 and published.json()['status'] == 'published'
    history_url = '/api/lifeweave/personal/capabilities/'+candidate['id']+'/evaluations'
    history = client.get(history_url, params={'limit': 2}).json()
    assert history['total'] == 4 and len(history['items']) == 2
    assert history['items'][0]['id'] == third['id']
    assert history['items'][0]['runId'] == third_run
    assert history['items'][0]['evidence'][0]['status'] == 'accepted'
    assert client.get(history_url, params={'limit': 2, 'offset': 2}).json()['total'] == 4
    assert client.get(history_url.replace('/personal/', '/team/')).status_code == 404


def test_successor_candidate_must_resolve_predecessor_failure_under_original_standard(dedicated_client):
    client = dedicated_client
    item = post(client, '/items', {'itemType': 'research', 'title': '能力改进链',
                                   'payload': {'goal': '修复来源遗漏并复测'}})
    predecessor = post(client, '/capabilities', {
        'title': '来源说明', 'target': 'agent', 'content': '初版：总结结果',
        'desiredBehavior': '说明依据', 'validationPlan': '保留来源后复测',
    })
    failed_task = post(client, '/evaluations', {
        'itemId': item['id'], 'targetKind': 'capability', 'candidateId': predecessor['id'],
        'title': '来源完整性', 'instruction': '给出有来源的答复', 'criteria': '逐项写出资料来源',
    })
    failed_run = client.post('/api/lifeweave/personal/evaluations/'+failed_task['id']+'/start', json={}).json()['runId']
    db = client.app.state.database_manager.postgres()
    db.execute("UPDATE workbench.t_lifeweave_run SET state='failed', finished_at=now() WHERE id=%s", (failed_run,))
    failed = client.post('/api/lifeweave/personal/evaluations/'+failed_task['id']+'/assess',
                         json={'outcome': 'failed', 'assessment': '遗漏来源'})
    assert failed.status_code == 200
    improvement = client.post('/api/lifeweave/personal/evaluations/'+failed_task['id']+'/improvement', json={
        'targetKind': 'agent', 'problem': '遗漏来源', 'desiredBehavior': '逐项引用来源',
        'validationPlan': '沿原标准复测',
    }).json()
    successor_body = {
        'title': '来源说明', 'target': 'agent', 'content': '新版：逐项引用来源',
        'desiredBehavior': '说明依据', 'validationPlan': '沿原标准复测',
        'predecessorCandidateId': predecessor['id'], 'sourceEntityId': improvement['improvementId'],
    }
    assert client.post('/api/lifeweave/team/capabilities', json=successor_body).status_code == 404
    assert client.post('/api/lifeweave/personal/capabilities',
                       json={**successor_body, 'target': 'harness'}).status_code == 409
    successor = post(client, '/capabilities', successor_body)
    assert successor['predecessorCandidateId'] == predecessor['id']

    def pass_task(task: dict, artifact: str) -> None:
        run = client.post('/api/lifeweave/personal/evaluations/'+task['id']+'/start', json={}).json()['runId']
        db.execute("UPDATE workbench.t_lifeweave_run SET state='succeeded', finished_at=now() WHERE id=%s", (run,))
        proof = post(client, '/items/'+item['id']+'/evidence', {
            'artifactRef': artifact, 'artifactVersion': 'v1', 'environmentRef': '受控集成测试',
            'summary': '按当前标准审阅', 'runId': run,
        })
        post(client, '/evidence/'+proof['id']+'/review', {'status': 'accepted', 'reason': '符合本次标准'}, 200)
        response = client.post('/api/lifeweave/personal/evaluations/'+task['id']+'/assess', json={
            'outcome': 'passed', 'assessment': '符合本次标准', 'evidenceId': proof['id'],
        })
        assert response.status_code == 200, response.text

    easier = post(client, '/evaluations', {
        'itemId': item['id'], 'targetKind': 'capability', 'candidateId': successor['id'],
        'title': '简单答复', 'instruction': '给一个结论', 'criteria': '有一个结论',
    })
    pass_task(easier, '简单答复')
    publish_url = '/api/lifeweave/personal/capabilities/'+successor['id']+'/publish'
    assert client.post(publish_url, json={'version': successor['version']}).status_code == 409
    repaired = post(client, '/evaluations', {
        'itemId': item['id'], 'targetKind': 'capability', 'candidateId': successor['id'],
        'repeatOf': failed_task['id'], 'title': '来源完整性 · 新候选复测',
        'instruction': failed_task['instruction'], 'criteria': failed_task['criteria'],
    })
    pass_task(repaired, '有来源的答复')
    published = client.post(publish_url, json={'version': successor['version']})
    assert published.status_code == 200 and published.json()['status'] == 'published'
    history = client.get('/api/lifeweave/personal/capabilities/'+successor['id']+'/evaluations').json()
    assert history['total'] == 3
    assert [row['id'] for row in history['lineage']] == [successor['id'], predecessor['id']]
    assert {row['id'] for row in history['items']} == {failed_task['id'], easier['id'], repaired['id']}


def test_home_layout_is_durable_and_separate_for_personal_and_team(dedicated_client):
    client = dedicated_client
    layout = {'cards': [{'key': 'capture', 'column': 'main', 'visible': True},
                        {'key': 'attention', 'column': 'aside', 'visible': False}]}
    saved = client.put('/api/lifeweave/personal/preferences/home-view',
                       json={'version': None, 'payload': layout})
    assert saved.status_code == 200, saved.text
    personal = client.get('/api/lifeweave/personal/state').json()
    team = client.get('/api/lifeweave/team/state').json()
    assert next(row for row in personal['preferences'] if row['preferenceKey'] == 'home-view')['payload'] == layout
    assert not any(row['preferenceKey'] == 'home-view' for row in team['preferences'])
    assert client.put('/api/lifeweave/personal/preferences/home-view',
                      json={'version': None, 'payload': {}}).status_code == 409
    barrier = Barrier(3)

    def competing_save(marker: str):
        barrier.wait(timeout=5)
        return client.put('/api/lifeweave/personal/preferences/home-view',
                          json={'version': saved.json()['version'], 'payload': {'marker': marker}})

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(competing_save, 'first')
        second = workers.submit(competing_save, 'second')
        barrier.wait(timeout=5)
        results = [first.result(timeout=5), second.result(timeout=5)]
    assert sorted(response.status_code for response in results) == [200, 409]
    winner = next(response.json()['payload'] for response in results if response.status_code == 200)
    personal_after = client.get('/api/lifeweave/personal/state').json()
    assert next(row for row in personal_after['preferences'] if row['preferenceKey'] == 'home-view')['payload'] == winner


def test_library_links_are_derived_from_current_markdown_and_keep_scope(dedicated_client):
    client = dedicated_client
    root = client.app.state.library.roots['personal']
    notes = root / 'notes'
    notes.mkdir(parents=True)
    source = notes / '甲.md'
    target = notes / '乙.md'
    source.write_text('# 甲\n\n[乙](%E4%B9%99.md#section) 和 [乙再读](乙.md?view=1)\n\n'
                      '[失效](未建.md) [越界](../../secret.md) ![图](乙.md)\n\n'
                      '```markdown\n[假链接](乙.md)\n```\n', encoding='utf-8')
    target.write_text('# 乙\n\n[返回甲](甲.md)\n', encoding='utf-8')
    url = '/api/lifeweave/personal/library/links'
    current = client.get(url, params={'sourceId': 'local', 'path': 'notes/乙.md'})
    assert current.status_code == 200, current.text
    body = current.json()
    assert body['scannedDocuments'] == 2
    assert body['outgoing'][0]['path'] == 'notes/甲.md'
    assert body['backlinks'] == [{'sourceId': 'local', 'path': 'notes/甲.md', 'title': '甲', 'label': '乙', 'count': 2}]
    from_source = client.get(url, params={'sourceId': 'local', 'path': 'notes/甲.md'}).json()
    assert {row['status'] for row in from_source['outgoing']} == {'valid', 'missing', 'blocked'}
    assert len(from_source['outgoing']) == 3  # image and fenced code are not knowledge links
    assert client.get('/api/lifeweave/team/library/links', params={'path': 'notes/乙.md'}).status_code == 404

    hidden = root / '.hidden'
    hidden.mkdir()
    (hidden / 'secret.md').write_text('# 不可见', encoding='utf-8')
    (notes / 'alias.md').symlink_to(hidden / 'secret.md')
    assert client.get('/api/lifeweave/personal/library/document', params={'path': 'notes/alias.md'}).status_code == 409
    source.write_text('# 甲\n\n不再引用乙。\n', encoding='utf-8')
    assert client.get(url, params={'path': 'notes/乙.md'}).json()['backlinks'] == []


def test_legacy_api_keeps_method_body_query_and_same_data(client):
    old = '/api/gongzuo/personal/items'
    redirect = client.post(old, json={'itemType':'other','title':'旧入口继续使用'}, follow_redirects=False)
    assert redirect.status_code == 308
    assert redirect.headers['location'] == '/api/lifeweave/personal/items'
    created = client.post(old, json={'itemType':'other','title':'旧入口继续使用'})
    assert created.status_code == 201
    item_id = created.json()['id']
    assert client.get('/api/lifeweave/personal/items/'+item_id).json()['title'] == '旧入口继续使用'
    redirect = client.get('/api/gongzuo/personal/runs?state=failed&limit=5', follow_redirects=False)
    assert redirect.headers['location'] == '/api/lifeweave/personal/runs?state=failed&limit=5'
    assert client.post(old, json={}, headers={'Origin':'https://outside.example'}, follow_redirects=False).status_code == 403


def test_persistent_work_context_conflict_and_acceptance(client):
    item = post(client, '/items', {'itemType':'research','title':'真实数据库纵切','payload':{'goal':'明确结果'}})
    path = '/api/lifeweave/personal/items/'+item['id']
    assert client.get(path).json()['context']['content']['goal'] == '明确结果'
    assert client.get(path.replace('/personal/', '/team/')).status_code == 404
    accepted = client.post(path+'/accept', json={'version':1})
    assert accepted.status_code == 400
    changed = client.patch(path, json={'version':1,'status':'planned','payload':{'priority':2,'due':'2026-09-30'}})
    assert changed.status_code == 200, changed.text
    assert client.patch(path, json={'version':1,'title':'过时编辑'}).status_code == 409
    proposal = post(client, '/items/'+item['id']+'/context/proposals', {'baseVersion':1,'title':'补充目标','proposedContent':{'goal':'可核验的新目标'},'provenance':[]})
    post(client, '/context-proposals/'+proposal['id']+'/accept', {'version':1}, 200)
    assert client.get(path).json()['context']['content']['goal'] == '可核验的新目标'
    evidence = post(client, '/items/'+item['id']+'/evidence', {'artifactRef':'docs/result.md','artifactVersion':'test-v1','environmentRef':'isolated-integration-db','summary':'人工验证结果'})
    post(client, '/evidence/'+evidence['id']+'/review', {'status':'accepted','reason':'结果符合预期'}, 200)
    row = client.get(path).json()
    post(client, '/items/'+item['id']+'/accept', {'version':row['version']}, 200)
    assert client.get(path).json()['status'] == 'completed'


def test_knowledge_review_conflicts_and_external_read_only(client, tmp_path):
    library = client.app.state.library
    target = library.roots['personal']/'学习'/'笔记.md'
    draft = post(client,'/library/revisions',{'path':'学习/笔记.md','content':'# 笔记\n\n第一版','baseVersion':'new','reason':'真实审阅'})
    assert not target.exists()
    post(client,'/library/revisions/'+draft['id']+'/decision',{'accept':True},200)
    assert target.read_text() == '# 笔记\n\n第一版'
    doc = client.get('/api/lifeweave/personal/library/document', params={'path':'学习/笔记.md'}).json()
    draft2 = post(client,'/library/revisions',{'path':doc['path'],'content':'# 笔记\n第二版','baseVersion':doc['version'],'reason':'冲突验证'})
    target.write_text('# 笔记\n来自本地编辑器的新内容')
    response = client.post('/api/lifeweave/personal/library/revisions/'+draft2['id']+'/decision',json={'accept':True})
    assert response.status_code == 409
    assert '本地编辑器' in target.read_text()
    post(client,'/library/revisions/'+draft2['id']+'/decision',{'accept':False},200)
    outside = tmp_path/'external'; outside.mkdir(); file = outside/'index.md'; file.write_text('# 原知识\n独立来源')
    source = post(client,'/library/sources',{'title':'外部来源','root':str(outside)})
    doc = library.document('personal', source['id'], 'index.md')
    draft3 = post(client,'/library/revisions',{'sourceId':source['id'],'path':'index.md','content':'不可静默覆盖','baseVersion':doc['version'],'reason':'边界'})
    response = client.post('/api/lifeweave/personal/library/revisions/'+draft3['id']+'/decision',json={'accept':True})
    assert response.status_code == 409 and file.read_text() == '# 原知识\n独立来源'
    assert client.get('/api/lifeweave/team/library/document', params={'path':'index.md','sourceId':source['id']}).status_code == 404
    for path in ('../index.md','raw/index.md','/etc/passwd','.hidden.md'):
        assert client.get('/api/lifeweave/personal/library/document',params={'path':path}).status_code == 409
    (library.roots['personal']/'escape.md').symlink_to(file)
    assert client.get('/api/lifeweave/personal/library/document',params={'path':'escape.md'}).status_code == 409


class FakeLinear:
    def __init__(self):
        self.remote = {'id':'source-id','identifier':'TEST-1','title':'远程标题','description':'原描述','url':'https://linear.app/example/issue/TEST-1','updatedAt':'2026-09-18T00:00:00Z','priority':3}
        self.comments = {}; self.writes = 0; self.timeout = False
    def issue(self, identity): return dict(self.remote)
    def query(self, query, variables):
        if 'mutation' in query:
            self.writes += 1
            value = variables['input']; self.comments[value['id']] = {'id':value['id'],'body':value['body']}
            if self.timeout: raise ValueError('模拟响应丢失')
            return {'commentCreate':{'success':True,'comment':self.comments[value['id']]}}
        return {'comment':self.comments.get(variables['id'])}


def test_linear_import_preserves_local_and_publish_readback_is_idempotent(client):
    from src.integrations.linear import LinearService
    fake = FakeLinear()
    service = LinearService(client.app.state.database_manager.postgres(), fake, client.app.state.lifeweave_service)
    imported = service.import_issue('personal','TEST-1')
    item = service.work.get_item('personal', imported['itemId'])
    service.work.update_item('personal', item['id'], version=item['version'], title='本地重新澄清', status=None, payload={'due':None,'priority':1}, actor_id='local-user')
    fake.remote['title'] = '远程后来改过'; fake.remote['priority'] = 4
    assert service.import_issue('personal','TEST-1')['created'] is False
    after = service.work.get_item('personal', item['id'])
    assert after['title'] == '本地重新澄清' and after['payload'] == {'due':None,'priority':1}
    prepared = service.prepare('personal', item['id'], '## 真实正文预览\n固定内容')
    assert fake.writes == 0
    fake.timeout = True
    with pytest.raises(ValueError, match='响应丢失'): service.publish('personal',prepared['id'])
    assert service.publish('personal',prepared['id'])['status'] == 'confirmed'
    service.publish('personal',prepared['id'])
    assert fake.writes == 1


def test_task_inputs_are_frozen_and_run_limits_are_enforced(client, tmp_path):
    root = tmp_path/'skills'; method = root/'focused'; method.mkdir(parents=True)
    (method/'SKILL.md').write_text('---\nname: focused\ndescription: 有界方法\n---\n\n读 references/example.md')
    (method/'references').mkdir(); support = method/'references/example.md'; support.write_text('原方法依据')
    catalog = post(client,'/methods/roots',{'root':str(root)},200)
    method_id = catalog['items'][0]['id']
    item = post(client,'/items',{'itemType':'research','title':'验证委托输入','payload':{}})
    refs=[]
    for number in range(10):
        name=f'combination-{number}.md'
        (client.app.state.library.roots['personal']/name).write_text(f'# 文档 {number}\n独立事实 {number}')
        refs.append('local:'+name)
    payload = {'itemId':item['id'],'instruction':'只分析指定依据','engine':'codex','methodId':method_id,'knowledgeRefs':refs}
    run = post(client,'/runs',payload,202)
    snapshot = client.app.state.lifeweave_runtime_service.get_run_snapshot('personal',run['id'])
    entries = snapshot['capability_snapshot']
    assert len(entries) == 11 and entries[0]['files']['references/example.md'] == '原方法依据'
    support.write_text('源方法后来变化')
    assert snapshot['capability_snapshot'][0]['files']['references/example.md'] == '原方法依据'
    assert client.post('/api/lifeweave/personal/runs',json={**payload,'knowledgeRefs':['local:学习/笔记.md']*11}).status_code == 422
    assert client.post('/api/lifeweave/personal/runs',json={**payload,'methodId':'missing'}).status_code == 409
    cancelled = post(client,'/runs/'+run['id']+'/cancel',{},200)
    assert cancelled['state'] == 'cancelled'
    retry = post(client,'/runs/'+run['id']+'/retry',{'syncContext':True},202)
    assert client.app.state.lifeweave_runtime_service.get_run_snapshot('personal',retry['id'])['capability_snapshot'][0]['files']['references/example.md'] == '原方法依据'


def test_origin_boundary(client):
    assert client.post('/api/lifeweave/personal/items',json={'itemType':'personal','title':'不应创建'},headers={'Origin':'https://elsewhere.test'}).status_code == 403


def test_manual_result_body_is_readable_and_duplicate_save_is_idempotent(client):
    item=post(client,'/items',{'itemType':'research','title':'人工工作闭环','payload':{}})
    body={'title':'验证记录','content':'# 实际结果\n正文可阅读','verification':'已核对关键路径；远程协作尚未覆盖','environment':'本机浏览器'}
    first=post(client,'/items/'+item['id']+'/manual-results',body)
    again=post(client,'/items/'+item['id']+'/manual-results',body)
    assert first==again
    detail=client.get('/api/lifeweave/personal/items/'+item['id']).json()
    assert len(detail['evidence'])==1 and detail['evidence'][0]['payload']['body']==body['content']
    entity=client.get('/api/lifeweave/personal/entities/'+first['artifactId']).json()
    assert entity['payload']['body']==body['content']
    assert client.post('/api/lifeweave/team/items/'+item['id']+'/manual-results',json=body).status_code==404


def test_current_context_reaches_lists_meeting_and_export_without_rewriting_snapshot(client):
    item=post(client,'/items',{'itemType':'research','title':'多入口共识验证','payload':{'goal':'旧目标','scope':'旧范围','owner':'独立负责人'}})
    meeting=client.get('/api/lifeweave/personal/state').json()['meeting']
    response=client.put('/api/lifeweave/personal/meeting',json={'version':meeting['version'],'config':{'title':'范围验证','sections':[{'key':'deliveries','title':'交付','enabled':True,'mode':'generic','filters':{'itemIds':[item['id']]},'fields':['title','payload'],'payloadFields':['goal','scope','owner']}]}})
    assert response.status_code==200,response.text
    snapshot=post(client,'/meeting/freeze',{})
    proposal=post(client,'/items/'+item['id']+'/context/proposals',{'baseVersion':1,'title':'澄清目标','proposedContent':{'goal':'新目标','scope':'新范围'}})
    pending=next(row for row in client.get('/api/lifeweave/personal/state').json()['items'] if row['id']==item['id'])
    assert pending['contextProposals'][0]['id']==proposal['id']
    post(client,'/context-proposals/'+proposal['id']+'/accept',{'version':1},200)
    current=next(row for row in client.get('/api/lifeweave/personal/state').json()['items'] if row['id']==item['id'])
    assert current['context']['content']['goal']=='新目标' and current['payload']['goal']=='旧目标'
    preview=client.get('/api/lifeweave/personal/meeting/preview').json()
    assert preview['sections'][0]['entries'][0]['values']['payload']=={'goal':'新目标','scope':'新范围','owner':'独立负责人'}
    exported=client.get('/api/lifeweave/personal/meeting/markdown').text
    assert '目标：新目标' in exported and '范围：新范围' in exported
    frozen=client.get('/api/lifeweave/personal/meeting/markdown',params={'snapshotId':snapshot['id']}).text
    assert '目标：旧目标' in frozen and '新目标' not in frozen


def test_team_local_worker_requires_explicit_account_choice(client):
    response=client.put('/api/lifeweave/team/settings/local-worker',json={'enabled':True,'useLocalAccount':False})
    assert response.status_code==409
    assert client.get('/api/lifeweave/team/settings').json()['localWorker']['enabled'] is False


def test_continuation_feedback_is_idempotent_scoped_and_pinned_in_next_run(client):
    item = post(client, '/items', {'itemType':'research','title':'维护噪声识别方法','initialContext':{'goal':'先讨论误报的适用范围，不做代码'}})
    path = '/items/' + item['id']
    payload = {'body':'重点是标注分歧，先不要比较训练速度','requestId':'feedback-once'}
    first = post(client, path+'/feedback', payload)
    again = post(client, path+'/feedback', payload)
    assert first == again
    assert client.post('/api/lifeweave/personal'+path+'/feedback',json={**payload,'body':'不同内容'}).status_code == 409
    assert client.post('/api/lifeweave/team'+path+'/feedback',json=payload).status_code == 404
    assert client.post('/api/lifeweave/personal'+path+'/feedback',json={**payload,'runId':'missing'}).status_code == 400
    assert client.post('/api/lifeweave/personal'+path+'/feedback',json={**payload,'body':'  '}).status_code == 400
    current = client.get('/api/lifeweave/personal'+path+'/continuation').json()
    assert current['context']['content']['goal'] == '先讨论误报的适用范围，不做代码'
    assert [f['id'] for f in current['feedback']] == [first['id']]
    run = post(client, '/runs', {'itemId':item['id'],'instruction':'只讨论','engine':'codex'}, 202)
    runtime = client.app.state.lifeweave_runtime_service
    original = runtime.get_run_snapshot('personal',run['id'])['prompt_snapshot']
    assert payload['body'] in original
    second = post(client, path+'/feedback', {'body':'补充考虑漏检','requestId':'feedback-two','runId':run['id']})
    post(client, '/runs/'+run['id']+'/cancel', {}, 200)
    retried = post(client, '/runs/'+run['id']+'/retry', {'syncContext':False}, 202)
    snapshot = runtime.get_run_snapshot('personal', retried['id'])
    assert [f['id'] for f in snapshot['environment_snapshot']['feedbackSnapshot']] == [first['id'], second['id']]
    assert '补充考虑漏检' in snapshot['prompt_snapshot']
    assert runtime.get_run_snapshot('personal',run['id'])['prompt_snapshot'] == original
    third = post(client, '/items', {'itemType':'personal','title':'另一项生活工作'})
    assert client.post('/api/lifeweave/personal/items/'+third['id']+'/feedback',json={'body':'不属于这个事项','requestId':'wrong-run','runId':run['id']}).status_code == 400


def test_discovery_and_recommendations_reuse_accepted_knowledge_without_a_paper_fixture(client, tmp_path):
    idea = post(client, '/entities', {'entityType':'idea','title':'整理阳台植物','payload':{'body':'想了解采光，暂时只记录'}})
    assert any(row['id'] == idea['id'] for row in client.get('/api/lifeweave/personal/work-discovery?query=阳台采光').json()['items'])
    item = post(client, '/items', {'itemType':'personal','title':'阳台采光记录','initialContext':{'goal':'比较朝向对植物采光的影响'}})
    draft = post(client, '/library/revisions', {'path':'生活/采光.md','content':'# 阳台采光\n植物朝向影响照射时长。','baseVersion':'new','reason':'已有领域知识'})
    post(client, '/library/revisions/'+draft['id']+'/decision', {'accept':True}, 200)
    method = tmp_path/'methods'/'lighting'; method.mkdir(parents=True)
    (method/'SKILL.md').write_text('---\nname: lighting\ndescription: 比较植物采光的观察方法\n---\n\n保留朝向、时间与实际观察。')
    post(client, '/methods/roots', {'root':str(method.parent)}, 200)
    path = '/api/lifeweave/personal/items/'+item['id']+'/input-recommendations'
    before = client.get(path).json()
    assert 'local:生活/采光.md' in before['suggested']['knowledgeRefs']
    assert before['methods'][0]['title'] == 'lighting'
    full = client.get('/api/lifeweave/personal/methods/'+before['methods'][0]['id'])
    assert full.status_code == 200 and '保留朝向' in full.json()['content']
    assert full.json()['version'] == before['methods'][0]['version']
    assert client.get('/api/lifeweave/team/methods/'+before['methods'][0]['id']).status_code == 409
    assert before['methods'][0]['matchedTerms'] and before['documents'][0]['version']
    version = next(d['version'] for d in before['documents'] if d['ref'] == 'local:生活/采光.md')
    (client.app.state.library.roots['personal']/'生活/采光.md').write_text('# 阳台采光\n补充新观察')
    run = post(client, '/runs', {'itemId':item['id'],'instruction':'观察植物采光','engine':'codex',**before['suggested']}, 202)
    snapshot = client.app.state.lifeweave_runtime_service.get_run_snapshot('personal',run['id'])
    doc = next(d for d in snapshot['capability_snapshot'] if d.get('sourcePath') == 'local:生活/采光.md')
    assert doc['version'] != version and '补充新观察' in doc['content']
    assert snapshot['environment_snapshot']['inputRecommendations']['strategy'] == 'lexical-v1'
    assert client.get(path.replace('/personal/','/team/')).status_code == 404
    assert client.get('/api/lifeweave/team/work-discovery?query=阳台').json()['items'] == []
    assert client.get('/api/lifeweave/personal/work-discovery?query=zyxwuniqueunmatched').json()['items'] == []


def test_worker_http_reports_keep_input_provenance_and_retry_uses_current_feedback(client):
    runtime = client.app.state.lifeweave_runtime_service
    base = '/api/lifeweave/team'

    def send(path, body, status=200, headers=None):
        response = client.post(base+path, json=body, headers=headers)
        assert response.status_code == status, response.text
        return response.json()

    machine = send('/machines/register', {'name':'input provenance regression','capacity':1,
                   'engines':['codex'],'runtimes':['native']}, 201,
                   {'X-LifeWeave-Registration-Token':runtime.registration_tokens['team']})
    auth = {'X-LifeWeave-Worker-Token':machine['workerToken']}
    item = send('/items', {'itemType':'research','title':'运行全过程保留依据'}, 201)
    feedback_path = '/items/'+item['id']+'/feedback'
    first = send(feedback_path, {'body':'先核对依据','requestId':'before-running'}, 201)
    run = send('/runs', {'itemId':item['id'],'instruction':'核对依据','engine':'codex',
                        'machineId':machine['id']}, 202)
    fixed = run['environmentSnapshot']
    original_prompt = runtime.get_run_snapshot('team', run['id'])['prompt_snapshot']
    claim = send('/worker/'+machine['id']+'/claim', {'leaseSeconds':30}, headers=auth)
    assert claim['id'] == run['id']
    report_path = '/worker/'+machine['id']+'/runs/'+run['id']+'/report'
    for outcome, environment in (
        ('running', {'runtime':'native','actualDirectory':'/isolated/task',
                     'feedbackSnapshot':[], 'selectedInputs':{'forged':True},
                     'inputRecommendations':{'forged':True}}),
        ('succeeded', {'exitObserved':True}),
    ):
        saved = send(report_path, {'leaseId':claim['lease_id'],'outcome':outcome,
                                  'exitCode':0,'environment':environment}, headers=auth)
        actual = saved['environmentSnapshot']
        for key in ('feedbackSnapshot','selectedInputs','inputRecommendations','requestedRuntime'):
            assert actual[key] == fixed[key]
        assert actual['actualDirectory'] == '/isolated/task'
    current = client.get(base+'/runs/'+run['id']).json()
    assert current['environmentSnapshot']['feedbackSnapshot'][0]['id'] == first['id']
    second = send(feedback_path, {'body':'补充第二轮问题','requestId':'after-running','runId':run['id']}, 201)
    retry = send('/runs/'+run['id']+'/retry', {'syncContext':False}, 202)
    assert [f['id'] for f in retry['environmentSnapshot']['feedbackSnapshot']] == [first['id'],second['id']]
    assert retry['environmentSnapshot']['selectedInputs'] == fixed['selectedInputs']
    assert runtime.get_run_snapshot('team', run['id'])['prompt_snapshot'] == original_prompt


@pytest.mark.parametrize('transport', ['http', 'local'])
def test_pdf_nul_does_not_abort_worker_and_original_evidence_is_recoverable(dedicated_client, transport):
    import asyncio
    import base64
    import hashlib
    import json
    from src.lifeweave_runtime.worker import ServiceWorkerClient

    client = dedicated_client
    runtime = client.app.state.lifeweave_runtime_service
    base = '/api/lifeweave/personal'
    registered = client.post(base+'/machines/register', json={
        'name': 'PDF NUL '+transport, 'capacity': 1, 'engines': ['codex'], 'runtimes': ['native'],
    }, headers={'X-LifeWeave-Registration-Token': runtime.registration_tokens['personal']})
    assert registered.status_code == 201, registered.text
    machine = registered.json()
    auth = {'X-LifeWeave-Worker-Token': machine['workerToken']}
    prefix = base+'/worker/'+machine['id']
    local = ServiceWorkerClient(runtime, 'personal', machine['id'], machine['workerToken'])
    item = post(client, '/items', {'itemType': 'research', 'title': 'PDF 控制字符回归 '+transport})
    run = post(client, '/runs', {'itemId': item['id'], 'instruction': '读取论文',
                               'engine': 'codex', 'machineId': machine['id']}, 202)
    claim = client.post(prefix+'/claim', json={'leaseSeconds': 30}, headers=auth).json()
    assert claim['id'] == run['id']

    def send(kind, body):
        if transport == 'local':
            return asyncio.run(getattr(local, kind)(run['id'], body))
        response = client.post(prefix+'/runs/'+run['id']+'/'+('events' if kind == 'event' else kind),
                               json=body, headers=auth)
        assert response.status_code in (200, 201, 202), response.text
        return response.json()

    send('report', {'lease_id': claim['lease_id'], 'outcome': 'running'})
    original_event = {
        'event_type': 'item.completed', 'source': 'codex', 'channel': 'stdout',
        'summary': 'PDF 提取\0完成',
        'payload': {'item': {'text': 'ADEn\0中文\n下一行', 'literal': r'\u0000',
                             'nested': [{'\0key': '原值', '␀key': '另一个键'}]}},
    }
    send('event', {'lease_id': claim['lease_id'], **original_event})
    events = client.get(base+'/runs/'+run['id']+'/events').json()['items']
    event = next(entry for entry in events if entry['eventType'] == 'item.completed')
    assert event['summary'] == 'PDF 提取␀完成'
    encoded = event['payload']['_lifeweaveTextStorage']['originalJsonBase64']
    assert json.loads(base64.b64decode(encoded)) == original_event
    assert event['payload']['item']['literal'] == r'\u0000'
    assert len(event['payload']['item']['nested'][0]['entries']) == 2
    report = {'lease_id': claim['lease_id'], 'outcome': 'succeeded', 'exit_code': 0,
              'result': '# 论文\n\n公式 ADEn\0已提取',
              'result_payload': {'report': '# 论文\n\n公式 ADEn\0已提取'},
              'environment': {'reader': 'PDF\0reader', 'selectedInputs': {'forged': True}}}
    version = 'sha256:'+hashlib.sha256(report['result'].encode()).hexdigest()
    report['artifacts'] = [{'kind': 'executor-result', 'version': version}]
    send('report', report)
    saved = client.get(base+'/runs/'+run['id']).json()
    assert saved['state'] == 'succeeded' and '␀' in saved['result']
    assert saved['environmentSnapshot']['selectedInputs'] == run['environmentSnapshot']['selectedInputs']
    encoded = saved['environmentSnapshot']['_lifeweaveTextStorage']['originalJsonBase64']
    recovered = json.loads(base64.b64decode(encoded))
    assert recovered['result'] == report['result']
    assert recovered['result_payload'] == report['result_payload']
    output = client.get(base+'/items/'+item['id']+'/research-output').json()['current']
    assert output['content'] == '# 论文\n\n公式 ADEn␀已提取'
    assert 'NUL' in output['storageNote'] and output['rawDownloadUrl'].endswith('/artifacts/result')
    artifact = client.get(output['rawDownloadUrl'])
    assert artifact.content == report['result'].encode()
    assert artifact.headers['X-Artifact-Version'] == 'sha256:'+hashlib.sha256(artifact.content).hexdigest()
    readable = client.get(output['downloadUrl'])
    assert readable.text == output['content']
    assert readable.headers['ETag'] == '"'+hashlib.sha256(readable.content).hexdigest()+'"'
    candidate = post(client, '/items/'+item['id']+'/knowledge-candidates', {
        'runId': run['id'], 'path': '研究/NUL-'+transport+'.md', 'content': output['content'],
        'baseVersion': 'new', 'reason': '保留提取字符的解释边界', 'requestId': 'nul-knowledge',
    })
    assert candidate['references']['warnings'] == [output['storageNote']]
    post(client, '/library/revisions/'+candidate['id']+'/decision', {'accept': True}, 200)
    document = client.get(base+'/library/document', params={'path': '研究/NUL-'+transport+'.md'}).json()
    assert document['references']['warnings'] == [output['storageNote']]
