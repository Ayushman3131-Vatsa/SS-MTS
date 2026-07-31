
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.employee import Employee


class EmployeePersonalDetails(Base):
    __tablename__ = "employee_personal_details"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "effective_from", name="uq_tenant_employee_personal_version"),
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
    
    title: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    father_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    spouse_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    maiden_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    number_of_children: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    personal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    permanent_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    permanent_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    permanent_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    permanent_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    permanent_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    current_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    aadhar_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uan_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pf_account_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    employee: Mapped["Employee"] = relationship("Employee")