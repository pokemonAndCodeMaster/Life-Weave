from __future__ import annotations

from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from .models import (
    MachineAction,
    MachineOut,
    MachineRegister,
    MachineRegistered,
    RetryRun,
    RunCreate,
    RunEventListOut,
    RunListOut,
    RunOut,
    WorkerClaim,
    WorkerEvent,
    WorkerHeartbeat,
    WorkerReport,
    Workspace,
)
from .service import LifeWeaveRuntimeService
from .storage_text import result_text_storage


router = APIRouter(prefix="/api/lifeweave/{workspace}", tags=["lifeweave-runtime"])


def runtime_service(request: Request) -> LifeWeaveRuntimeService:
    return request.app.state.lifeweave_runtime_service


Service = Annotated[LifeWeaveRuntimeService, Depends(runtime_service)]
def worker_credential(request: Request) -> str | None:
    return request.headers.get('X-LifeWeave-Worker-Token') or request.headers.get('X-Gongzuo-Worker-Token')


def registration_credential(request: Request) -> str | None:
    return request.headers.get('X-LifeWeave-Registration-Token') or request.headers.get('X-Gongzuo-Registration-Token')


WorkerToken = Annotated[str | None, Depends(worker_credential)]
RegistrationToken = Annotated[str | None, Depends(registration_credential)]


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=f"对象不存在：{exc.args[0]}")
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/runs", response_model=RunListOut)
def list_runs(
    workspace: Workspace,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    item_id: Annotated[str | None, Query(alias="itemId")] = None,
    states: Annotated[list[str] | None, Query(alias="state")] = None,
) -> dict:
    rows, total = service.list_runs(
        workspace,
        limit=limit,
        offset=offset,
        item_id=item_id,
        states=tuple(states or ()),
    )
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def create_run(workspace: Workspace, payload: RunCreate, service: Service) -> dict:
    try:
        return service.create_run(workspace, actor_id="admin", **payload.model_dump())
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(workspace: Workspace, run_id: str, service: Service) -> dict:
    try:
        return service.get_run(workspace, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}/artifacts/result", response_class=Response)
