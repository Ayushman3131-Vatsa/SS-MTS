import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getPrincipalHome, normalizeTenantCode } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { AuthShell } from "../../features/auth/ui/AuthShell/AuthShell";
import { TenantLoginForm } from "../../features/auth/ui/LoginForm/TenantLoginForm";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import type { TenantLoginValues } from "../../features/auth/model/login-schemas";

export const LoginPage = () => {
  const navigate = useNavigate();
  const { tenantCode } = useParams<{ tenantCode?: string }>();
  const lockedTenantCode = tenantCode ? normalizeTenantCode(tenantCode) : null;
  const { loginTenant, notice } = useSession();
  const [serverError, setServerError] = useState<ReturnType<
    typeof getLoginErrorContent
  > | null>(null);

  const handleLogin = async (values: TenantLoginValues) => {
    setServerError(null);

    try {
      const principal = await loginTenant({
        tenant_code: values.tenant_code,
        email: values.email.toLowerCase(),
        password: values.password,
      });
      navigate(getPrincipalHome(principal), { replace: true });
    } catch (error) {
      setServerError(getLoginErrorContent(error));
    }
  };

  return (
    <AuthShell
      eyebrow="Organization access"
      title={lockedTenantCode ? `Sign in to ${lockedTenantCode}` : "Welcome back"}
      description={
        lockedTenantCode
          ? "Enter your work email or username and password to continue."
          : "Enter your organization code, work email or username, and password."
      }
    >
      <TenantLoginForm
        notice={notice}
        lockedTenantCode={lockedTenantCode}
        onSubmit={handleLogin}
        serverError={serverError}
      />
    </AuthShell>
  );
};
