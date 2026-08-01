import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.common.models.base import Base


class PayCalendar(Base):
    __tablename__ = "pay_calendar"
    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", name="uq_tenant_pay_calendar_year_month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Scoped strictly to the tenant organization
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Payroll processing lifecycle timestamps
    payroll_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payroll_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payslips_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bank_file_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PayCalendar tenant={self.tenant_id} period={self.month}/{self.year}>"