import { z } from "zod";

const emailSchema = z
  .string()
  .trim()
  .min(1, "Enter your work email.")
  .max(254, "Email must be 254 characters or fewer.")
  .email("Enter a valid email address.");

const passwordSchema = z
  .string()
  .min(1, "Enter your password.")
  .max(128, "Password must be 128 characters or fewer.");

export const tenantLoginSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
});

export const platformLoginSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
});

export type TenantLoginValues = z.infer<typeof tenantLoginSchema>;
export type PlatformLoginValues = z.infer<typeof platformLoginSchema>;
