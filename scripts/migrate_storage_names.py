#!/usr/bin/env python3
"""Rename this installation's original default DB/role without copying data.

Stop the app and run workbench.py backup first. Custom database names are not
rewritten. This intentionally only connects to this project's private cluster.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='apply after stopping and backing up the local installation')
    args = parser.parse_args()
    address = dict(host=str(ROOT / '.runtime/postgres/socket'), port=55440, dbname='postgres', autocommit=True, connect_timeout=3)
    connection = None
    for role in ('lifeweave', 'gongzuo'):
        try:
            connection = psycopg.connect(**address, user=role)
            break
        except psycopg.OperationalError:
            pass
    if connection is None:
        raise SystemExit('未找到本项目默认数据库角色；自定义安装请保留其配置。')
    with connection as c:
        if Path(c.execute('SHOW data_directory').fetchone()[0]).resolve() != ROOT / '.runtime/postgres/data':
            raise SystemExit('拒绝操作非本项目集群')
        roles = {row[0] for row in c.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('gongzuo','lifeweave')")}
        databases = {row[0] for row in c.execute("SELECT datname FROM pg_database WHERE datname IN ('gongzuo','lifeweave')")}
        if len(roles) > 1 or len(databases) > 1:
            raise SystemExit('新旧身份同时存在，停止自动迁移，需先核对来源。')
        if not databases:
            raise SystemExit('没有找到默认数据库')
        print(json.dumps({'roles': sorted(roles), 'databases': sorted(databases), 'target': 'lifeweave', 'apply': args.apply}))
        if not args.apply or (roles == databases == {'lifeweave'}):
            return
        active = c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname IN ('gongzuo','lifeweave')").fetchone()[0]
        if active:
            raise SystemExit('仍有业务数据库连接，请先停止应用和相关客户端。')
        temporary = 'lw_rename_' + uuid4().hex[:12]
        c.execute(sql.SQL('CREATE ROLE {} LOGIN SUPERUSER').format(sql.Identifier(temporary)))
    # PostgreSQL cannot rename the current session user. A temporary local admin
    # performs the rename; role OID, ownership and memberships are preserved.
    try:
        with psycopg.connect(**address, user=temporary) as admin:
            if 'gongzuo' in databases:
                admin.execute('ALTER DATABASE gongzuo RENAME TO lifeweave')
            if 'gongzuo' in roles:
                admin.execute('ALTER ROLE gongzuo RENAME TO lifeweave')
    finally:
        for role in ('lifeweave', 'gongzuo'):
            try:
                cleanup = psycopg.connect(**address, user=role)
            except psycopg.OperationalError:
                continue
            with cleanup:
                cleanup.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(temporary)))
            break
    print('数据库与角色已原位改名；请应用 SQL 迁移，再启动工作台。')


if __name__ == '__main__':
    main()
