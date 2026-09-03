import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  Building2,
  Check,
  MapPin,
  PackageCheck,
  Plus,
  Save,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type {
  TenantRecord,
  TenantRegistrationOptions,
  TenantRegistrationPayload,
} from "../../features/tenant-management/model/tenants";
import { TenantAdminCredentialsPanel } from "../../features/tenant-management/ui/TenantAdminCredentialsPanel/TenantAdminCredentialsPanel";
import { canModifyPage } from "../../entities/session/model/page-access";
import { useOptionalSession } from "../../entities/session/model/session-context";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { ApiError, InvalidApiResponseError, NetworkError } from "../../shared/api/errors";
import styles from "./TenantRegistrationPage.module.css";

const optionalUrl = z
  .string()
  .trim()
  .refine(
    (value) => value.length === 0 || /^https?:\/\/.+/i.test(value),
    "Enter a full URL beginning with http:// or https://",
  );

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
  tax_registration_number: z.string().trim().max(100),
  pan_number: z
    .string()
    .trim()
    .min(1, "PAN number is required")
    .regex(
      /^[A-Z]{5}[0-9]{4}[A-Z]$/i,
      "Enter a valid PAN (five letters, four digits, and one letter)",
    ),
  address_line_1: z.string().trim().min(1, "Address is required").max(255),
  address_line_2: z.string().trim().max(255),
  city: z.string().trim().min(1, "City is required").max(100),
  state_province: z.string().trim().min(1, "State or province is required").max(100),
  country: z.string().trim().min(1, "Country is required").max(100),
  postal_code: z.string().trim().min(1, "Postal code is required").max(30),
  contact_name: z.string().trim().min(1, "Contact name is required").max(255),
  contact_designation: z
    .string()
    .trim()
    .min(1, "Designation is required")
    .max(100),
  contact_email: z.string().trim().email("Enter a valid contact email"),
  contact_phone: z
    .string()
    .trim()
    .min(5, "Phone number is required")
    .max(40)
    .regex(/^[0-9+().\-\s]+$/, "Enter a valid phone number"),
  alternate_contact_name: z.string().trim().max(255),
  alternate_contact_designation: z.string().trim().max(100),
  alternate_contact_email: z
    .string()
    .trim()
    .refine(
      (value) => value.length === 0 || z.string().email().safeParse(value).success,
      "Enter a valid alternate contact email",
    ),
  alternate_contact_phone: z
    .string()
    .trim()
    .max(40)
    .refine(
      (value) => value.length === 0 || (value.length >= 5 && /^[0-9+().\-\s]+$/.test(value)),
      "Enter a valid alternate contact phone number",
    ),
  offering_ids: z.preprocess(
    (value) => (Array.isArray(value) ? value : value ? [value] : []),
    z.array(z.string().uuid()).min(1, "Select at least one offering"),
  ),
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
  tax_registration_number: "",
  pan_number: "",
  address_line_1: "",
  address_line_2: "",
  city: "",
  state_province: "",
  country: "",
  postal_code: "",
  contact_name: "",
  contact_designation: "",
  contact_email: "",
  contact_phone: "",
  alternate_contact_name: "",
  alternate_contact_designation: "",
  alternate_contact_email: "",
  alternate_contact_phone: "",
  offering_ids: [],
};

const asOfferingIds = (value: string[] | string | undefined): string[] => {
  if (Array.isArray(value)) {
    return value.filter((item) => typeof item === "string" && item.length > 0);
  }
  return typeof value === "string" && value.length > 0 ? [value] : [];
};

const textOrNull = (value: string): string | null => value.trim() || null;

