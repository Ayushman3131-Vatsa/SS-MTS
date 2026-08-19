"""Combined API surface for the Tenant Management module — tenant
onboarding plus the platform admin dashboard. main.py mounts this single
router instead of reaching into tenants/ and dashboard/ individually."""

from fastapi import APIRouter

from app.tenant_management.dashboard.router import router as dashboard_router
from app.tenant_management.tenants.router import router as tenants_router

router = APIRouter()
router.include_router(tenants_router)
router.include_router(dashboard_router)
