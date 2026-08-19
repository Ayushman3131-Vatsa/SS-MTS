export const DEFAULT_TEMPLATE_TYPES = [
  "EMAIL",
  "LETTER",
  "NOTIFICATION",
  "OTHER",
] as const;

export type DefaultTemplateType = (typeof DEFAULT_TEMPLATE_TYPES)[number];

export interface DefaultTemplatePlaceholder {
  key: string;
  label: string;
  sample_value: string;
  required: boolean;
}

export interface DefaultTemplateListItem {
  template_id: string;
  offering_id: string;
  offering_code: string;
  offering_name: string;
  category_id: string;
  category_code: string;
  category_name: string;
  code: string;
  name: string;
  description: string;
  type: DefaultTemplateType;
  subject: string | null;
  sort_order: number;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  inheriting_tenant_count: number;
  customized_tenant_count: number;
}

export interface DefaultTemplateDetail extends DefaultTemplateListItem {
  body: string;
  placeholders: DefaultTemplatePlaceholder[];
}

export interface DefaultTemplateCreatePayload {
  offering_id: string;
  code: string;
  name: string;
  description: string;
  type: DefaultTemplateType;
  subject: string | null;
  body: string;
  placeholders: DefaultTemplatePlaceholder[];
  sort_order: number;
}

export interface DefaultTemplateUpdatePayload {
  expected_version: number;
  name?: string;
  description?: string;
  subject?: string | null;
  body?: string;
  placeholders?: DefaultTemplatePlaceholder[];
  sort_order?: number;
}

export interface DefaultTemplatePreviewPayload {
  subject: string | null;
  body: string;
  placeholders: DefaultTemplatePlaceholder[];
  sample_data: Record<string, string>;
}

export interface DefaultTemplatePreview {
  subject: string | null;
  rendered_body: string;
}
