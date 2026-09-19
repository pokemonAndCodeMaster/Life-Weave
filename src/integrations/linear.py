from __future__ import annotations
import hashlib,json,os,stat
from pathlib import Path
from uuid import uuid4
import httpx
from psycopg.types.json import Jsonb

ISSUE_FIELDS='id identifier title description url updatedAt priority dueDate state { id name type } team { id name key } assignee { name }'
class LinearConnection:
 def __init__(self,root:Path):self.file=root/'.runtime/linear.json'
 def configured(self):return self.file.exists() or bool(os.environ.get('LINEAR_API_KEY') or os.environ.get('LINEAR_API_KEY_FILE'))
 def save(self,token:str='',credential_file:str=''):
  if not token.strip() and not credential_file.strip():raise ValueError('请输入 API Key 或凭证文件路径')
  if credential_file:
   path=Path(credential_file).expanduser()
   if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('凭证文件须为仅当前用户可读的普通文件（权限 600）')
  candidate=token.strip() or Path(credential_file).expanduser().read_text().strip()
  viewer=self.query('{ viewer { id name } organization { name } }',authorization=candidate)
  self.file.parent.mkdir(parents=True,exist_ok=True)
  fd=os.open(self.file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  with os.fdopen(fd,'w') as handle:json.dump({'token':token.strip(),'credentialFile':credential_file.strip()},handle)
  os.chmod(self.file,0o600)
  return viewer
 def token(self):
  config=json.loads(self.file.read_text()) if self.file.exists() else {}
  token=os.environ.get('LINEAR_API_KEY') or config.get('token')
  file=os.environ.get('LINEAR_API_KEY_FILE') or config.get('credentialFile')
  if not token and file:
   path=Path(file).expanduser()
   if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('Linear 凭证文件不可用或权限过宽')
   token=path.read_text().strip()
  if not token:raise ValueError('尚未连接 Linear，请在设置中配置')
  return token
 def query(self,query,variables=None,authorization=None):
  try:
   with httpx.Client(timeout=25) as client:response=client.post('https://api.linear.app/graphql',headers={'Authorization':authorization or self.token()},json={'query':query,'variables':variables or {}})
   if response.status_code==401:raise ValueError('Linear 凭证无效，请重新连接')
   if response.status_code==429:raise ValueError('Linear 请求暂时过多，请稍后重试')
   if response.status_code>=400:raise ValueError(f'Linear 暂不可用（HTTP {response.status_code}）')
   data=response.json()
   if data.get('errors'):raise ValueError('Linear 拒绝了请求：'+'; '.join(e.get('message','未知错误') for e in data['errors']))
   return data['data']
  except httpx.HTTPError as exc:raise ValueError('无法连接 Linear，请检查网络后重试') from exc
 def viewer(self):return self.query('{ viewer { id name } organization { name } }')
 def issues(self,after=None):return self.query('query($after:String){ viewer { assignedIssues(first:50,after:$after){ nodes { '+ISSUE_FIELDS+' } pageInfo { hasNextPage endCursor } } } }',{'after':after})['viewer']['assignedIssues']
 def issue(self,identity):return self.query('query($id:String!){ issue(id:$id){ '+ISSUE_FIELDS+' } }',{'id':identity})['issue']

class LinearService:
 def __init__(self,db,connection,work):self.db=db;self.connection=connection;self.work=work
 def bindings(self,workspace):return self.db.fetch_all('SELECT * FROM workbench.linear_binding WHERE workspace=%s ORDER BY synced_at DESC',(workspace,))
 def import_issue(self,workspace,identity):
  remote=self.connection.issue(identity)
  if not remote:raise ValueError('Linear 事项不存在')
  item_id='linear-'+hashlib.sha256((workspace+remote['id']).encode()).hexdigest()[:20]
  context_id='ctx-'+item_id;version_id='v1-'+item_id
  with self.db.transaction() as conn:
   conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(workspace+remote['id'],))
   binding=conn.execute('SELECT * FROM workbench.linear_binding WHERE workspace=%s AND issue_id=%s',(workspace,remote['id'])).fetchone()
   if binding:
    conn.execute('UPDATE workbench.linear_binding SET remote_snapshot=%s,synced_at=now() WHERE workspace=%s AND issue_id=%s',(Jsonb(remote),workspace,remote['id']))
    return {'itemId':binding['item_id'],'created':False,'remote':remote}
   payload={'goal':remote['description'] or remote['title'],'scope':'从 Linear 引入，在经纬中推进；本地状态与原事项分别维护。','owner':'我','due':remote.get('dueDate'),'priority':remote['priority'],'linearUrl':remote['url'],'linearIdentifier':remote['identifier']}
   conn.execute("INSERT INTO workbench.t_lifeweave_item(id,workspace_key,item_type,title,payload,created_by,updated_by) VALUES(%s,%s,'other',%s,%s,'local-user','local-user')",(item_id,workspace,remote['title'],Jsonb(payload)))
   conn.execute('INSERT INTO workbench.t_lifeweave_context(id,workspace_key,item_id) VALUES(%s,%s,%s)',(context_id,workspace,item_id))
   conn.execute("INSERT INTO workbench.t_lifeweave_context_version(id,context_id,revision_no,status,content,provenance,accepted_by,accepted_at,created_by) VALUES(%s,%s,1,'accepted',%s,%s,'local-user',now(),'local-user')",(version_id,context_id,Jsonb({'goal':payload['goal'],'scope':payload['scope']}),Jsonb([{'source':remote['url'],'updatedAt':remote['updatedAt']}])) )
   conn.execute('UPDATE workbench.t_lifeweave_context SET current_version_id=%s WHERE id=%s',(version_id,context_id))
   conn.execute('INSERT INTO workbench.linear_binding(workspace,issue_id,item_id,remote_snapshot) VALUES(%s,%s,%s,%s)',(workspace,remote['id'],item_id,Jsonb(remote)))
  return {'itemId':item_id,'created':True,'remote':remote}
 def prepare(self,workspace,item_id,body):
  binding=self.db.fetch_one('SELECT * FROM workbench.linear_binding WHERE workspace=%s AND item_id=%s',(workspace,item_id))
  if not binding:raise ValueError('此事项尚未关联 Linear')
  self.work.get_item(workspace,item_id)
  identity=str(uuid4())
  return self.db.fetch_one("INSERT INTO workbench.linear_publication(id,workspace,item_id,issue_id,body,status) VALUES(%s,%s,%s,%s,%s,'prepared') RETURNING *",(identity,workspace,item_id,binding['issue_id'],body))
 def publish(self,workspace,publication_id):
  # Client supplied comment ID makes a timeout retry address the same remote object.
  with self.db.transaction() as conn:
   row=conn.execute('SELECT * FROM workbench.linear_publication WHERE workspace=%s AND id=%s FOR UPDATE',(workspace,publication_id)).fetchone()
   if not row:raise ValueError('发布预览不存在')
   if row['status']=='confirmed':return row
   if row['status'] in ('sending','uncertain'):
    data=self.connection.query('query($id:String!){ comment(id:$id){ id body } }',{'id':row['id']}).get('comment')
    if data and data['body']==row['body']:
     return conn.execute("UPDATE workbench.linear_publication SET status='confirmed',remote_comment_id=id,confirmed_at=now() WHERE id=%s RETURNING *",(row['id'],)).fetchone()
    raise ValueError('上次发送结果尚未确认，请先核对 Linear 原事项，不会重复创建评论')
   conn.execute("UPDATE workbench.linear_publication SET status='sending' WHERE id=%s",(row['id'],))
  try:
   result=self.connection.query('mutation($input:CommentCreateInput!){ commentCreate(input:$input){ success comment { id body } } }',{'input':{'id':row['id'],'issueId':row['issue_id'],'body':row['body']}})['commentCreate']
   if not result['success']:raise ValueError('Linear 未接受发布')
   readback=self.connection.query('query($id:String!){ comment(id:$id){ id body } }',{'id':row['id']})['comment']
   if readback['body']!=row['body']:raise ValueError('写入后正文回读不一致，请核对原事项')
  except Exception:
   self.db.execute("UPDATE workbench.linear_publication SET status='uncertain' WHERE id=%s",(row['id'],));raise
  return self.db.fetch_one("UPDATE workbench.linear_publication SET status='confirmed',remote_comment_id=%s,confirmed_at=now() WHERE id=%s RETURNING *",(readback['id'],row['id']))
