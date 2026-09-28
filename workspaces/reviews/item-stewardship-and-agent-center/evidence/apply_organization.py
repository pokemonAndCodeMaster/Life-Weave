"""Apply the reviewed organization mapping through the public product API.
No status, context or artifact writes; source snapshots remain the authority.
Run once after the new service is deployed; repeat is guarded by exact batch IDs.
"""
from pathlib import Path
import argparse,hashlib,json,urllib.request,urllib.error

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8010/api/lifeweave/'

def call(workspace,path,body=None,method=None):
    request=urllib.request.Request(BASE+workspace+path,
        data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,
        headers={'Content-Type':'application/json'},method=method)
    try:
        with urllib.request.urlopen(request,timeout=90) as response:return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'{workspace}{path}: {exc.code} '+exc.read().decode()) from exc

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8010');parser.add_argument('--evidence-prefix',default='')
    args=parser.parse_args();BASE=args.url+'/api/lifeweave/'
    output=ROOT/'evidence'/args.evidence_prefix;output.mkdir(parents=True,exist_ok=True)
    plan=json.loads((ROOT/'organization-plan.json').read_text())
    baseline=json.loads((ROOT/'evidence/organization-before.json').read_text())
    receipts={}
    for workspace,scope in plan.items():
        state=call(workspace,'/state')
        entities={ (kind,entry['title']):entry['id'] for kind,key in [('topic','topics'),('domain','domains')] for entry in state[key] }
        for entry in scope['entities']:
            key=(entry['entityType'],entry['title'])
            if key not in entities:entities[key]=call(workspace,'/entities',entry)['id']
        current={entry['id']:entry for entry in state['items']}
        changes=[]
        for assignment in scope['assignments']:
            change={'itemId':assignment['itemId'],'itemVersion':current[assignment['itemId']]['version'],
                    'topicIds':[entities['topic',title] for title in assignment['topics']],
                    'domainIds':[entities['domain',title] for title in assignment['domains']],
                    'reason':assignment['reason']}
            if 'parentId' in assignment:change['parentId']=assignment['parentId']
            changes.append(change)
        proposal=call(workspace,'/item-organization/proposals',{
            'requestId':f'current-organization-{workspace}-20260928',
            'reason':'用户要求实际规整现有事项；按原目标核对并保留全部事项、状态、讨论和成果。',
            'changes':changes,'groups':scope['groups']})
        (output/f'{workspace}-organization-proposal.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2))
        anchor='item-c0f13d85b5c145fd' if workspace=='personal' else 'item-2cab593824114b90'
        execution=call(workspace,f'/items/{anchor}/agent-dispatch',{
            'requestId':f'apply-organization-{workspace}-20260928','agentId':'item-steward','mode':'organization',
            'instruction':'按已核对的存量事项目标应用可撤销的组织变更，不更改业务状态或成果。',
            'organization':{'action':'apply','proposalId':proposal['id']}})
        after=call(workspace,'/state');after_items={x['id']:x for x in after['items']}
        before=baseline[workspace]
        checks=[]
        for item in before['items']:
            actual=after_items[item['id']]
            for key in ('id','title','status','itemType'):assert actual[key]==item[key],(workspace,item['id'],key)
            original_payload={k:v for k,v in item['payload'].items() if k!='parentId'}
            actual_payload={k:v for k,v in actual['payload'].items() if k!='parentId'}
            assert actual_payload==original_payload,(workspace,item['id'],'payload changed')
            detail=call(workspace,'/items/'+item['id'])
            assert digest(detail['context'])==before['contextSignatures'][item['id']],(workspace,item['id'],'context changed')
            checks.append(item['id'])
        artifacts={x['id']:x for x in after['artifacts']}
        for original in before['artifacts']:
            assert digest(artifacts[original['id']]['payload'])==original['payloadSha256']
        catalog=call(workspace,'/item-organization/catalog')
        receipts[workspace]={'execution':execution,'proposalId':proposal['id'],'originalItemsVerified':checks,
            'originalArtifactCount':len(before['artifacts']),'afterItemCount':len(after['items']),
            'catalog':catalog}
        (output/f'{workspace}-organization-after.json').write_text(json.dumps(receipts[workspace],ensure_ascii=False,indent=2))
        print(workspace, 'preserved',len(checks),'original items;',len(after['items']),'now; proposal',proposal['id'])
    (output/'organization-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