export const TenantRegistrationPage = () => {
  const navigate = useNavigate();
  const principal = useOptionalSession()?.principal;
  const canModify = canModifyPage(principal, "/platform/tenants/register");
  const [options, setOptions] = useState<TenantRegistrationOptions | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdTenant, setCreatedTenant] = useState<TenantRecord | null>(null);
  const [showAlternateContact, setShowAlternateContact] = useState(false);
  const {
    formState: { errors, isSubmitting },
    clearErrors,
    handleSubmit,
    register,
    reset,
    setError,
    setValue,
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
  const selectedOfferingIds = asOfferingIds(watch("offering_ids"));
  const selectedOfferings = useMemo(
    () =>
      options?.offerings.filter((offering) =>
        selectedOfferingIds.includes(offering.offering_id),
      ) ?? [],
    [options, selectedOfferingIds],
  );

  const resetRegistration = () => {
    if (!options) return;
    reset({
      ...emptyDefaults,
      status: options.defaults.status,
      subscription_plan_code: options.defaults.subscription_plan_code,
      database_mode: options.defaults.database_mode,
    });
    setShowAlternateContact(false);
    setSubmitError(null);
  };

  const onSubmit = async (values: RegistrationFormValues) => {
    if (!canModify) {
      setSubmitError("You have view-only access. Registering new tenants requires Modify permission.");
      return;
    }
    if (selectedPlan?.requires_end_date && !values.subscription_end_date) {
      setError("subscription_end_date", {
        message: "An end date is required for this plan",
      });
      return;
    }

    if (showAlternateContact) {
      const alternateContactFields = [
        ["alternate_contact_name", values.alternate_contact_name],
        ["alternate_contact_designation", values.alternate_contact_designation],
        ["alternate_contact_email", values.alternate_contact_email],
        ["alternate_contact_phone", values.alternate_contact_phone],
      ] as const;
      const missingFields = alternateContactFields.filter(([, value]) => !value.trim());
      if (missingFields.length > 0) {
        for (const [field] of missingFields) {
          setError(field, {
            type: "required",
            message: "Complete all alternate contact fields",
          });
        }
        return;
      }
    }

    setSubmitError(null);
    const payload: TenantRegistrationPayload = {
      ...values,
      offering_ids: asOfferingIds(values.offering_ids),
      tenant_code: values.tenant_code.toUpperCase(),
      subscription_ends_at: values.subscription_end_date
        ? new Date(`${values.subscription_end_date}T23:59:59.000Z`).toISOString()
        : null,
      website: textOrNull(values.website),
      tax_registration_number: textOrNull(values.tax_registration_number),
      pan_number: values.pan_number.toUpperCase(),
      address_line_2: textOrNull(values.address_line_2),
      alternate_contact_name: textOrNull(values.alternate_contact_name),
      alternate_contact_designation: textOrNull(values.alternate_contact_designation),
      alternate_contact_email: textOrNull(values.alternate_contact_email),
      alternate_contact_phone: textOrNull(values.alternate_contact_phone),
    };
    delete (payload as TenantRegistrationPayload & { subscription_end_date?: string })
      .subscription_end_date;

    try {
      const tenant = await tenantsApi.create({ ...payload, status: "ACTIVE" });
      setCreatedTenant(tenant);
    } catch (error) {
      if (error instanceof ApiError) {
        setSubmitError(error.message);
      } else if (error instanceof NetworkError) {
        setSubmitError("The service could not be reached. Your form has been preserved.");
      } else if (error instanceof InvalidApiResponseError) {
        setSubmitError("The tenant may have been created, but the response could not be read. Check All Tenants.");
      } else {
        setSubmitError("Tenant registration could not be completed.");
      }
    }
  };

  if (createdTenant) {
    const access = createdTenant.first_access;
    const smartskale = access?.smartskale_access;
    return (
      <div className={styles.page}>
        <header className={styles.pageHeader}>
          <div>
            <p>Tenant onboarding</p>
            <h1>{createdTenant.org_name} is ready</h1>
            <span>Share the admin credentials securely. Temporary passwords are shown once.</span>
          </div>
        </header>
        <section className={styles.credentialsCard}>
          {access?.login_path && (
            <p className={styles.credentialsEyebrow}>Sign-in URL: {access.login_path}</p>
          )}
          <p className={styles.credentialsEyebrow}>Contact admin</p>
          {access ? (
            <TenantAdminCredentialsPanel access={access} />
          ) : (
            <Alert tone="warning" title="Credentials unavailable">
              The tenant was created, but admin credentials were not returned. Open the tenant record to reset access if needed.
            </Alert>
          )}
          {smartskale && (
            <>
              <p className={styles.credentialsEyebrow}>Smartskale Admin</p>
              <TenantAdminCredentialsPanel access={smartskale} />
            </>
          )}
          <div className={styles.credentialsActions}>
            <Button type="button" variant="secondary" onClick={() => navigate(`/platform/tenants/${createdTenant.tenant_id}`)}>
              View tenant
            </Button>
            <Button
              type="button"
              onClick={() => {
                setCreatedTenant(null);
                setSubmitError(null);
              }}
            >
              Register another tenant
            </Button>
          </div>
        </section>
      </div>
    );
  }

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
            <span>Create the organization profile and licensed modules together.</span>
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
          <span>Create the organization profile and licensed modules together.</span>
        </div>
        <div className={styles.headerActions}>
          <Button
            type="button"
            variant="secondary"
            disabled={isSubmitting}
            onClick={resetRegistration}
          >
            Reset
          </Button>
          <Button
            form="tenant-registration"
            type="submit"
            disabled={isSubmitting || !canModify}
            loading={isSubmitting}
            loadingLabel="Registering tenant…"
          >
            <Save size={16} aria-hidden="true" />
            Register tenant
          </Button>
        </div>
      </header>

      {!canModify && (
        <Alert tone="info" title="Read-only mode">
          You have view-only permissions for this page. Registering new tenants is disabled.
        </Alert>
      )}

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
              <span>Tax Registration number</span>
              <input {...register("tax_registration_number")} />
            </label>
            <label>
              <span>PAN number *</span>
              <input
                {...register("pan_number")}
                required
                maxLength={10}
                autoCapitalize="characters"
              />
              {fieldError("pan_number") && <small>{fieldError("pan_number")}</small>}
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
          <div className={styles.contactHeader}>
            <div className={styles.sectionHeading}>
              <UserRound size={19} aria-hidden="true" />
              <div>
                <h2>Contact information</h2>
                <p>Primary business contact for the tenant.</p>
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              className={styles.contactAction}
              onClick={() => {
                if (showAlternateContact) {
                  setValue("alternate_contact_name", "");
                  setValue("alternate_contact_designation", "");
                  setValue("alternate_contact_email", "");
                  setValue("alternate_contact_phone", "");
                  clearErrors([
                    "alternate_contact_name",
                    "alternate_contact_designation",
                    "alternate_contact_email",
                    "alternate_contact_phone",
                  ]);
                }
                setShowAlternateContact((current) => !current);
              }}
              aria-expanded={showAlternateContact}
            >
              {showAlternateContact ? <X size={14} aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />}
              {showAlternateContact ? "Remove alternate" : "Add alternate contact"}
            </Button>
          </div>
          <div className={styles.contactBlock}>
            <div className={styles.contactBlockHeading}>
              <strong>Primary contact</strong>
              <span>Required</span>
            </div>
            <div className={styles.fieldGridFour}>
              <label>
                <span>Contact person *</span>
                <input {...register("contact_name")} />
                {fieldError("contact_name") && <small>{fieldError("contact_name")}</small>}
              </label>
              <label>
                <span>Designation *</span>
                <input {...register("contact_designation")} required maxLength={100} />
                {fieldError("contact_designation") && (
                  <small>{fieldError("contact_designation")}</small>
                )}
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
          </div>
          {showAlternateContact && (
            <div className={styles.contactBlock}>
              <div className={styles.contactBlockHeading}>
                <strong>Alternate contact</strong>
                <span>All fields required</span>
              </div>
              <div className={styles.fieldGridFour}>
                <label>
                  <span>Contact person *</span>
                  <input {...register("alternate_contact_name")} />
                  {fieldError("alternate_contact_name") && <small>{fieldError("alternate_contact_name")}</small>}
                </label>
                <label>
                  <span>Designation *</span>
                  <input
                    {...register("alternate_contact_designation")}
                    required
                    maxLength={100}
                  />
                  {fieldError("alternate_contact_designation") && (
                    <small>{fieldError("alternate_contact_designation")}</small>
                  )}
                </label>
                <label>
                  <span>Contact email *</span>
                  <input type="email" {...register("alternate_contact_email")} />
                  {fieldError("alternate_contact_email") && <small>{fieldError("alternate_contact_email")}</small>}
                </label>
                <label>
                  <span>Phone number *</span>
                  <input type="tel" {...register("alternate_contact_phone")} />
                  {fieldError("alternate_contact_phone") && <small>{fieldError("alternate_contact_phone")}</small>}
                </label>
              </div>
            </div>
          )}
        </section>

        <section className={`${styles.section} ${styles.offeringsSection}`}>
          <div className={styles.offeringToolbar}>
            <div className={styles.sectionHeading}>
              <PackageCheck size={19} aria-hidden="true" />
              <div>
                <h2>Licensed offerings</h2>
                <p>Select the products this tenant can access.</p>
              </div>
            </div>
            <span className={styles.selectionCount} aria-live="polite">
              {selectedOfferings.length} selected
            </span>
          </div>
          <div className={styles.offeringCatalog}>
            {options.offerings.map((offering) => {
              const isSelected = selectedOfferingIds.includes(offering.offering_id);
              return (
                <label
                  className={`${styles.offeringCard} ${isSelected ? styles.selectedOffering : ""}`}
                  key={offering.offering_id}
                >
                  <input
                    type="checkbox"
                    value={offering.offering_id}
                    aria-label={`Select ${offering.display_name}`}
                    checked={isSelected}
                    onChange={(event) => {
                      const next = event.target.checked
                        ? [...selectedOfferingIds, offering.offering_id]
                        : selectedOfferingIds.filter((id) => id !== offering.offering_id);
                      setValue("offering_ids", next, { shouldDirty: true, shouldValidate: true });
                    }}
                  />
                  <span className={styles.checkbox}>
                    <Check size={13} aria-hidden="true" />
                  </span>
                  <span className={styles.offeringCopy}>
                    <strong>{offering.display_name}</strong>
                    <small>{offering.description}</small>
                  </span>
                  {isSelected && <span className={styles.selectedMark}>Selected</span>}
                </label>
              );
            })}
          </div>
          {fieldError("offering_ids") && (
            <p className={styles.sectionError} role="alert">{fieldError("offering_ids")}</p>
          )}
        </section>

        <div className={styles.mobileActions}>
          <Button type="submit" fullWidth disabled={isSubmitting || !canModify} loading={isSubmitting} loadingLabel="Registering tenant…">
            Register tenant
          </Button>
        </div>
      </form>
    </div>
  );
};
