
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.common.models.base import Base, TimestampMixin
from app.core_hr.models.employee import Employee


class ExitInterview(Base, TimestampMixin):
    __tablename__ = "exit_interviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", name="uq_tenant_employee_exit_interview"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    
    q1_primary_reason_for_leaving: Mapped[str | None] = mapped_column(Text, nullable=True)
    q2_aspects_liked_most_about_company: Mapped[str | None] = mapped_column(Text, nullable=True)
    q3_actions_to_prevent_departure: Mapped[str | None] = mapped_column(Text, nullable=True)
    q4_likelihood_of_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    q5_suggestions_for_workplace_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    employee: Mapped["Employee"] = relationship("Employee")