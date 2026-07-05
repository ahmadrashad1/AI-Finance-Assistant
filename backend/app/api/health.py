from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.session import check_database_connection

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def get_health(db_ok: bool = Depends(check_database_connection)) -> HealthResponse:
    database_status = "ok" if db_ok else "unavailable"
    overall_status = "healthy" if db_ok else "degraded"
    return HealthResponse(status=overall_status, app="ok", database=database_status)
