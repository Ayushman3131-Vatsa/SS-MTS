import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base


class EmployeeYtdBalance(Base):
    __tablename__ = "employee_ytd_balances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", "employee_id", name="uq_tenant_ytd_year_month_employee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    basic_ytd: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    hra_ytd: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    gross_earnings_ytd: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    net_pay_ytd: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)