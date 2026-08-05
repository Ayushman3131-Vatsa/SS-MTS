export class ApiError extends Error {
  readonly status: number;
  readonly retryAfterSeconds: number | null;
  readonly code: string;

  constructor(
    message: string,
    status: number,
    retryAfterSeconds: number | null = null,
    code = "APP_ERROR",
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
    this.code = code;
  }
}

export class NetworkError extends Error {
  constructor() {
    super("The service could not be reached.");
    this.name = "NetworkError";
  }
}

export class InvalidApiResponseError extends Error {
  constructor() {
    super("The server returned an unexpected response.");
    this.name = "InvalidApiResponseError";
  }
}
