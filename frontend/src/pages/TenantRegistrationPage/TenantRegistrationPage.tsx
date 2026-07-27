import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  Building2,
  Check,
  Eye,
  EyeOff,
  KeyRound,
  MapPin,
  PackageCheck,
  Save,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type {
  TenantRegistrationOptions,
  TenantRegistrationPayload,
} from "../../features/tenant-management/model/tenants";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { ApiError, NetworkError } from "../../shared/api/errors";
import styles from "./TenantRegistrationPage.module.css";

const optionalUrl = z
  .string()
  .trim()
  .refine(
    (value) => value.length === 0 || /^https?:\/\/.+/i.test(value),
    "Enter a full URL beginning with http:// or https://",
  );

const contextTokens = (value: string): string[] => {
  const normalized = value.toLocaleLowerCase();
  const parts = normalized.split(/[^\p{L}\p{N}\p{M}]+/u).filter(
    (part) => part.length >= 3,
  );
  const compact = normalized.replace(/[^\p{L}\p{N}\p{M}]/gu, "");
  return compact.length >= 3 ? [...parts, compact] : parts;
};

const registrationSchema = z.object({
  org_name: z.string().trim().min(1, "Tenant name is required").max(255),
  tenant_code: z
    .string()
    .trim()
    .min(2, "Tenant code is required")
    .max(30)
    .regex(/^[A-Za-z0-9][A-Za-z0-9_-]*$/, "Use letters, numbers, _ or -"),
  status: z.string().min(1),
  subscription_plan_code: z.string().min(1),
  subscription_end_date: z.string(),
  database_mode: z.string().min(1),
  legal_name: z.string().trim().min(1, "Legal name is required").max(255),
  industry: z.string().trim().min(1, "Industry is required").max(100),
  company_size: z.string().trim().min(1, "Company size is required").max(50),
  website: optionalUrl,
  registration_number: z.string().trim().max(100),
  tax_identifier: z.string().trim().max(100),
  address_line_1: z.string().trim().min(1, "Address is required").max(255),
  address_line_2: z.string().trim().max(255),
  city: z.string().trim().min(1, "City is required").max(100),
  state_province: z.string().trim().min(1, "State or province is required").max(100),
  country: z.string().trim().min(1, "Country is required").max(100),
  postal_code: z.string().trim().min(1, "Postal code is required").max(30),
  contact_name: z.string().trim().min(1, "Contact name is required").max(255),
  contact_email: z.string().trim().email("Enter a valid contact email"),
  contact_phone: z
    .string()
    .trim()
    .min(5, "Phone number is required")
    .max(40)
    .regex(/^[0-9+().\-\s]+$/, "Enter a valid phone number"),
  offering_ids: z.array(z.string().uuid()).min(1, "Select at least one offering"),
  workspace_slug: z
    .string()
    .trim()
    .min(3, "Workspace slug is required")
    .max(63)
    .regex(
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      "Use lowercase letters, numbers, and single hyphens",
    ),
  tenant_admin_name: z.string().trim().min(1, "Admin name is required").max(255),
  tenant_admin_email: z.string().trim().email("Enter a valid login email"),
  tenant_admin_password: z
    .string()
    .min(12, "Use at least 12 characters")
    .max(128)
    .regex(/[a-z]/, "Include a lowercase letter")
    .regex(/[A-Z]/, "Include an uppercase letter")
    .regex(/[0-9]/, "Include a number")
    .regex(/[^\p{L}\p{N}\s]/u, "Include a special character"),
}).superRefine((values, context) => {
  const compactPassword = values.tenant_admin_password
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}\p{M}]/gu, "");
  const emailName = values.tenant_admin_email.split("@")[0] ?? "";
  const tokens = [
    values.org_name,
    values.workspace_slug,
    values.tenant_admin_name,
    emailName,
  ].flatMap(contextTokens);
  if (tokens.some((token) => compactPassword.includes(token))) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["tenant_admin_password"],
      message:
        "Do not include the admin name, email, organization, or workspace",
    });
  }
});

