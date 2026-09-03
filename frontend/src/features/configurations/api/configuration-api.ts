import { apiRequest } from "../../../shared/api/client";
import type {
  ConfigCategoryResponse,
  ConfigTemplateCatalogItem,
  ConfigTemplateDetailResponse,
  ConfigTemplateListItem,
  TemplateOverrideRequest,
  TemplatePreviewResponse,
} from "../model/types";

export const fetchConfigCategories = async (): Promise<ConfigCategoryResponse[]> => {
  return apiRequest<ConfigCategoryResponse[]>("/config/categories");
};

export const fetchConfigTemplates = async (): Promise<ConfigTemplateCatalogItem[]> => {
  return apiRequest<ConfigTemplateCatalogItem[]>("/config/templates");
};

export const fetchCategoryTemplates = async (
  categoryId: string
): Promise<ConfigTemplateListItem[]> => {
  return apiRequest<ConfigTemplateListItem[]>(
    `/config/categories/${categoryId}/templates`
  );
};

export const fetchTemplateDetail = async (
  templateId: string
): Promise<ConfigTemplateDetailResponse> => {
  return apiRequest<ConfigTemplateDetailResponse>(
    `/config/templates/${templateId}`
  );
};

export const saveTemplateOverride = async (
  templateId: string,
  payload: TemplateOverrideRequest
): Promise<ConfigTemplateDetailResponse> => {
  return apiRequest<ConfigTemplateDetailResponse>(
    `/config/templates/${templateId}/override`,
    {
      method: "PUT",
      body: payload,
    }
  );
};

export const resetTemplateOverride = async (
  templateId: string
): Promise<ConfigTemplateDetailResponse> => {
  return apiRequest<ConfigTemplateDetailResponse>(
    `/config/templates/${templateId}/override`,
    {
      method: "DELETE",
    }
  );
};

export const previewTemplate = async (
  templateId: string,
  sampleData: Record<string, string>
): Promise<TemplatePreviewResponse> => {
  return apiRequest<TemplatePreviewResponse>(
    `/config/templates/${templateId}/preview`,
    {
      method: "POST",
      body: { sample_data: sampleData },
    }
  );
};
