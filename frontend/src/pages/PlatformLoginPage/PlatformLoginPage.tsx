import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import type { PlatformLoginValues } from "../../features/auth/model/login-schemas";
import { AuthShell } from "../../features/auth/ui/AuthShell/AuthShell";
import { PlatformLoginForm } from "../../features/auth/ui/LoginForm/PlatformLoginForm";

export const PlatformLoginPage = () => {
  const navigate = useNavigate();
  const { loginPlatform, notice } = useSession();
  const [serverError, setServerError] = useState<ReturnType<
    typeof getLoginErrorContent
  > | null>(null);

  const handleLogin = async (values: PlatformLoginValues) => {
    setServerError(null);

    try {
      const principal = await loginPlatform({
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
      eyebrow="Platform console"
      title="Administrator sign in"
      description="Use your separately provisioned platform administrator account."
    >
      <PlatformLoginForm
        notice={notice}
        onSubmit={handleLogin}
        serverError={serverError}
      />
    </AuthShell>
  );
};
