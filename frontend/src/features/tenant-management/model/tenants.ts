export interface LicensedOffering {
  offering_id: string;
  code: string;
  display_name: string;
  description: string;
  icon_key: string;
  route_slug: string;
  sort_order: number;
}

export interface OfferingCatalogEntry extends LicensedOffering {
  status: string;
}

export interface TenantOfferingEntitlement extends LicensedOffering {
  entitlement_id: string;
  status: string;
  starts_at: string;
  ends_at: string | null;
  suspended_at: string | null;
  deactivated_at: string | null;
  reason: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TenantOfferingEvent {
  event_id: string;
  entitlement_id: string;
  tenant_id: string;
  event_type: string;
  actor_admin_id: string | null;
  occurred_at: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
}

export interface SubscriptionPlanOption {
  code: string;
  display_name: string;
  price: number | null;
  currency: string | null;
  billing_interval: string | null;
  max_users: number | null;
  requires_end_date: boolean;
}

export interface TenantRegistrationOptions {
  plans: SubscriptionPlanOption[];
  offerings: LicensedOffering[];
  statuses: string[];
  database_modes: string[];
  defaults: {
    subscription_plan_code: string;
    status: string;
    database_mode: string;
  };
}

export interface TenantRecord {
  tenant_id: string;
  org_name: string;
  tenant_code: string;
  legal_name: string | null;
  industry: string | null;
  company_size: string | null;
  website: string | null;
  tax_registration_number: string | null;
  pan_number: string | null;
  address_line_1: string | null;
  address_line_2: string | null;
  city: string | null;
  state_province: string | null;
  country: string | null;
  postal_code: string | null;
  contact_name: string | null;
  contact_designation: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  alternate_contact_name?: string | null;
  alternate_contact_designation?: string | null;
  alternate_contact_email?: string | null;
  alternate_contact_phone?: string | null;
  subscription_plan: string;
  subscription_plan_code: string;
  subscription_ends_at: string | null;
  status: string;
  database_mode: string;
  database_provisioning_state: string;
  user_count: number;
  offerings: TenantOfferingEntitlement[];
  created_by_admin_id: string;
  created_at: string;
  updated_at: string;
  version: number;
  first_access?: TenantFirstAccess | null;
}

export interface TenantFirstAccess {
  email: string | null;
  username?: string | null;
  temporary_password: string;
  login_path: string;
  password_change_required: boolean;
  smartskale_access?: TenantFirstAccess | null;
}

export interface TenantListResponse {
  items: TenantRecord[];
  page: number;
  page_size: number;
  total: number;
}

export interface TenantRegistrationPayload {
  org_name: string;
  tenant_code: string;
  subscription_plan_code: string;
  subscription_ends_at: string | null;
  status: string;
  database_mode: string;
  legal_name: string;
  industry: string;
  company_size: string;
  website: string | null;
  tax_registration_number: string | null;
  pan_number: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
  contact_name: string;
  contact_designation: string;
  contact_email: string;
  contact_phone: string;
  alternate_contact_name: string | null;
  alternate_contact_designation: string | null;
  alternate_contact_email: string | null;
  alternate_contact_phone: string | null;
  offering_ids?: string[];
  offering_grants?: Array<{
    offering_id: string;
    starts_at: string;
    ends_at: string;
    expected_tenant_version?: number;
    reason?: string | null;
  }>;
  bootstrap_role_ids?: string[];
}

export interface TenantOfferingActionPayload {
  expected_version: number;
  reason?: string | null;
}

export interface TenantOfferingRemovalPayload {
  expected_version: number;
  reason: string;
}

export interface TenantOfferingGrantPayload {
  offering_id: string;
  starts_at: string;
  ends_at: string;
  expected_tenant_version: number;
  reason?: string | null;
}

export type TenantStatusActionPayload = TenantOfferingActionPayload;
