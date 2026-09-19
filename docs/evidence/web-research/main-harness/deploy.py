import hashlib,json
from pathlib import Path
import psycopg
from psycopg import sql
from src.cli import migrate
R=Path.cwd()
def capture():
 with psycopg.connect(host=str(R/'.runtime/postgres/socket'),port=55440,user='lifeweave',dbname='lifeweave') as c:
  result={}
  for (name,) in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='workbench' ORDER BY tablename"):
   rows=c.execute(sql.SQL('SELECT to_jsonb(t)::text FROM workbench.{} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(name))).fetchall()
   result[name]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()}
 return result
before=capture();kb={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'.runtime/knowledge').rglob('*.md')}
migrate();after=capture();changes={k:{'before':v,'after':after.get(k)} for k,v in before.items() if v!=after.get(k)}
assert set(changes)<= {'schema_migration'},changes
assert kb=={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'.runtime/knowledge').rglob('*.md')}
e={'base':'bb161dd','candidate':'71f00f8','backup':'lifeweave-20260919-172157.dump','before':before,'after':after,'existingChanged':changes,'newTables':list(set(after)-set(before)),'knowledgeHashes':kb}
(R/'docs/evidence/web-research/upgrade-preservation.json').write_text(json.dumps(e,ensure_ascii=False,indent=2))
print('Preserved',len(before)-len(changes),'existing tables and',len(kb),'knowledge files; added',e['newTables'])
