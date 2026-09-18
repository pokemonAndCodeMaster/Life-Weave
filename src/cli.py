from pathlib import Path
import hashlib
from src.config import ConfigManager
from src.database import DatabaseManager

def migrate():
    root = Path(__file__).resolve().parents[1]
    manager = DatabaseManager(ConfigManager(project_root=root))
    try:
        with manager.postgres().transaction() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS public.gongzuo_migrations (name text primary key, digest text not null, applied_at timestamptz not null default now())')
            connection.execute('SELECT pg_advisory_xact_lock(71820918)')
            for file in sorted((root / 'migrations').glob('*.sql')):
                content = file.read_text()
                digest = hashlib.sha256(content.encode()).hexdigest()
                existing = connection.execute('SELECT digest FROM public.gongzuo_migrations WHERE name=%s', (file.name,)).fetchone()
                if existing:
                    if existing['digest'] != digest:
                        raise RuntimeError(f'已应用迁移被修改：{file.name}。请新增迁移。')
                    continue
                connection.execute(content)
                connection.execute('INSERT INTO public.gongzuo_migrations(name,digest) VALUES (%s,%s)', (file.name,digest))
                print('已应用', file.name)
    finally:
        manager.close()

if __name__ == '__main__':
    migrate()
