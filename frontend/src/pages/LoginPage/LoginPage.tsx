import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getPrincipalHome, normalizeTenantCode } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { sessionApi } from "../../features/auth/api/session-api";
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

  const [tenantInfo, setTenantInfo] = useState<{
    orgName: string | null;
    isValid: boolean | null;
  }>({
    orgName: null,
    isValid: null,
  });

  useEffect(() => {
    if (!lockedTenantCode) {
      setTenantInfo({ orgName: null, isValid: null });
      return;
    }

    let isMounted = true;
    sessionApi
      .lookupTenant(lockedTenantCode)
      .then((res) => {
        if (!isMounted) return;
        if (res.exists) {
          setTenantInfo({
            orgName: res.org_name || res.tenant_code,
            isValid: true,
          });
          setServerError(null);
        } else {
          setTenantInfo({
            orgName: null,
            isValid: false,
          });
          setServerError({
            title: "Tenant not found",
            message: `Tenant "${lockedTenantCode}" does not exist. Please check the URL or enter your tenant code below.`,
          });
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setTenantInfo({ orgName: null, isValid: null });
      });

    return () => {
      isMounted = false;
    };
  }, [lockedTenantCode]);

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

  const isLockedValid = lockedTenantCode !== null && tenantInfo.isValid === true;
  const effectiveLockedCode = isLockedValid ? lockedTenantCode : null;

  const displayTitle = isLockedValid
    ? `Sign in to ${tenantInfo.orgName || lockedTenantCode}`
    : tenantInfo.isValid === false
    ? "Tenant not found"
    : lockedTenantCode
    ? `Sign in to ${lockedTenantCode}`
    : "Welcome back";

  const displayDescription = isLockedValid
    ? "Enter your work email or username and password to continue."
    : "Enter your tenant code, work email or username, and password.";

  return (
    <AuthShell
      eyebrow="Organization access"
      title={displayTitle}
      description={displayDescription}
    >
      <TenantLoginForm
        notice={notice}
        lockedTenantCode={effectiveLockedCode}
        onSubmit={handleLogin}
        serverError={serverError}
      />
    </AuthShell>
  );
};
