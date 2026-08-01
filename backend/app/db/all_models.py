from app.common.models.audit_log import AuditLog
from app.core_hr.models.candidate import Candidate
from app.core_hr.models.candidate_compensation import CandidateCompensation
from app.core_hr.models.candidate_education import CandidateEducation
from app.core_hr.models.candidate_emergency_contacts import CandidateEmergencyContact
from app.core_hr.models.candidate_employment_history import CandidateEmploymentHistory
from app.core_hr.models.candidate_personal_details import CandidatePersonalDetails
from app.core_hr.models.candidate_status_log import CandidateStatusLog
from app.core_hr.models.candidate_uploaded_document import CandidateUploadedDocument
from app.task_management.models.daily_progress_log import DailyProgressLog
from app.core_hr.models.departments import Department
from app.core_hr.models.designation import Designation
from app.core_hr.models.document import Document
from app.core_hr.models.email_log import EmailLog
from app.core_hr.models.employee import Employee
from app.core_hr.models.employee_bank_details import EmployeeBankDetails
from app.core_hr.models.employee_compensation import EmployeeCompensation
from app.core_hr.models.employee_compensation_component import EmployeeCompensationComponent
from app.core_hr.models.employee_dependents import EmployeeDependent
from app.core_hr.models.employee_education import EmployeeEducation
from app.core_hr.models.employee_emergency_contacts import EmployeeEmergencyContact
from app.core_hr.models.employee_employment_details import EmployeeEmploymentDetails
from app.core_hr.models.employee_employment_history import EmployeeEmploymentHistory
from app.core_hr.models.employee_personal_details import EmployeePersonalDetails
from app.core_hr.models.employee_status_log import EmployeeStatusLog
from app.core_hr.models.employee_uploaded_document import EmployeeUploadedDocument
from app.core_hr.models.employee_ytd_balance import EmployeeYtdBalance
from app.tenant_management.models.enums import (
    DatabaseIsolationMode,
    DatabaseProvisioningState,
    PlatformActivityType,
    PlatformActorType,
    SubscriptionPlanCode,
    SubscriptionPlanStatus,
    TenantStatus,
    TenantSubscriptionStatus,
)
from app.core_hr.models.exit_interview import ExitInterview
from app.tenant_management.models.offering import Offering
from app.auth.models.page import Page
from app.auth.models.password_reset_token import PasswordResetToken
from app.core_hr.models.pay_calendar import PayCalendar
from app.core_hr.models.payroll_record import PayrollRecord
from app.core_hr.models.payroll_record_component import PayrollRecordComponent
from app.core_hr.models.payroll_run import PayrollRun
from app.tenant_management.models.platform_activity_event import PlatformActivityEvent
from app.auth.models.platform_admin import PlatformAdmin
from app.task_management.models.project import Project
from app.auth.models.role import Role
from app.auth.models.role_page_access import RolePageAccess
from app.core_hr.models.salary_structure import SalaryStructure
from app.core_hr.models.salary_structure_component import SalaryStructureComponent
from app.tenant_management.models.subscription_plan import SubscriptionPlan
from app.auth.models.system_roles import ROLE_CODE_BY_NAME, ROLE_NAME_BY_CODE, SYSTEM_ROLES
from app.task_management.models.task import Task
from app.task_management.models.task_comment import TaskComment
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.models.tenant_database_allocation import TenantDatabaseAllocation
from app.tenant_management.models.tenant_module import TenantModule
from app.tenant_management.models.tenant_offering import TenantOffering
from app.tenant_management.models.tenant_subscription import TenantSubscription
from app.auth.models.user_account import UserAccount
from app.auth.models.user_role import UserRole
from app.auth.models.user_session import UserSession
from app.core_hr.models.work_location import WorkLocation

# Backwards-compatible aliases while modules finish migrating off the old names.
User = UserAccount
BrowserSession = UserSession

__all__ = [
    "AuditLog",
    "BrowserSession",
    "Candidate",
    "CandidateCompensation",
    "CandidateEducation",
    "CandidateEmergencyContact",
    "CandidateEmploymentHistory",
    "CandidatePersonalDetails",
    "CandidateStatusLog",
    "CandidateUploadedDocument",
    "DailyProgressLog",
    "DatabaseIsolationMode",
    "DatabaseProvisioningState",
    "Department",
    "Designation",
    "Document",
    "EmailLog",
    "Employee",
    "EmployeeBankDetails",
    "EmployeeCompensation",
    "EmployeeCompensationComponent",
    "EmployeeDependent",
    "EmployeeEducation",
    "EmployeeEmergencyContact",
    "EmployeeEmploymentDetails",
    "EmployeeEmploymentHistory",
    "EmployeePersonalDetails",
    "EmployeeStatusLog",
    "EmployeeUploadedDocument",
    "EmployeeYtdBalance",
    "ExitInterview",
    "Offering",
    "Page",
    "PasswordResetToken",
    "PayCalendar",
    "PayrollRecord",
    "PayrollRecordComponent",
    "PayrollRun",
    "PlatformActivityEvent",
    "PlatformActivityType",
    "PlatformActorType",
    "PlatformAdmin",
    "Project",
    "ROLE_CODE_BY_NAME",
    "ROLE_NAME_BY_CODE",
    "Role",
    "RolePageAccess",
    "SYSTEM_ROLES",
    "SalaryStructure",
    "SalaryStructureComponent",
    "SubscriptionPlan",
    "SubscriptionPlanCode",
    "SubscriptionPlanStatus",
    "Task",
    "TaskComment",
    "Tenant",
    "TenantDatabaseAllocation",
    "TenantModule",
    "TenantOffering",
    "TenantStatus",
    "TenantSubscription",
    "TenantSubscriptionStatus",
    "User",
    "UserAccount",
    "UserRole",
    "UserSession",
    "WorkLocation",
]
