export type OfferingRoleType = "PLATFORM" | "TENANT" | "BOTH";

export interface OfferingCatalogItem {
  offering_id: string;
  code: string;
  display_name: string;
  description: string;
  icon_key: string;
  route_slug: string;
  sort_order: number;
  status: "ACTIVE" | "INACTIVE";
  role_type?: OfferingRoleType;
  tenant_entitlement_count: number;
  configuration_category_count: number;
}

export interface OfferingCreatePayload {
  code: string;
  display_name: string;
  description: string;
  icon_key: string;
  route_slug: string;
  sort_order: number;
  status: "ACTIVE" | "INACTIVE";
  role_type: OfferingRoleType;
}

export type OfferingUpdatePayload = Partial<Omit<OfferingCreatePayload, "code" | "status">>;

export interface OfferingListParams {
  query?: string;
  roleType?: OfferingRoleType;
  status?: "ACTIVE" | "INACTIVE";
}
