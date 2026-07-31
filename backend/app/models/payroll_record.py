import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base


class PayrollRecord(Base):
    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "payroll_run_id", "employee_id", name="uq_tenant_payroll_run_employee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    standard_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    days_in_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lop_days: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    lop_rev_days: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    
    # Financial metrics
    basic_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    hra: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    medical_allowance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    conveyance_allowance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    special_allowance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    variable_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    other_allowance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    gross_earnings: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    
    pf_deduction: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    income_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    leave_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    other_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_deductions: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    net_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    net_salary_words: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    payslip_blob_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payslip_emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bank_file_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    payroll_run: Mapped["PayrollRun"] = relationship("PayrollRun")
    employee: Mapped["Employee"] = relationship("Employee")