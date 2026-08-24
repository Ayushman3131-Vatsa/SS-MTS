import { z } from "zod";

const identifierSchema = z
  .string()
  .trim()
  .min(1, "Enter your work email or username.")
  .max(254, "Must be 254 characters or fewer.")
  .refine((value) => {
    if (value.includes("@")) {
      return z.string().email().safeParse(value).success;
    }
    return /^[A-Za-z][A-Za-z0-9._-]{2,49}$/.test(value);
  }, "Enter a valid work email or username.");

const passwordSchema = z
  .string()
  .min(1, "Enter your password.")
  .max(128, "Password must be 128 characters or fewer.");

export const tenantLoginSchema = z.object({
  email: identifierSchema,
  password: passwordSchema,
});

export const platformLoginSchema = z.object({
  email: identifierSchema,
  password: passwordSchema,
});

export type TenantLoginValues = z.infer<typeof tenantLoginSchema>;
export type PlatformLoginValues = z.infer<typeof platformLoginSchema>;
