import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, get_current_principal
from app.db.session import get_db
from app.modules.task_management.domain.enums import ProjectStatus
from app.modules.task_management.memberships import service as membership_service
from app.modules.task_management.memberships.schemas import (
    ProjectMemberCreateRequest,
    ProjectMemberResponse,
    ProjectMemberUpdateRequest,
)
from app.modules.task_management.projects import service
from app.modules.task_management.projects.schemas import (
    ProjectArchiveRequest,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.modules.task_management.schemas import PageResponse


router = APIRouter(prefix="/projects", tags=["task-management-projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return ProjectResponse.model_validate(await service.create_project(db, principal, payload))


@router.get("", response_model=PageResponse[ProjectResponse])
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    query: str | None = Query(default=None, max_length=255),
    project_status: ProjectStatus | None = Query(default=None, alias="status"),
    member_id: uuid.UUID | None = None,
    include_archived: bool = False,
    sort: str = Query(default="-updated_at", pattern=r"^-?(name|project_key|created_at|updated_at|status)$"),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[ProjectResponse]:
    return await service.list_projects(
        db,
        principal,
        page=page,
        page_size=page_size,
        query=query,
        status=project_status.value if project_status else None,
        member_id=member_id,
        include_archived=include_archived,
        sort=sort,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await service.get_project_for_principal(db, principal, project_id)
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await service.update_project(db, principal, project_id, payload)
    )


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: uuid.UUID,
    payload: ProjectArchiveRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await service.set_project_archived(
            db, principal, project_id, version=payload.version, archived=True
        )
    )


@router.post("/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(
    project_id: uuid.UUID,
    payload: ProjectArchiveRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await service.set_project_archived(
            db, principal, project_id, version=payload.version, archived=False
        )
    )


@router.get(
    "/{project_id}/members", response_model=PageResponse[ProjectMemberResponse]
)
async def list_project_members(
    project_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[ProjectMemberResponse]:
    return await membership_service.list_members(
        db, principal, project_id, page=page, page_size=page_size
    )


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: uuid.UUID,
    payload: ProjectMemberCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemberResponse:
    return ProjectMemberResponse.model_validate(
        await membership_service.add_member(db, principal, project_id, payload)
    )


@router.patch("/{project_id}/members/{membership_id}", response_model=ProjectMemberResponse)
async def update_project_member(
    project_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: ProjectMemberUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemberResponse:
    return ProjectMemberResponse.model_validate(
        await membership_service.update_member(
            db, principal, project_id, membership_id, payload
        )
    )


@router.delete(
    "/{project_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_project_member(
    project_id: uuid.UUID,
    membership_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    await membership_service.remove_member(db, principal, project_id, membership_id)
