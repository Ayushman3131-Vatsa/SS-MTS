
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.employee import Employee


class EmployeeCompensation(Base):
    __tablename__ = "employee_compensation"
    __table_args__ = (
        Index(
            "uq_tenant_emp_compensation_current",
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
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    salary_structure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_structures.id", ondelete="SET NULL"), nullable=True
    )
    
    annual_fixed_ctc: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    annual_variable_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    annual_variable_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    annual_total_ctc: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    
    basic_monthly: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    hra_monthly: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    medical_allowance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1250, nullable=False)
    conveyance_allowance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1600, nullable=False)
    special_allowance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    should_send_letter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee: Mapped["Employee"] = relationship("Employee")