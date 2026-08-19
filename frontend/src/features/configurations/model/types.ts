export type ConfigTemplateType = "EMAIL" | "LETTER" | "NOTIFICATION" | "OTHER";
export type ConfigCategoryStatus = "ACTIVE" | "INACTIVE";

export interface ConfigCategoryResponse {
  category_id: string;
  offering_id: string;
  offering_code: string;
  offering_display_name: string;
  code: string;
  display_name: string;
  description: string;
  icon_key: string;
  sort_order: number;
  status: ConfigCategoryStatus;
  template_count: number;
}

export interface ConfigTemplateListItem {
  template_id: string;
  category_id: string;
  code: string;
  display_name: string;
  description: string;
  template_type: ConfigTemplateType;
  subject: string | null;
  is_active: boolean;
  sort_order: number;
  is_customized: boolean;
}

export interface TemplatePlaceholder {
  key: string;
  label: string;
  sample_value: string;
  required?: boolean;
}

export interface ConfigTemplateDetailResponse {
  template_id: string;
  category_id: string;
  code: string;
  display_name: string;
  description: string;
  template_type: ConfigTemplateType;
  subject: string | null;
  body: string;
  placeholders: TemplatePlaceholder[];
  metadata: Record<string, unknown>;
  is_active: boolean;
  sort_order: number;
  is_customized: boolean;
  default_subject: string | null;
  default_body: string | null;
}

export interface TemplateOverrideRequest {
  subject?: string | null;
  body?: string | null;
  metadata?: Record<string, unknown> | null;
  is_active?: boolean | null;
}

export interface TemplatePreviewRequest {
  sample_data: Record<string, string>;
}

export interface TemplatePreviewResponse {
  subject: string | null;
  rendered_body: string;
}
