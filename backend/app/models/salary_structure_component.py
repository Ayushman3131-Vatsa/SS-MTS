import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

CALC_TYPES = (
    "PERCENT_OF_CTC",
    "PERCENT_OF_TCC",
    "PERCENT_OF_BASIC",
    "FLAT_MONTHLY",
    "FLAT_ANNUAL",
    "REMAINDER_OF_TCC",
)
CATEGORIES = ("EARNING", "DEDUCTION", "EMPLOYER_CONTRIBUTION")


class SalaryStructureComponent(Base):
    __tablename__ = "salary_structure_components"
    __table_args__ = (
        UniqueConstraint("tenant_id", "structure_id", "code", name="uq_tenant_structure_component_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    structure_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(Enum(*CATEGORIES, name="salary_component_category"), nullable=False)
    calc_type: Mapped[str] = mapped_column(Enum(*CALC_TYPES, name="salary_component_calc_type"), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    appears_on_payslip: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    structure: Mapped["SalaryStructure"] = relationship("SalaryStructure")