#!/usr/bin/env python3
"""Local lifecycle; every process and backup belongs to this installation."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[1]; RUNTIME=ROOT/'.runtime'; PYTHON=ROOT/'.venv/bin/python'
def command(args,cwd=ROOT): subprocess.run([str(x) for x in args],cwd=cwd,check=True)
def owned_process(pid):
 try:
  process=Path(f'/proc/{pid}')
  if process.joinpath('stat').read_text().split()[2]=='Z':return False
  commandline=process.joinpath('cmdline').read_bytes().replace(b'\x00',b' ')
  return b'uvicorn' in commandline and b'src.api.app:create_app' in commandline and process.joinpath('cwd').resolve()==ROOT
 except (FileNotFoundError,ProcessLookupError):return False

def main():
 parser=argparse.ArgumentParser(description='共作：安装、启动、停止与备份');parser.add_argument('action',choices=['setup','start','stop','status','backup']);args=parser.parse_args();RUNTIME.mkdir(exist_ok=True);RUNTIME.chmod(0o700);pidfile=RUNTIME/'server.pid'
 if args.action=='setup':
  if not PYTHON.exists():command([sys.executable,'-m','venv',ROOT/'.venv'])
  command([PYTHON,'-m','pip','install','-e','.[dev]']);command(['npm','ci','--no-audit','--no-fund'],ROOT/'web');command(['npm','run','build'],ROOT/'web');command(['bash','scripts/postgres.sh','init']);command([PYTHON,'-m','src.cli']);print('安装完成。启动：python scripts/workbench.py start')
 elif args.action=='start':
  if pidfile.exists():
   if owned_process(int(pidfile.read_text())):print('工作台已启动：http://127.0.0.1:8010');return
   pidfile.unlink()
  command(['bash','scripts/postgres.sh','start']);command([PYTHON,'-m','src.cli'])
  with (RUNTIME/'server.log').open('ab') as log:process=subprocess.Popen([str(PYTHON),'-m','uvicorn','src.api.app:create_app','--factory','--host','127.0.0.1','--port','8010'],cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
  pidfile.write_text(str(process.pid))
  for _ in range(50):
   if process.poll() is not None:pidfile.unlink(missing_ok=True);raise SystemExit('启动失败，请查看 .runtime/server.log')
   try:
    with urllib.request.urlopen('http://127.0.0.1:8010/api/health',timeout=1) as response:
     if response.status==200:print('打开工作台：http://127.0.0.1:8010');return
   except OSError:time.sleep(.2)
  raise SystemExit('服务尚未就绪，请查看 .runtime/server.log')
 elif args.action=='stop':
  if pidfile.exists():
   pid=int(pidfile.read_text())
   if owned_process(pid):
    os.kill(pid,signal.SIGTERM)
    for _ in range(100):
     if not owned_process(pid):break
     time.sleep(.1)
    else:raise SystemExit('执行仍在退出，请稍后再次检查，未强制终止任务。')
   pidfile.unlink()
  print('已请求停止工作台；数据库保留。')
 elif args.action=='status':
  try:
   with urllib.request.urlopen('http://127.0.0.1:8010/api/health',timeout=2) as response:print(json.dumps(json.load(response),ensure_ascii=False))
  except OSError:raise SystemExit('工作台未启动')
 elif args.action=='backup':
  if pidfile.exists() and owned_process(int(pidfile.read_text())):raise SystemExit('请先运行 stop，确保数据库与知识文件在同一静止状态，再备份；完成后可 start。')
  import tarfile
  command(['bash','scripts/postgres.sh','backup']);target=RUNTIME/'backups'/f'knowledge-{time.strftime("%Y%m%d-%H%M%S")}.tar.gz'
  with tarfile.open(target,'w:gz') as archive:
   if (RUNTIME/'knowledge').exists():archive.add(RUNTIME/'knowledge',arcname='knowledge')
  target.chmod(0o600);print(target)
if __name__=='__main__':main()
