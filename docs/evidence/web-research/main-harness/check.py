import httpx,json
c=httpx.Client(base_url='http://127.0.0.1:8011/api/lifeweave/personal')
d=c.get('/conversations/conversation-ec9e93d6ed939b134a7a26d468448760').json()
for t in d['turns']:
 print(json.dumps({k:t[k] for k in ['id','status','itemId','runId','error']},ensure_ascii=False))
 if t['runId']:
  r=c.get('/runs/'+t['runId']).json();print(r['state'],len(r.get('result') or ''))