type RegistrationFormValues = z.infer<typeof registrationSchema>;

const emptyDefaults: RegistrationFormValues = {
  org_name: "",
  tenant_code: "",
  status: "",
  subscription_plan_code: "",
  subscription_end_date: "",
  database_mode: "",
  legal_name: "",
  industry: "",
  company_size: "",
  website: "",
  registration_number: "",
  tax_identifier: "",
  address_line_1: "",
  address_line_2: "",
  city: "",
  state_province: "",
  country: "",
  postal_code: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  offering_ids: [],
  workspace_slug: "",
  tenant_admin_name: "",
  tenant_admin_email: "",
  tenant_admin_password: "",
};

const textOrNull = (value: string): string | null => value.trim() || null;

export const TenantRegistrationPage = () => {
  const navigate = useNavigate();
  const [options, setOptions] = useState<TenantRegistrationOptions | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
    setError,
    watch,
  } = useForm<RegistrationFormValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: emptyDefaults,
  });

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(null);
    void tenantsApi
      .getRegistrationOptions(controller.signal)
      .then((data) => {
        setOptions(data);
        reset({
          ...emptyDefaults,
          status: data.defaults.status,
          subscription_plan_code: data.defaults.subscription_plan_code,
          database_mode: data.defaults.database_mode,
        });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setLoadError(
          error instanceof NetworkError
            ? "The registration service could not be reached."
            : "Registration options could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [reset]);

  const selectedPlanCode = watch("subscription_plan_code");
  const selectedPlan = useMemo(
    () => options?.plans.find((plan) => plan.code === selectedPlanCode),
    [options, selectedPlanCode],
  );

  const onSubmit = async (values: RegistrationFormValues) => {
    if (selectedPlan?.requires_end_date && !values.subscription_end_date) {
      setError("subscription_end_date", {
        message: "An end date is required for this plan",
      });
      return;
    }

    setSubmitError(null);
    const payload: TenantRegistrationPayload = {
      ...values,
      tenant_code: values.tenant_code.toUpperCase(),
      workspace_slug: values.workspace_slug.toLowerCase(),
      subscription_ends_at: values.subscription_end_date
        ? new Date(`${values.subscription_end_date}T23:59:59.000Z`).toISOString()
        : null,
      website: textOrNull(values.website),
      registration_number: textOrNull(values.registration_number),
      tax_identifier: textOrNull(values.tax_identifier),
      address_line_2: textOrNull(values.address_line_2),
    };
    delete (payload as TenantRegistrationPayload & { subscription_end_date?: string })
      .subscription_end_date;

    try {
      const tenant = await tenantsApi.create(payload);
      navigate("/platform/tenants", {
        replace: true,
        state: {
          notice: `${tenant.org_name} was registered successfully.`,
        },
      });
    } catch (error) {
      if (error instanceof ApiError) {
        setSubmitError(error.message);
      } else if (error instanceof NetworkError) {
        setSubmitError("The service could not be reached. Your form has been preserved.");
      } else {
        setSubmitError("Tenant registration could not be completed.");
      }
    }
  };

  if (loadError) {
    return (
      <div className={styles.page}>
        <Alert tone="error" title="Registration unavailable">
          {loadError} Refresh the page to try again.
        </Alert>
      </div>
    );
  }

  if (!options) {
    return (
      <div className={styles.page} role="status">
        <header className={styles.pageHeader}>
          <div>
            <p>Tenant onboarding</p>
            <h1>Register tenant</h1>
            <span>Create the organization, workspace access, and licensed modules together.</span>
          </div>
        </header>
        <div className={styles.loadingCard}>Loading registration settings…</div>
      </div>
    );
  }

  const fieldError = (name: keyof RegistrationFormValues) =>
    errors[name]?.message?.toString();

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <Link to="/platform/tenants">
            <ArrowLeft size={15} aria-hidden="true" />
            All tenants
          </Link>
          <p>Tenant onboarding</p>
          <h1>Register tenant</h1>
          <span>Create the organization, workspace access, and licensed modules together.</span>
        </div>
        <div className={styles.headerActions}>
          <Button
            type="button"
            variant="secondary"
            disabled={isSubmitting}
            onClick={() =>
              reset({
                ...emptyDefaults,
                status: options.defaults.status,
                subscription_plan_code: options.defaults.subscription_plan_code,
                database_mode: options.defaults.database_mode,
              })
            }
          >
            Reset
          </Button>
          <Button
            form="tenant-registration"
            type="submit"
            loading={isSubmitting}
            loadingLabel="Registering tenant…"
          >
            <Save size={16} aria-hidden="true" />
            Register tenant
          </Button>
        </div>
      </header>

      {submitError && (
        <Alert tone="error" title="Registration failed">
          {submitError}
        </Alert>
      )}

      <form
        id="tenant-registration"
        className={styles.form}
        onSubmit={handleSubmit(onSubmit)}
        noValidate
      >
        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <Building2 size={19} aria-hidden="true" />
            <div>
              <h2>Tenant information</h2>
              <p>Commercial identity, subscription, and infrastructure.</p>
            </div>
          </div>
          <div className={styles.fieldGrid}>
            <label>
              <span>Tenant name *</span>
              <input {...register("org_name")} placeholder="Acme Corporation" />
              {fieldError("org_name") && <small>{fieldError("org_name")}</small>}
            </label>
            <label>
              <span>Tenant code *</span>
              <input {...register("tenant_code")} placeholder="ACME" autoCapitalize="characters" />
              {fieldError("tenant_code") && <small>{fieldError("tenant_code")}</small>}
            </label>
            <label>
              <span>Status *</span>
              <select {...register("status")}>
                {options.statuses.map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Plan *</span>
              <select {...register("subscription_plan_code")}>
                {options.plans.map((plan) => (
                  <option key={plan.code} value={plan.code}>{plan.display_name}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Database *</span>
              <select {...register("database_mode")}>
                {options.database_modes.map((mode) => (
                  <option key={mode} value={mode}>{mode}</option>
                ))}
              </select>
            </label>
            {selectedPlan?.requires_end_date && (
              <label>
                <span>Plan end date *</span>
                <input type="date" {...register("subscription_end_date")} />
                {fieldError("subscription_end_date") && (
                  <small>{fieldError("subscription_end_date")}</small>
                )}
              </label>
            )}
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <Building2 size={19} aria-hidden="true" />
            <div>
              <h2>Company details</h2>
              <p>Legal and operational details for the organization.</p>
            </div>
          </div>
          <div className={styles.fieldGrid}>
            <label className={styles.spanTwo}>
              <span>Legal company name *</span>
              <input {...register("legal_name")} />
              {fieldError("legal_name") && <small>{fieldError("legal_name")}</small>}
            </label>
            <label>
              <span>Industry *</span>
              <input {...register("industry")} placeholder="Software services" />
              {fieldError("industry") && <small>{fieldError("industry")}</small>}
            </label>
            <label>
              <span>Company size *</span>
              <input {...register("company_size")} placeholder="51–200 employees" />
              {fieldError("company_size") && <small>{fieldError("company_size")}</small>}
            </label>
            <label className={styles.spanTwo}>
              <span>Website</span>
              <input {...register("website")} type="url" placeholder="https://example.com" />
              {fieldError("website") && <small>{fieldError("website")}</small>}
            </label>
            <label>
              <span>Registration number</span>
              <input {...register("registration_number")} />
            </label>
            <label>
              <span>Tax identifier</span>
              <input {...register("tax_identifier")} />
            </label>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <MapPin size={19} aria-hidden="true" />
            <div>
              <h2>Address information</h2>
              <p>Primary registered business address.</p>
            </div>
          </div>
          <div className={styles.fieldGrid}>
            <label className={styles.spanTwo}>
              <span>Address line 1 *</span>
              <input {...register("address_line_1")} />
              {fieldError("address_line_1") && <small>{fieldError("address_line_1")}</small>}
            </label>
            <label className={styles.spanTwo}>
              <span>Address line 2</span>
              <input {...register("address_line_2")} />
            </label>
            <label>
              <span>City *</span>
              <input {...register("city")} />
              {fieldError("city") && <small>{fieldError("city")}</small>}
            </label>
            <label>
              <span>State / province *</span>
              <input {...register("state_province")} />
              {fieldError("state_province") && <small>{fieldError("state_province")}</small>}
            </label>
            <label>
              <span>Country *</span>
              <input {...register("country")} />
              {fieldError("country") && <small>{fieldError("country")}</small>}
            </label>
            <label>
              <span>Postal / ZIP code *</span>
              <input {...register("postal_code")} />
              {fieldError("postal_code") && <small>{fieldError("postal_code")}</small>}
            </label>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <UserRound size={19} aria-hidden="true" />
            <div>
              <h2>Contact information</h2>
              <p>Primary business contact for the tenant.</p>
            </div>
          </div>
          <div className={styles.fieldGridThree}>
            <label>
              <span>Contact person *</span>
              <input {...register("contact_name")} />
              {fieldError("contact_name") && <small>{fieldError("contact_name")}</small>}
            </label>
            <label>
              <span>Contact email *</span>
              <input type="email" {...register("contact_email")} />
              {fieldError("contact_email") && <small>{fieldError("contact_email")}</small>}
            </label>
            <label>
              <span>Phone number *</span>
              <input type="tel" {...register("contact_phone")} />
              {fieldError("contact_phone") && <small>{fieldError("contact_phone")}</small>}
            </label>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <PackageCheck size={19} aria-hidden="true" />
            <div>
              <h2>Licensed offerings</h2>
              <p>Only selected modules will appear in this tenant’s portal.</p>
            </div>
          </div>
          <div className={styles.offerings}>
            {options.offerings.map((offering) => (
              <label className={styles.offering} key={offering.offering_id}>
                <input
                  type="checkbox"
                  value={offering.offering_id}
                  {...register("offering_ids")}
                />
                <span className={styles.checkbox}><Check size={13} aria-hidden="true" /></span>
                <span>
                  <strong>{offering.display_name}</strong>
                  <small>{offering.description}</small>
                </span>
              </label>
            ))}
          </div>
          {fieldError("offering_ids") && (
            <p className={styles.sectionError} role="alert">{fieldError("offering_ids")}</p>
          )}
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <KeyRound size={19} aria-hidden="true" />
            <div>
              <h2>Workspace access</h2>
              <p>Creates the first Tenant Admin account and login workspace.</p>
            </div>
          </div>
          <div className={styles.fieldGrid}>
            <label>
              <span>Workspace slug *</span>
              <input {...register("workspace_slug")} placeholder="acme-corporation" autoCapitalize="none" />
              {fieldError("workspace_slug") && <small>{fieldError("workspace_slug")}</small>}
            </label>
            <label>
              <span>Tenant Admin name *</span>
              <input {...register("tenant_admin_name")} />
              {fieldError("tenant_admin_name") && <small>{fieldError("tenant_admin_name")}</small>}
            </label>
            <label>
              <span>Login email *</span>
              <input type="email" {...register("tenant_admin_email")} autoComplete="off" />
              {fieldError("tenant_admin_email") && <small>{fieldError("tenant_admin_email")}</small>}
            </label>
            <label>
              <span>Temporary password *</span>
              <span className={styles.passwordInput}>
                <input
                  type={showPassword ? "text" : "password"}
                  {...register("tenant_admin_password")}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
              {fieldError("tenant_admin_password") ? (
                <small>{fieldError("tenant_admin_password")}</small>
              ) : (
                <em>At least 12 characters with upper, lower, number, and symbol.</em>
              )}
            </label>
          </div>
        </section>

        <div className={styles.mobileActions}>
          <Button type="submit" fullWidth loading={isSubmitting} loadingLabel="Registering tenant…">
            Register tenant
          </Button>
        </div>
      </form>
    </div>
  );
};
