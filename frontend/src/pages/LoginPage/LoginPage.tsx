import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { AuthShell } from "../../features/auth/ui/AuthShell/AuthShell";
import { TenantLoginForm } from "../../features/auth/ui/LoginForm/TenantLoginForm";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import type { TenantLoginValues } from "../../features/auth/model/login-schemas";
import {
  getRememberedWorkspace,
  setRememberedWorkspace,
} from "../../features/auth/model/workspace-storage";

export const LoginPage = () => {
  const navigate = useNavigate();
  const { loginTenant, notice } = useSession();
  const [serverError, setServerError] = useState<ReturnType<
    typeof getLoginErrorContent
  > | null>(null);
  const [initialWorkspace] = useState(getRememberedWorkspace);

  const handleLogin = async (values: TenantLoginValues) => {
    setServerError(null);

    try {
      const principal = await loginTenant({
        workspace_slug: values.workspaceSlug,
        email: values.email.toLowerCase(),
        password: values.password,
      });

      setRememberedWorkspace(
        values.rememberWorkspace ? values.workspaceSlug : null,
      );
      navigate(getPrincipalHome(principal), { replace: true });
    } catch (error) {
      setServerError(getLoginErrorContent(error));
    }
  };

  return (
    <AuthShell
      eyebrow="Organization access"
      title="Welcome back"
      description="Enter your organization workspace and account details to continue."
    >
      <TenantLoginForm
        initialWorkspace={initialWorkspace}
        notice={notice}
        onSubmit={handleLogin}
        serverError={serverError}
      />
    </AuthShell>
  );
};
