import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, KeyRound, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { AuthShell } from "../../features/auth/ui/AuthShell/AuthShell";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { InputField } from "../../shared/ui/InputField/InputField";
import styles from "./ForcedPasswordChangePage.module.css";

const schema = z
  .object({
    currentPassword: z.string().min(1, "Enter the temporary password.").max(128),
    newPassword: z
      .string()
      .min(12, "Use at least 12 characters.")
      .max(128, "Password must be 128 characters or fewer.")
      .regex(/[a-z]/, "Include a lowercase letter.")
      .regex(/[A-Z]/, "Include an uppercase letter.")
      .regex(/[0-9]/, "Include a number.")
      .regex(/[^\p{L}\p{N}\s]/u, "Include a special character."),
    confirmPassword: z.string().min(1, "Confirm the new password."),
  })
  .superRefine((values, context) => {
    if (values.newPassword === values.currentPassword) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["newPassword"],
        message: "Choose a password different from the temporary password.",
      });
    }
    if (values.newPassword !== values.confirmPassword) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["confirmPassword"],
        message: "Passwords do not match.",
      });
    }
  });

type Values = z.infer<typeof schema>;

export const ForcedPasswordChangePage = () => {
  const navigate = useNavigate();
  const { changePassword, principal } = useSession();
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
    mode: "onTouched",
  });

  if (!principal || principal.principal_type !== "tenant_user") return null;
  if (!principal.password_change_required) {
    return <Navigate to={getPrincipalHome(principal)} replace />;
  }

  const submit = async (values: Values) => {
    setServerError(null);
    try {
      const updated = await changePassword({
        current_password: values.currentPassword,
        new_password: values.newPassword,
      });
      navigate(getPrincipalHome(updated), { replace: true });
    } catch (error) {
      setServerError(getLoginErrorContent(error).message);
    }
  };

  return (
    <AuthShell
      eyebrow="Account security"
      title="Create your password"
      description={`Replace the temporary password for ${principal.tenant.org_name} before continuing.`}
    >
      <form className={styles.form} onSubmit={handleSubmit(submit)} noValidate>
        {serverError && <Alert tone="error" title="Password could not be changed">{serverError}</Alert>}
        <InputField
          id="current-password"
          type={showCurrent ? "text" : "password"}
          label="Temporary password"
          autoComplete="current-password"
          disabled={isSubmitting}
          leadingIcon={<KeyRound size={18} />}
          error={errors.currentPassword?.message}
          trailingControl={(
            <button type="button" onClick={() => setShowCurrent((value) => !value)} aria-label={showCurrent ? "Hide temporary password" : "Show temporary password"}>
              {showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          )}
          {...register("currentPassword")}
        />
        <InputField
          id="new-password"
          type={showNew ? "text" : "password"}
          label="New password"
          autoComplete="new-password"
          disabled={isSubmitting}
          leadingIcon={<LockKeyhole size={18} />}
          error={errors.newPassword?.message}
          hint="At least 12 characters with upper, lower, number, and symbol."
          trailingControl={(
            <button type="button" onClick={() => setShowNew((value) => !value)} aria-label={showNew ? "Hide new password" : "Show new password"}>
              {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          )}
          {...register("newPassword")}
        />
        <InputField
          id="confirm-password"
          type={showNew ? "text" : "password"}
          label="Confirm new password"
          autoComplete="new-password"
          disabled={isSubmitting}
          leadingIcon={<LockKeyhole size={18} />}
          error={errors.confirmPassword?.message}
          {...register("confirmPassword")}
        />
        <Button type="submit" fullWidth loading={isSubmitting} loadingLabel="Updating password…">
          Save password and continue
        </Button>
      </form>
    </AuthShell>
  );
};

