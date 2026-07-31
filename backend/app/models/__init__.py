from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.candidate_compensation import CandidateCompensation
from app.models.candidate_education import CandidateEducation
from app.models.candidate_emergency_contacts import CandidateEmergencyContact
from app.models.candidate_employment_history import CandidateEmploymentHistory
from app.models.candidate_personal_details import CandidatePersonalDetails
from app.models.candidate_status_log import CandidateStatusLog
from app.models.candidate_uploaded_document import CandidateUploadedDocument
from app.models.daily_progress_log import DailyProgressLog
from app.models.departments import Department
from app.models.designation import Designation
from app.models.document import Document
from app.models.email_log import EmailLog
from app.models.employee import Employee
from app.models.employee_bank_details import EmployeeBankDetails
from app.models.employee_compensation import EmployeeCompensation
from app.models.employee_compensation_component import EmployeeCompensationComponent
from app.models.employee_dependents import EmployeeDependent
from app.models.employee_education import EmployeeEducation
from app.models.employee_emergency_contacts import EmployeeEmergencyContact
from app.models.employee_employment_details import EmployeeEmploymentDetails
from app.models.employee_employment_history import EmployeeEmploymentHistory
from app.models.employee_personal_details import EmployeePersonalDetails
from app.models.employee_status_log import EmployeeStatusLog
from app.models.employee_uploaded_document import EmployeeUploadedDocument
from app.models.employee_ytd_balance import EmployeeYtdBalance
from app.models.enums import (
    DatabaseIsolationMode,
    DatabaseProvisioningState,
    PlatformActivityType,
    PlatformActorType,
    SubscriptionPlanCode,
    SubscriptionPlanStatus,
    TenantStatus,
    TenantSubscriptionStatus,
)
from app.models.exit_interview import ExitInterview
from app.models.offering import Offering
from app.models.page import Page
from app.models.password_reset_token import PasswordResetToken
from app.models.pay_calendar import PayCalendar
from app.models.payroll_record import PayrollRecord
from app.models.payroll_record_component import PayrollRecordComponent
from app.models.payroll_run import PayrollRun
from app.models.platform_activity_event import PlatformActivityEvent
from app.models.platform_admin import PlatformAdmin
from app.models.project import Project
from app.models.role import Role
from app.models.role_page_access import RolePageAccess
from app.models.salary_structure import SalaryStructure
from app.models.salary_structure_component import SalaryStructureComponent
from app.models.subscription_plan import SubscriptionPlan
from app.models.system_roles import ROLE_CODE_BY_NAME, ROLE_NAME_BY_CODE, SYSTEM_ROLES
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.models.tenant import Tenant
from app.models.tenant_database_allocation import TenantDatabaseAllocation
from app.models.tenant_module import TenantModule
from app.models.tenant_offering import TenantOffering
from app.models.tenant_subscription import TenantSubscription
from app.models.user_account import UserAccount
from app.models.user_role import UserRole
from app.models.user_session import UserSession
from app.models.work_location import WorkLocation

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
