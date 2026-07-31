
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_code", name="uq_tenant_employee_code"),
        UniqueConstraint("tenant_id", "email", name="uq_tenant_employee_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Scoped strictly to the tenant organization
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Optional link if converted from a recruitment candidate
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True
    )
    
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Organization mapping foreign keys
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("designations.id", ondelete="SET NULL"), nullable=True
    )
    
    # Work Location Mapping (Foreign Key to a WorkLocations master table or string fallback)
    work_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_locations.id", ondelete="SET NULL"), nullable=True
    )
    work_location: Mapped[str | None] = mapped_column(String(255), nullable=True) # e.g., "Headquarters - Delhi", "Remote"
    
    # Client Deployment fields (Common in IT/Consulting service firms)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Employment metadata
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True) # Full-time, Contract, Intern
    contract_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    
    regime_type: Mapped[str | None] = mapped_column(String(50), nullable=True) # Tax regime (e.g., Old/New)
    date_of_joining: Mapped[date | None] = mapped_column(Date, nullable=True)
    probation_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_working_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False) # active, suspended, terminated
    
    # Statutory & compliance fields
    uan_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pf_account_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    police_verification_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    
    # System Access & Profile Blob Path (for secure S3 storage of profile pictures/documents)
    ess_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile_image_blob_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Employee {self.employee_code} (status={self.status})>"