import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_offering
from app.db.session import get_db
from app.modules.projects import service
from app.schemas.project import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    principal: Principal = Depends(require_offering("TASK_MANAGEMENT")),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await service.create_project(db, principal, payload)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    principal: Principal = Depends(require_offering("TASK_MANAGEMENT")),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    return [ProjectResponse.model_validate(p) for p in await service.list_projects(db, principal)]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_offering("TASK_MANAGEMENT")),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await service.get_project_for_principal(db, principal, project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    principal: Principal = Depends(require_offering("TASK_MANAGEMENT")),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await service.update_project(db, principal, project_id, payload)
    return ProjectResponse.model_validate(project)
