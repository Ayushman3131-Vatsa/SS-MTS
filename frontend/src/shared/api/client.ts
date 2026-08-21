import { readCookie } from "./cookies";
import {
  ApiError,
  InvalidApiResponseError,
  NetworkError,
} from "./errors";
import { announceSessionExpiry, announceTenantAccessChanged } from "./session-events";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE_URL = (configuredBaseUrl || "/api").replace(/\/$/, "");
const CSRF_COOKIE_NAME =
  import.meta.env.VITE_CSRF_COOKIE_NAME?.trim() || "mt_csrf";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

type RequestOptions = Omit<RequestInit, "body" | "credentials"> & {
  body?: unknown;
  notifyOnUnauthorized?: boolean;
};

export interface DownloadedFile {
  blob: Blob;
  filename: string | null;
}

const extractError = async (response: Response): Promise<{ message: string; code: string }> => {
  try {
    const payload = (await response.json()) as { code?: unknown; detail?: unknown };
    const code = typeof payload.code === "string" ? payload.code : "APP_ERROR";
    if (typeof payload.detail === "string" && payload.detail.length > 0) {
      return { message: payload.detail, code };
    }
    if (Array.isArray(payload.detail)) {
      const messages = payload.detail
        .map((issue: unknown) => {
          if (!issue || typeof issue !== "object") {
            return null;
          }
          const validationIssue = issue as { loc?: unknown; msg?: unknown };
          if (
            typeof validationIssue.msg !== "string" ||
            validationIssue.msg.length === 0
          ) {
            return null;
          }
          const message = validationIssue.msg.replace(/^Value error,\s*/i, "");
          const location = Array.isArray(validationIssue.loc)
            ? validationIssue.loc.filter(
                (part): part is string =>
                  typeof part === "string" && part !== "body",
              )
            : [];
          const field = location.at(-1);
          if (!field) {
            return message;
          }
          const label = field
            .replaceAll("_", " ")
            .replace(/^\w/, (character) => character.toUpperCase());
          return `${label}: ${message}`;
        })
        .filter((message): message is string => Boolean(message));
      if (messages.length > 0) {
        return { message: messages.slice(0, 3).join(" "), code };
      }
    }
  } catch {
    // A generic status message is safer and more useful than a JSON parse error.
  }

  return { message: response.statusText || "The request could not be completed.", code: "APP_ERROR" };
};

const parseRetryAfter = (response: Response): number | null => {
  const value = response.headers.get("Retry-After");
  if (!value) {
    return null;
  }

  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
};

export const apiRequest = async <T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> => {
  const {
    body: requestBody,
    notifyOnUnauthorized = true,
    ...fetchOptions
  } = options;
  const method = (fetchOptions.method || "GET").toUpperCase();
  const headers = new Headers(fetchOptions.headers);
  headers.set("Accept", "application/json");

  let body: BodyInit | undefined;
  if (requestBody !== undefined) {
    if (requestBody instanceof FormData) {
      body = requestBody;
    } else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(requestBody);
    }
  }

  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      method,
      headers,
      body,
      credentials: "include",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new NetworkError();
  }

  if (!response.ok) {
    if (response.status === 401 && notifyOnUnauthorized) {
      announceSessionExpiry();
    }

    const apiError = await extractError(response);
    if (["TENANT_SUSPENDED", "PASSWORD_CHANGE_REQUIRED", "OFFERING_NOT_EFFECTIVE", "OFFERING_NOT_ENTITLED", "OFFERING_NOT_STARTED", "OFFERING_DEACTIVATED", "OFFERING_EXPIRED", "OFFERING_SUSPENDED"].includes(apiError.code)) {
      announceTenantAccessChanged(apiError.code);
    }
    throw new ApiError(apiError.message, response.status, parseRetryAfter(response), apiError.code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new InvalidApiResponseError();
  }
};

const downloadFilename = (response: Response): string | null => {
  const disposition = response.headers.get("Content-Disposition");
  if (!disposition) return null;
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (utf8) {
    try {
      return decodeURIComponent(utf8);
    } catch {
      return utf8;
    }
  }
  return disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? null;
};

export const apiDownload = async (
  path: string,
  signal?: AbortSignal,
): Promise<DownloadedFile> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "GET",
      headers: { Accept: "application/octet-stream" },
      credentials: "include",
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new NetworkError();
  }

  if (!response.ok) {
    if (response.status === 401) announceSessionExpiry();
    const apiError = await extractError(response);
    if (["TENANT_SUSPENDED", "PASSWORD_CHANGE_REQUIRED", "OFFERING_NOT_EFFECTIVE", "OFFERING_NOT_ENTITLED", "OFFERING_NOT_STARTED", "OFFERING_DEACTIVATED", "OFFERING_EXPIRED", "OFFERING_SUSPENDED"].includes(apiError.code)) {
      announceTenantAccessChanged(apiError.code);
    }
    throw new ApiError(apiError.message, response.status, parseRetryAfter(response), apiError.code);
  }

  return {
    blob: await response.blob(),
    filename: downloadFilename(response),
  };
};
