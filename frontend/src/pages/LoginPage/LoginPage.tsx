import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { AuthShell } from "../../features/auth/ui/AuthShell/AuthShell";
import { TenantLoginForm } from "../../features/auth/ui/LoginForm/TenantLoginForm";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import type { TenantLoginValues } from "../../features/auth/model/login-schemas";

export const LoginPage = () => {
  const navigate = useNavigate();
  const { loginTenant, notice } = useSession();
  const [serverError, setServerError] = useState<ReturnType<
    typeof getLoginErrorContent
  > | null>(null);

  const handleLogin = async (values: TenantLoginValues) => {
    setServerError(null);

    try {
      const principal = await loginTenant({
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
      title="Welcome back"
      description="Enter your work email and password to continue."
    >
      <TenantLoginForm
        notice={notice}
        onSubmit={handleLogin}
        serverError={serverError}
      />
    </AuthShell>
  );
};
