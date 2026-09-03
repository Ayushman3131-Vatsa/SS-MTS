/** Display helpers for user names and roles across admin screens. */

const AVATAR_PALETTE = [
  { background: "#eef2ff", border: "#c7d2fe", color: "#3730a3" },
  { background: "#ecfeff", border: "#a5f3fc", color: "#155e75" },
  { background: "#ecfdf5", border: "#a7f3d0", color: "#166534" },
  { background: "#fff7ed", border: "#fed7aa", color: "#9a3412" },
  { background: "#fdf2f8", border: "#fbcfe8", color: "#9d174d" },
  { background: "#f5f3ff", border: "#ddd6fe", color: "#5b21b6" },
] as const;

export type AvatarPalette = (typeof AVATAR_PALETTE)[number];

export function avatarPaletteForName(name: string): AvatarPalette {
  const normalized = name.trim().toLowerCase();
  let hash = 0;
  for (let index = 0; index < normalized.length; index += 1) {
    hash = (hash + normalized.charCodeAt(index) * (index + 1)) % AVATAR_PALETTE.length;
  }
  return AVATAR_PALETTE[hash] ?? AVATAR_PALETTE[0];
}

export function formatUserInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0]?.[0] ?? ""}${parts[1]?.[0] ?? ""}`.toUpperCase();
  }
  return (parts[0]?.slice(0, 2) ?? "U").toUpperCase();
}

const ACRONYMS = new Set([
  "IT",
  "HR",
  "QA",
  "UI",
  "UX",
  "VP",
  "CEO",
  "CTO",
  "CFO",
  "COO",
  "ERP",
  "CRM",
  "AI",
  "ML",
  "DB",
  "ID",
  "SYS",
]);

/** Human-readable role title for headers (never show raw codes like PLATFORM_ADMIN). */
export function formatRoleLabel(role: string): string {
  const trimmed = role.trim();
  if (!trimmed) {
    return "User";
  }

  // Only transform raw SCREAMING_SNAKE_CASE codes (e.g., PLATFORM_ADMIN, IT_ADMIN)
  if (/^[A-Z0-9_]+$/.test(trimmed) && trimmed.includes("_")) {
    return trimmed
      .split("_")
      .map((part) =>
        ACRONYMS.has(part)
          ? part
          : part.charAt(0).toUpperCase() + part.slice(1).toLowerCase(),
      )
      .join(" ");
  }

  // Preserve user-defined role names exactly as created
  return trimmed;
}
