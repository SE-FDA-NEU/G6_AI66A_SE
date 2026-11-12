from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.services.health import get_health_probe

router = APIRouter(tags=['Operations'])


@router.get('/health')
async def health(probe=Depends(get_health_probe)):
    ready = await probe.ready()
    return JSONResponse(
        {'status': 'ok' if ready else 'unavailable', 'database': 'ready' if ready else 'unavailable'},
        status_code=200 if ready else 503, headers={'Cache-Control': 'no-store'})
