"""Owned, versioned reading routes for documents, code and research outputs."""
from fastapi import APIRouter, HTTPException, Request, Response
from urllib.parse import quote

from .models import WorkspaceKey
from .output_files import IMAGE_TYPES

router = APIRouter(prefix='/api/lifeweave/{workspace}/items/{item_id}/outputs', tags=['output-files'])


def call(request, method, *args):
    try:
        return getattr(request.app.state.output_files, method)(*args)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(404, '指定产物或固定文件不存在') from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/catalog')
def catalog(request: Request, workspace: WorkspaceKey, item_id: str, outputId: str,
            version: str | None = None):
    return call(request, 'catalog', workspace, item_id, outputId, version)


@router.get('/file')
def file(request: Request, workspace: WorkspaceKey, item_id: str, outputId: str, path: str,
         version: str | None = None):
    return call(request, 'file', workspace, item_id, outputId, path, version)


@router.get('/document')
def document(request: Request, workspace: WorkspaceKey, item_id: str, outputId: str, path: str,
             version: str | None = None):
    return call(request, 'document', workspace, item_id, outputId, path, version)


@router.get('/asset')
def asset(request: Request, workspace: WorkspaceKey, item_id: str, outputId: str, path: str,
          version: str | None = None):
    data, content_type = call(request, 'bytes', workspace, item_id, outputId, path, version)
    if content_type not in IMAGE_TYPES:
        raise HTTPException(415, '该文件不支持作为图片内嵌，请下载查看')
    return Response(data, media_type=content_type, headers={'X-Content-Type-Options': 'nosniff',
                    'Content-Security-Policy': "default-src 'none'; sandbox"})


@router.get('/download')
def download(request: Request, workspace: WorkspaceKey, item_id: str, outputId: str, path: str,
             version: str | None = None):
    data, content_type = call(request, 'bytes', workspace, item_id, outputId, path, version)
    return Response(data, media_type=content_type, headers={'X-Content-Type-Options': 'nosniff',
                    'Content-Disposition': "attachment; filename*=UTF-8''" + quote(path.rsplit('/', 1)[-1], safe='')})


@router.get('/bundle')
def bundle(request: Request, workspace: WorkspaceKey, item_id: str, outputId: str,
           version: str | None = None):
    data = call(request, 'bundle', workspace, item_id, outputId, version)
    return Response(data, media_type='application/zip', headers={'X-Content-Type-Options': 'nosniff',
                    'Content-Disposition': 'attachment; filename="lifeweave-output.zip"'})
