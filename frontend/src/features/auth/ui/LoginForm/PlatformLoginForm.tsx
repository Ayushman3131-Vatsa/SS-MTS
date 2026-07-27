import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { Alert } from "../../../../shared/ui/Alert/Alert";
import { Button } from "../../../../shared/ui/Button/Button";
import { InputField } from "../../../../shared/ui/InputField/InputField";
import {
  platformLoginSchema,
  type PlatformLoginValues,
} from "../../model/login-schemas";
import styles from "./LoginForm.module.css";

interface PlatformLoginFormProps {
  notice?: string | null;
  onSubmit: (values: PlatformLoginValues) => Promise<void>;
  serverError?: { title: string; message: string } | null;
}

export const PlatformLoginForm = ({
  notice,
  onSubmit,
  serverError,
}: PlatformLoginFormProps) => {
  const [showPassword, setShowPassword] = useState(false);
  const serverErrorRef = useRef<HTMLDivElement>(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<PlatformLoginValues>({
    resolver: zodResolver(platformLoginSchema),
    defaultValues: { email: "", password: "" },
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

      <div className={styles.operatorNotice}>
        <ShieldCheck size={19} aria-hidden="true" />
        <span>
          Authorized operators only. Platform administrator accounts are
          provisioned through secure backend operations.
        </span>
      </div>

      <InputField
        id="platform-email"
        type="email"
        label="Administrator email"
        placeholder="admin@platform.example"
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        disabled={isSubmitting}
        leadingIcon={<Mail size={18} />}
        error={errors.email?.message}
        {...register("email")}
      />

      <InputField
        id="platform-password"
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

      <Button
        type="submit"
        fullWidth
        loading={isSubmitting}
        loadingLabel="Signing in…"
      >
        Sign in to platform console
      </Button>

      <Link className={styles.modeLink} to="/login">
        <ArrowLeft size={17} aria-hidden="true" />
        Back to organization sign in
      </Link>
    </form>
  );
};
