import { createContext, useContext } from "react";

import type {
  PlatformLoginCredentials,
  SessionPrincipal,
  SessionStatus,
  TenantLoginCredentials,
} from "./session";

export interface SessionContextValue {
  status: SessionStatus;
  principal: SessionPrincipal | null;
  notice: string | null;
  clearNotice: () => void;
  loginTenant: (
    credentials: TenantLoginCredentials,
  ) => Promise<SessionPrincipal>;
  loginPlatform: (
    credentials: PlatformLoginCredentials,
  ) => Promise<SessionPrincipal>;
  logout: () => Promise<void>;
  retryBootstrap: () => Promise<void>;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export const useSession = (): SessionContextValue => {
  const context = useContext(SessionContext);

  if (!context) {
    throw new Error("useSession must be used inside AuthProvider");
  }

  return context;
};
