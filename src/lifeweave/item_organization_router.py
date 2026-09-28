from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.deps import get_actor_id

from .item_organization import ItemOrganizationService
from .item_organization_models import OrganizationActionInput, OrganizationProposalInput, OrganizationRulesInput
from .repository import ConcurrentUpdateError


router = APIRouter(prefix='/api/lifeweave/{workspace}', tags=['lifeweave'])
Actor = Annotated[str, Depends(get_actor_id)]


def _service(request: Request) -> ItemOrganizationService:
    return ItemOrganizationService(request.app.state.lifeweave_service)


Service = Annotated[ItemOrganizationService, Depends(_service)]


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError): return HTTPException(404, detail=f'对象不存在：{exc.args[0]}')
    if isinstance(exc, ConcurrentUpdateError): return HTTPException(409, detail=str(exc))
    return HTTPException(400, detail=str(exc))


@router.get('/item-organization/catalog')
def catalog(workspace: str, service: Service) -> dict[str, Any]:
    try: return service.catalog(workspace)
    except (KeyError, ValueError) as exc: raise _error(exc) from exc


@router.post('/item-organization/proposals')
def propose(workspace: str, body: OrganizationProposalInput, service: Service, actor_id: Actor) -> dict[str, Any]:
    try: return service.propose(workspace, body, actor_id)
    except (KeyError, ValueError) as exc: raise _error(exc) from exc


@router.get('/item-organization/proposals/{proposal_id}')
def get_proposal(workspace: str, proposal_id: str, service: Service) -> dict[str, Any]:
    try: return service.get_proposal(workspace, proposal_id)
    except (KeyError, ValueError) as exc: raise _error(exc) from exc


@router.post('/item-organization/proposals/{proposal_id}/apply')
def apply(workspace: str, proposal_id: str, body: OrganizationActionInput,
          service: Service, actor_id: Actor) -> dict[str, Any]:
    try: return service.apply(workspace, proposal_id, body.request_id, actor_id)
    except (KeyError, ValueError) as exc: raise _error(exc) from exc


@router.post('/item-organization/proposals/{proposal_id}/undo')
def undo(workspace: str, proposal_id: str, body: OrganizationActionInput,
         service: Service, actor_id: Actor) -> dict[str, Any]:
    try: return service.undo(workspace, proposal_id, body.request_id, actor_id)
    except (KeyError, ValueError) as exc: raise _error(exc) from exc


@router.put('/item-organization/rules')
def save_rules(workspace: str, body: OrganizationRulesInput, service: Service, actor_id: Actor) -> dict[str, Any]:
    try: return service.save_rules(workspace, body, actor_id)
    except (KeyError, ValueError) as exc: raise _error(exc) from exc
