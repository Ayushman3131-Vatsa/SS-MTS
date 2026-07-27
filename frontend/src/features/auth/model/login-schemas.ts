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
  workspaceSlug: z
    .string()
    .trim()
    .min(3, "Workspace must be at least 3 characters.")
    .max(63, "Workspace must be 63 characters or fewer.")
    .regex(
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      "Use lowercase letters, numbers, and single hyphens only.",
    ),
  email: emailSchema,
  password: passwordSchema,
  rememberWorkspace: z.boolean(),
});

export const platformLoginSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
});

export type TenantLoginValues = z.infer<typeof tenantLoginSchema>;
export type PlatformLoginValues = z.infer<typeof platformLoginSchema>;
