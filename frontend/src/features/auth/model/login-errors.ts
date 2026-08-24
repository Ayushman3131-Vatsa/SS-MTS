import {
  ApiError,
  InvalidApiResponseError,
  NetworkError,
} from "../../../shared/api/errors";

export interface LoginErrorContent {
  title: string;
  message: string;
}

const formatRetryAfter = (seconds: number | null): string => {
  if (seconds === null) {
    return "a few minutes";
  }

  if (seconds < 60) {
    return `${Math.max(1, Math.ceil(seconds))} seconds`;
  }

  return `${Math.ceil(seconds / 60)} minutes`;
};

export const getLoginErrorContent = (
  error: unknown,
): LoginErrorContent => {
  if (error instanceof NetworkError) {
    return {
      title: "Sign-in service unavailable",
      message:
        "We could not reach the service. Check your connection and try again.",
    };
  }

  if (error instanceof ApiError) {
    if (error.code === "ROLE_REQUIRED") {
      return {
        title: "Unable to sign in",
        message: "This account has no assigned role. Contact an administrator.",
      };
    }

    if (error.status === 401) {
      return {
        title: "Unable to sign in",
        message:
          "The email or password is not recognized. Check your details and try again.",
      };
    }

    if (error.status === 429) {
      return {
        title: "Too many sign-in attempts",
        message: `For your security, sign-in is temporarily limited. Try again in ${formatRetryAfter(error.retryAfterSeconds)}.`,
      };
    }

    if (error.status === 422) {
      return {
        title: "Check your details",
        message: "One or more fields were not accepted by the service.",
      };
    }

    if (error.status >= 500) {
      return {
        title: "Service temporarily unavailable",
        message: "The service could not complete sign-in. Try again shortly.",
      };
    }
  }

  if (error instanceof InvalidApiResponseError) {
    return {
      title: "Unexpected service response",
      message: "Refresh the page and try again. Contact support if this continues.",
    };
  }

  return {
    title: "Sign-in could not be completed",
    message: "Review your details and try again.",
  };
};
