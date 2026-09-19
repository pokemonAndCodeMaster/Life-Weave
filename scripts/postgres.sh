#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_BIN="${LIFEWEAVE_PG_BIN:-${GONGZUO_PG_BIN:-/usr/lib/postgresql/16/bin}}"
PG_RUNTIME="$ROOT/.runtime/postgres"
PG_DATA="$PG_RUNTIME/data"
PG_SOCKET="$PG_RUNTIME/socket"
PG_PORT="${LIFEWEAVE_DB_PORT:-${GONGZUO_DB_PORT:-55440}}"
PG_USER="${LIFEWEAVE_DB_USER:-${GONGZUO_DB_USER:-lifeweave}}"
PG_DATABASE="${LIFEWEAVE_DB_NAME:-${GONGZUO_DB_NAME:-lifeweave}}"
[[ "$PG_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ && "$PG_DATABASE" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || exit 2
mkdir -p "$PG_SOCKET"
chmod 700 "$PG_RUNTIME" "$PG_SOCKET"
ready() { "$PG_BIN/pg_isready" -h "$PG_SOCKET" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" >/dev/null 2>&1; }
case "${1:-status}" in
  init|start)
    if [[ ! -f "$PG_DATA/PG_VERSION" ]]; then
      "$PG_BIN/initdb" -D "$PG_DATA" -U "$PG_USER" --encoding=UTF8 --locale=C.UTF-8 --auth-local=trust --auth-host=reject >/dev/null
    fi
    if ! ready; then
      "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$PG_RUNTIME/server.log" -o "-c listen_addresses='' -c unix_socket_directories='$PG_SOCKET' -p $PG_PORT" -w start
    fi
    if ! "$PG_BIN/psql" -h "$PG_SOCKET" -p "$PG_PORT" -U "$PG_USER" -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname='$PG_DATABASE'" | rg -q 1; then
      "$PG_BIN/createdb" -h "$PG_SOCKET" -p "$PG_PORT" -U "$PG_USER" "$PG_DATABASE"
    fi
    ;;
  stop) "$PG_BIN/pg_ctl" -D "$PG_DATA" -m fast -w stop ;;
  status) ready ;;
  backup)
    mkdir -p "$ROOT/.runtime/backups"
    DEST="$ROOT/.runtime/backups/lifeweave-$(date +%Y%m%d-%H%M%S).dump"
    "$PG_BIN/pg_dump" -h "$PG_SOCKET" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DATABASE" -Fc -f "$DEST"
    chmod 600 "$DEST"
    echo "$DEST"
    ;;
  *) echo '用法: postgres.sh init|start|stop|status|backup' >&2; exit 2 ;;
esac
