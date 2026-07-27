export interface LicensedOffering {
  offering_id: string;
  code: string;
  display_name: string;
  description: string;
  icon_key: string;
  route_slug: string;
  sort_order: number;
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
  workspace_slug: string;
  legal_name: string | null;
  industry: string | null;
  company_size: string | null;
  website: string | null;
  registration_number: string | null;
  tax_identifier: string | null;
  address_line_1: string | null;
  address_line_2: string | null;
  city: string | null;
  state_province: string | null;
  country: string | null;
  postal_code: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  subscription_plan: string;
  subscription_plan_code: string;
  subscription_ends_at: string | null;
  status: string;
  database_mode: string;
  database_provisioning_state: string;
  user_count: number;
  offerings: LicensedOffering[];
  created_by_admin_id: string;
  created_at: string;
  updated_at: string;
}

export interface TenantRegistrationPayload {
  org_name: string;
  tenant_code: string;
  workspace_slug: string;
  subscription_plan_code: string;
  subscription_ends_at: string | null;
  status: string;
  database_mode: string;
  legal_name: string;
  industry: string;
  company_size: string;
  website: string | null;
  registration_number: string | null;
  tax_identifier: string | null;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state_province: string;
  country: string;
  postal_code: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  offering_ids: string[];
  tenant_admin_name: string;
  tenant_admin_email: string;
  tenant_admin_password: string;
}
