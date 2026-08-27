import { avatarPaletteForName, formatUserInitials } from "../../utils/user-display";
import styles from "./UserAvatar.module.css";

type UserAvatarSize = "sm" | "md" | "lg";

interface UserAvatarProps {
  name: string;
  size?: UserAvatarSize;
  className?: string;
}

export const UserAvatar = ({ name, size = "md", className }: UserAvatarProps) => {
  const palette = avatarPaletteForName(name);

  return (
    <span
      className={[styles.avatar, styles[size], className].filter(Boolean).join(" ")}
      style={{
        backgroundColor: palette.background,
        borderColor: palette.border,
        color: palette.color,
      }}
      aria-hidden="true"
    >
      <span className={styles.initials}>{formatUserInitials(name)}</span>
    </span>
  );
};
