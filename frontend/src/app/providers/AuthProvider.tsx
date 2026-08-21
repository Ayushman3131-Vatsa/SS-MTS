import {
  type PropsWithChildren,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { SessionContext } from "../../entities/session/model/session-context";
import type {
  PasswordChangeCredentials,
  PlatformLoginCredentials,
  SessionPrincipal,
  SessionStatus,
  TenantLoginCredentials,
} from "../../entities/session/model/session";
import { sessionApi } from "../../features/auth/api/session-api";
import { ApiError } from "../../shared/api/errors";
import { SESSION_EXPIRED_EVENT } from "../../shared/api/session-events";
import { TENANT_ACCESS_CHANGED_EVENT } from "../../shared/api/session-events";

const SESSION_EXPIRED_NOTICE =
  "Your session has expired. Sign in again to continue.";

const accessNotice = (code: string | undefined) => {
  switch (code) {
    case "TENANT_SUSPENDED":
      return "This workspace is suspended by the platform administrator. Contact support to restore access.";
    case "PASSWORD_CHANGE_REQUIRED":
      return "Create a permanent password before accessing tenant features.";
    case "OFFERING_EXPIRED":
      return "This module entitlement has expired. Contact your platform administrator for a re-grant.";
    case "OFFERING_SUSPENDED":
      return "This module entitlement is suspended. Contact your platform administrator to resume it.";
    case "OFFERING_DEACTIVATED":
      return "This module entitlement has been deactivated. Contact your platform administrator for a new grant.";
    case "OFFERING_NOT_STARTED":
      return "This module entitlement has not started yet.";
    case "OFFERING_NOT_ENTITLED":
    case "OFFERING_NOT_EFFECTIVE":
      return "This module is not currently enabled for your workspace.";
    default:
      return null;
  }
};

export const AuthProvider = ({ children }: PropsWithChildren) => {
  const [status, setStatus] = useState<SessionStatus>("bootstrapping");
  const [principal, setPrincipal] = useState<SessionPrincipal | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const bootstrap = useCallback(async (signal?: AbortSignal) => {
    setStatus("bootstrapping");

    try {
      const restoredPrincipal = await sessionApi.restore(signal);
      setPrincipal(restoredPrincipal);
      setStatus("authenticated");
      setNotice(null);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      setPrincipal(null);
      setStatus("unauthenticated");

      const accessMessage = error instanceof ApiError ? accessNotice(error.code) : null;
      if (accessMessage) {
        setNotice(accessMessage);
      } else if (!(error instanceof ApiError && error.status === 401)) {
        setNotice(
          "We could not verify an existing session. You can still sign in.",
        );
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void bootstrap(controller.signal);
    return () => controller.abort();
  }, [bootstrap]);

  useEffect(() => {
    const handleExpiry = () => {
      setPrincipal(null);
      setStatus("unauthenticated");
      setNotice(SESSION_EXPIRED_NOTICE);
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpiry);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpiry);
  }, []);

  useEffect(() => {
    const handleAccessChange = (event: Event) => {
      const code = (event as CustomEvent<{ code?: string }>).detail?.code;
      const message = accessNotice(code);
      if (message) setNotice(message);
      void bootstrap();
    };
    window.addEventListener(TENANT_ACCESS_CHANGED_EVENT, handleAccessChange);
    return () => window.removeEventListener(TENANT_ACCESS_CHANGED_EVENT, handleAccessChange);
  }, [bootstrap]);

  const tenantStatus =
    principal?.principal_type === "tenant_user"
      ? principal.tenant.status
      : null;

  useEffect(() => {
    if (tenantStatus === null) return;

    let disposed = false;
    const refreshTenantSession = async () => {
      try {
        const refreshedPrincipal = await sessionApi.restore();
        if (disposed) return;
        setPrincipal(refreshedPrincipal);
        setStatus("authenticated");
        if (
          refreshedPrincipal.principal_type !== "tenant_user" ||
          refreshedPrincipal.tenant.status === "ACTIVE"
        ) {
          setNotice(null);
        }
      } catch (error) {
        if (disposed || !(error instanceof ApiError && error.status === 401)) {
          return;
        }
        setPrincipal(null);
        setStatus("unauthenticated");
        setNotice(SESSION_EXPIRED_NOTICE);
      }
    };

    const intervalId = window.setInterval(() => {
      void refreshTenantSession();
    }, tenantStatus === "SUSPENDED" ? 10_000 : 30_000);
    const handleFocus = () => void refreshTenantSession();
    window.addEventListener("focus", handleFocus);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
    };
  }, [tenantStatus]);

  const loginTenant = useCallback(
    async (credentials: TenantLoginCredentials) => {
      const authenticatedPrincipal = await sessionApi.loginTenant(credentials);
      setPrincipal(authenticatedPrincipal);
      setStatus("authenticated");
      setNotice(null);
      return authenticatedPrincipal;
    },
    [],
  );

  const loginPlatform = useCallback(
    async (credentials: PlatformLoginCredentials) => {
      const authenticatedPrincipal =
        await sessionApi.loginPlatform(credentials);
      setPrincipal(authenticatedPrincipal);
      setStatus("authenticated");
      setNotice(null);
      return authenticatedPrincipal;
    },
    [],
  );

  const changePassword = useCallback(
    async (credentials: PasswordChangeCredentials) => {
      const updatedPrincipal = await sessionApi.changePassword(credentials);
      setPrincipal(updatedPrincipal);
      setStatus("authenticated");
      setNotice(null);
      return updatedPrincipal;
    },
    [],
  );

  const logout = useCallback(async () => {
    await sessionApi.logout();
    setPrincipal(null);
    setStatus("unauthenticated");
    setNotice("You have signed out securely.");
  }, []);

  const clearNotice = useCallback(() => setNotice(null), []);
  const retryBootstrap = useCallback(() => bootstrap(), [bootstrap]);

  const value = useMemo(
    () => ({
      status,
      principal,
      notice,
      clearNotice,
      loginTenant,
      loginPlatform,
      changePassword,
      logout,
      retryBootstrap,
    }),
    [
      status,
      principal,
      notice,
      clearNotice,
      loginTenant,
      loginPlatform,
      changePassword,
      logout,
      retryBootstrap,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
};
