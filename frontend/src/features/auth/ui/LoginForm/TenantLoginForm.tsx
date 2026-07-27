import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, Eye, EyeOff, LockKeyhole, Mail, Shield } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { Alert } from "../../../../shared/ui/Alert/Alert";
import { Button } from "../../../../shared/ui/Button/Button";
import { InputField } from "../../../../shared/ui/InputField/InputField";
import {
  tenantLoginSchema,
  type TenantLoginValues,
} from "../../model/login-schemas";
import styles from "./LoginForm.module.css";

interface TenantLoginFormProps {
  initialWorkspace?: string;
  notice?: string | null;
  onSubmit: (values: TenantLoginValues) => Promise<void>;
  serverError?: { title: string; message: string } | null;
}

export const TenantLoginForm = ({
  initialWorkspace = "",
  notice,
  onSubmit,
  serverError,
}: TenantLoginFormProps) => {
  const [showPassword, setShowPassword] = useState(false);
  const serverErrorRef = useRef<HTMLDivElement>(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<TenantLoginValues>({
    resolver: zodResolver(tenantLoginSchema),
    defaultValues: {
      workspaceSlug: initialWorkspace,
      email: "",
      password: "",
      rememberWorkspace: Boolean(initialWorkspace),
    },
    mode: "onTouched",
  });

  useEffect(() => {
    if (serverError) {
      serverErrorRef.current?.focus();
    }
  }, [serverError]);

  return (
    <form
      className={styles.form}
      onSubmit={handleSubmit(onSubmit)}
      noValidate
    >
      {notice && <Alert>{notice}</Alert>}
      {serverError && (
        <div
          ref={serverErrorRef}
          className={styles.alertFocus}
          tabIndex={-1}
        >
          <Alert tone="error" title={serverError.title}>
            {serverError.message}
          </Alert>
        </div>
      )}

      <InputField
        id="workspace-slug"
        label="Workspace"
        placeholder="northstar-labs"
        autoComplete="organization"
        autoCapitalize="none"
        spellCheck={false}
        disabled={isSubmitting}
        leadingIcon={<Building2 size={18} />}
        error={errors.workspaceSlug?.message}
        hint="The unique name used by your organization."
        {...register("workspaceSlug", {
          setValueAs: (value: string) => value.trim().toLowerCase(),
        })}
      />

      <InputField
        id="tenant-email"
        type="email"
        label="Work email"
        placeholder="you@company.com"
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        disabled={isSubmitting}
        leadingIcon={<Mail size={18} />}
        error={errors.email?.message}
        {...register("email")}
      />

      <InputField
        id="tenant-password"
        type={showPassword ? "text" : "password"}
        label="Password"
        placeholder="Enter your password"
        autoComplete="current-password"
        disabled={isSubmitting}
        leadingIcon={<LockKeyhole size={18} />}
        error={errors.password?.message}
        trailingControl={
          <button
            type="button"
            onClick={() => setShowPassword((visible) => !visible)}
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
            disabled={isSubmitting}
          >
            {showPassword ? (
              <EyeOff size={18} aria-hidden="true" />
            ) : (
              <Eye size={18} aria-hidden="true" />
            )}
          </button>
        }
        {...register("password")}
      />

      <div className={styles.options}>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            disabled={isSubmitting}
            {...register("rememberWorkspace")}
          />
          Remember workspace
        </label>
      </div>

      <Button
        type="submit"
        fullWidth
        loading={isSubmitting}
        loadingLabel="Signing in…"
      >
        Sign in to workspace
      </Button>

      <p className={styles.help}>
        Can’t access your account?{" "}
        <strong>Contact your organization administrator.</strong>
      </p>

      <div className={styles.divider}>Platform operations</div>

      <Link className={styles.modeLink} to="/login/platform">
        <Shield size={17} aria-hidden="true" />
        Platform administrator
      </Link>
    </form>
  );
};
