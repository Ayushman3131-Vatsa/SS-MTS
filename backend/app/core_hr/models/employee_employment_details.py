
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.common.models.base import Base

if TYPE_CHECKING:
    from app.core_hr.models.employee import Employee


class EmployeeEmploymentDetails(Base):
    """Versioned employment details — each change inserts a new row.
    The current record is where is_current = True, strictly scoped per tenant.
    """

    __tablename__ = "employee_employment_details"
    __table_args__ = (
        Index("ix_tenant_emp_employment_details_employee_id", "tenant_id", "employee_id"),
        Index("ix_tenant_emp_employment_details_is_current", "tenant_id", "employee_id", "is_current"),
        Index(
            "uq_tenant_emp_employment_details_current",
            "tenant_id",
            "employee_id",
            unique=True,
            postgresql_where="is_current = true",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Snapshot strings preserve title/department wording at the time of change
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporting_manager: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    designation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("designations.id", ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    work_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_locations.id", ondelete="SET NULL"), nullable=True)
    
    contract_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Statutory Identifiers
    uan_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pf_account_no: Mapped[str | None] = mapped_column(String(50), nullable=True)

    probation_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    employee: Mapped["Employee"] = relationship("Employee")