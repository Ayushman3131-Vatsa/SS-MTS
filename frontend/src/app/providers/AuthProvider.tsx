import {
  type PropsWithChildren,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { SessionContext } from "../../entities/session/model/session-context";
import type {
  PlatformLoginCredentials,
  SessionPrincipal,
  SessionStatus,
  TenantLoginCredentials,
} from "../../entities/session/model/session";
import { sessionApi } from "../../features/auth/api/session-api";
import { ApiError } from "../../shared/api/errors";
import { SESSION_EXPIRED_EVENT } from "../../shared/api/session-events";

const SESSION_EXPIRED_NOTICE =
  "Your session has expired. Sign in again to continue.";

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
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      setPrincipal(null);
      setStatus("unauthenticated");

      if (!(error instanceof ApiError && error.status === 401)) {
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
      logout,
      retryBootstrap,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
};