def run_result_artifact(workspace: Workspace, run_id: str, service: Service) -> Response:
    try:
        run = service.get_run_snapshot(workspace, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    if run.get("result") is None:
        raise HTTPException(status_code=404, detail="本次运行尚无可读取的结果正文")
    candidates = run.get("artifact_candidates") or []
    result_artifact = next(
        (entry for entry in candidates if entry.get("kind") == "executor-result"),
        {},
    )
    version = str(result_artifact.get("version") or "")
    headers = {"X-Artifact-Version": version}
    if version:
        headers["ETag"] = f'"{version}"'
    return Response(
        content=str(result_text_storage(run)[0]),
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )


@router.get('/runs/{run_id}/source', response_class=Response)
def run_source(workspace: Workspace, run_id: str, path: str, request: Request, service: Service):
    try:
        run = service.get_run_snapshot(workspace, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    run_root = (request.app.state.root / '.runtime/executions').resolve() / workspace / run_id
    root = (run_root / 'repo').resolve()
    relative = Path(path)
    target = (root / relative).resolve()
    # Earlier research runs used this dedicated output folder. It is the only
    # addressable hidden prefix; account/home and other hidden files stay closed.
    def allowed_parts(parts):
        visible = parts[2:] if parts[:2] == ('.runtime','research') else parts
        return not any(part.startswith('.') or part in {'node_modules','__pycache__'} for part in visible)
    if (not root.is_relative_to(run_root) or relative.is_absolute() or
            not allowed_parts(relative.parts) or not target.is_relative_to(root) or
            not allowed_parts(target.relative_to(root).parts)):
        raise HTTPException(400, '只提供本次独立工作目录中的普通源文件')
    if target.suffix.lower() not in {'.md','.txt','.py','.ts','.js','.vue','.css','.html','.json','.yaml','.yml','.toml','.sql','.sh'}:
        raise HTTPException(400, '此类型不支持在浏览器阅读')
    if run.get('state') not in {'succeeded','failed','cancelled','paused'} or not target.is_file():
        raise HTTPException(404, '本机没有此轮运行的源文件，运行可能尚未结束或在另一台机器上')
    if target.stat().st_size > 1_000_000:
        raise HTTPException(413, '文件超过 1 MB，请使用本地编辑器')
    try:
        return Response(target.read_text(), media_type='text/plain; charset=utf-8', headers={'X-Content-Type-Options':'nosniff'})
    except (OSError,UnicodeError) as exc:
        raise HTTPException(400, '文件无法作为文本读取') from exc


@router.get("/runs/{run_id}/events", response_model=RunEventListOut)
def run_events(
    workspace: Workspace,
    run_id: str,
    service: Service,
    after_sequence: Annotated[int, Query(alias="afterSequence", ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> dict:
    try:
        rows = service.events(
            workspace, run_id, after_sequence=after_sequence, limit=limit
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {
        "items": rows,
        "next_sequence": int(rows[-1]["sequence"]) if rows else after_sequence,
    }


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(workspace: Workspace, run_id: str, service: Service) -> dict:
    try:
        return service.request_cancel(workspace, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/pause", response_model=RunOut)
def pause_run(workspace: Workspace, run_id: str, service: Service) -> dict:
    try:
        return service.request_pause(workspace, run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/retry", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def retry_run(workspace: Workspace, run_id: str, payload: RetryRun, service: Service) -> dict:
    try:
        return service.retry_run(
            workspace, run_id, actor_id="admin", **payload.model_dump()
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/machines", response_model=list[MachineOut])
def list_machines(workspace: Workspace, service: Service) -> list[dict]:
    return service.list_machines(workspace)


@router.post("/machines/register", response_model=MachineRegistered, status_code=201)
def register_machine(
    workspace: Workspace,
    payload: MachineRegister,
    service: Service,
    response: Response,
    registration_token: RegistrationToken = None,
) -> dict:
    try:
        response.headers["Cache-Control"] = "no-store"
        return service.register_machine(
            workspace,
            registration_token=registration_token,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/machines/{machine_id}/state", response_model=MachineOut)
def machine_state(
    workspace: Workspace,
    machine_id: str,
    payload: MachineAction,
    service: Service,
) -> dict:
    try:
        return service.machine_action(workspace, machine_id, payload.action)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/worker/{machine_id}/claim")
def worker_claim(
    workspace: Workspace,
    machine_id: str,
    payload: WorkerClaim,
    service: Service,
    worker_token: WorkerToken = None,
) -> dict | None:
    try:
        return service.claim(
            workspace, machine_id, worker_token, lease_seconds=payload.lease_seconds
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/worker/{machine_id}/heartbeat")
def worker_heartbeat(
    workspace: Workspace,
    machine_id: str,
    payload: WorkerHeartbeat,
    service: Service,
    worker_token: WorkerToken = None,
) -> dict:
    try:
        return service.heartbeat(
            workspace,
            machine_id,
            worker_token,
            leases=[lease.model_dump() for lease in payload.leases],
            lease_seconds=payload.lease_seconds,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/worker/{machine_id}/runs/{run_id}/events")
def worker_event(
    workspace: Workspace,
    machine_id: str,
    run_id: str,
    payload: WorkerEvent,
    service: Service,
    worker_token: WorkerToken = None,
) -> dict:
    try:
        return service.worker_event(
            workspace,
            machine_id,
            worker_token,
            run_id,
            **payload.model_dump(),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/worker/{machine_id}/runs/{run_id}/report", response_model=RunOut)
def worker_report(
    workspace: Workspace,
    machine_id: str,
    run_id: str,
    payload: WorkerReport,
    service: Service,
    worker_token: WorkerToken = None,
) -> dict:
    try:
        return service.worker_report(
            workspace,
            machine_id,
            worker_token,
            run_id,
            payload.model_dump(),
        )
    except Exception as exc:
        raise _http_error(exc) from exc
