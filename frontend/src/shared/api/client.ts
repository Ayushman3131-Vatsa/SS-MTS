import { readCookie } from "./cookies";
import {
  ApiError,
  InvalidApiResponseError,
  NetworkError,
} from "./errors";
import { announceSessionExpiry } from "./session-events";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE_URL = (configuredBaseUrl || "/api").replace(/\/$/, "");
const CSRF_COOKIE_NAME =
  import.meta.env.VITE_CSRF_COOKIE_NAME?.trim() || "mt_csrf";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

type RequestOptions = Omit<RequestInit, "body" | "credentials"> & {
  body?: unknown;
  notifyOnUnauthorized?: boolean;
};

const extractErrorMessage = async (response: Response): Promise<string> => {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.length > 0) {
      return payload.detail;
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
        return messages.slice(0, 3).join(" ");
      }
    }
  } catch {
    // A generic status message is safer and more useful than a JSON parse error.
  }

  return response.statusText || "The request could not be completed.";
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
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(requestBody);
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

    throw new ApiError(
      await extractErrorMessage(response),
      response.status,
      parseRetryAfter(response),
    );
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
