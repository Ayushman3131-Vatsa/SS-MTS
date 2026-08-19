import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.common.models.base import Base
from app.core_hr.models.candidate import Candidate


class CandidateCompensation(Base):
    __tablename__ = "candidate_compensation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", name="uq_tenant_candidate_compensation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
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
    
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    candidate: Mapped["Candidate"] = relationship("Candidate")