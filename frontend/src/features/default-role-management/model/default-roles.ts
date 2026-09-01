export type AccessLevel = "none" | "view" | "modify";

export interface DefaultRolePage {
  page_id: string;
  page_code: string;
  module: string;
  page_name: string;
  route: string;
  app_scope: string;
  offering_code: string | null;
}

export interface DefaultRolePageAccess {
  page: DefaultRolePage;
  access_level: AccessLevel;
}

export interface DefaultRoleListItem {
  role_id: string;
  role_code: string;
  role_name: string;
  description: string | null;
  offering_id: string | null;
  offering_code: string | null;
  offering_name: string | null;
  module_scope: string;
  is_system: boolean;
  is_active: boolean;
  page_count: number;
  modify_count: number;
  view_count: number;
  none_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DefaultRoleDetail extends DefaultRoleListItem {
  page_access: DefaultRolePageAccess[];
}

export interface DefaultRolePagesCatalog {
  module_scope: string;
  offering_id: string | null;
  offering_code: string | null;
  offering_name: string | null;
  pages: DefaultRolePage[];
}

export interface DefaultRoleCreatePayload {
  role_name: string;
  role_code?: string;
  description?: string | null;
  offering_id?: string | null;
  is_system?: boolean;
  is_active?: boolean;
  entries?: Array<{ page_id: string; access_level: AccessLevel }>;
}

export interface DefaultRoleUpdatePayload {
  role_name?: string;
  description?: string | null;
  is_active?: boolean;
  version: number;
  entries?: Array<{ page_id: string; access_level: AccessLevel }>;
}

export const ACCESS_LEVELS: AccessLevel[] = ["none", "view", "modify"];

export const accessLevelLabel: Record<AccessLevel, string> = {
  none: "None",
  view: "View",
  modify: "Modify",
};
