import { Building2, ChevronDown, FileStack, KeyRound, LayoutDashboard, LogOut, Menu, Package, PlusCircle, ShieldCheck, UsersRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { canAccessPage } from "../../entities/session/model/page-access";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { BrandMark } from "../../shared/ui/BrandMark/BrandMark";
import { Button } from "../../shared/ui/Button/Button";
import { UserAvatar } from "../../shared/ui/UserAvatar/UserAvatar";
import { formatRoleLabel } from "../../shared/utils/user-display";
import styles from "./PlatformShell.module.css";

const primaryNavigation = [
  { end: true, icon: LayoutDashboard, label: "Dashboard", to: "/platform" },
  { end: true, icon: Building2, label: "All Tenants", to: "/platform/tenants" },
  { end: true, icon: PlusCircle, label: "Register Tenant", to: "/platform/tenants/register" },
] as const;

const catalogNavigation = [
  { end: true, icon: Package, label: "Offerings", to: "/platform/offerings" },
  { end: false, icon: FileStack, label: "Default Templates", to: "/platform/default-templates" },
] as const;

const accessNavigation = [
  { icon: UsersRound, label: "Users", to: "/platform/users" },
  { icon: KeyRound, label: "Roles & permissions", to: "/platform/roles" },
] as const;

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export const PlatformShell = () => {
  const { logout, principal } = useSession();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const accessRouteActive = location.pathname.startsWith("/platform/users") || location.pathname.startsWith("/platform/roles");
  const [accessExpanded, setAccessExpanded] = useState(accessRouteActive);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (accessRouteActive) {
      setAccessExpanded(true);
    }
  }, [accessRouteActive]);

  useEffect(() => {
    if (!drawerOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const menuButton = menuButtonRef.current;
    document.body.style.overflow = "hidden";
    const focusableElements = Array.from(
      drawerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
    );
    const mobileViewport = window.matchMedia?.("(max-width: 44rem)");
    const closeAtDesktopBreakpoint = (event: MediaQueryListEvent) => {
      if (!event.matches) {
        setDrawerOpen(false);
      }
    };
    mobileViewport?.addEventListener("change", closeAtDesktopBreakpoint);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setDrawerOpen(false);
        return;
      }

      if (event.key !== "Tab" || focusableElements.length === 0) {
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements.at(-1);
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement?.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      mobileViewport?.removeEventListener("change", closeAtDesktopBreakpoint);
      if (menuButton?.isConnected) {
        menuButton?.focus();
      } else if (previouslyFocused?.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [drawerOpen]);

  if (!principal || principal.principal_type !== "platform_admin") {
    return null;
  }

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
    } catch (error) {
      setLogoutError(getLoginErrorContent(error).message);
      setIsLoggingOut(false);
    }
  };

  return (
    <div className={styles.shell}>
      <header
        className={styles.topbar}
        aria-hidden={drawerOpen || undefined}
        inert={drawerOpen || undefined}
      >
        <div className={styles.brandGroup}>
          <button
            ref={menuButtonRef}
            className={styles.menuButton}
            type="button"
            aria-controls="platform-navigation"
            aria-expanded={drawerOpen}
            aria-label="Open platform navigation"
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={20} aria-hidden="true" />
          </button>
          <BrandMark />
        </div>

        <div className={styles.identity}>
          <div className={styles.userCard}>
            <UserAvatar name={principal.name} size="md" />
            <div className={styles.identityText}>
              <strong>{principal.name}</strong>
              <span className={styles.roleLine}>{formatRoleLabel(principal.role)}</span>
            </div>
          </div>
          <Button
            className={styles.signOutButton}
            variant="ghost"
            onClick={handleLogout}
            loading={isLoggingOut}
            loadingLabel="Signing out…"
            aria-label="Sign out"
          >
            {!isLoggingOut && <LogOut size={17} aria-hidden="true" />}
            {!isLoggingOut && <span className={styles.signOutLabel}>Sign out</span>}
          </Button>
        </div>
      </header>

      {drawerOpen && (
        <div
          className={styles.backdrop}
          aria-hidden="true"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      <aside
        ref={drawerRef}
        id="platform-navigation"
        className={`${styles.sidebar} ${drawerOpen ? styles.drawerOpen : ""}`}
        aria-label="Platform navigation"
        aria-modal={drawerOpen || undefined}
        role={drawerOpen ? "dialog" : undefined}
      >
        <div className={styles.sidebarHeader}>
          <div>
            <span className={styles.sidebarIcon} aria-hidden="true">
              <ShieldCheck size={17} />
            </span>
            <div>
              <strong>Platform Console</strong>
              <span>Administration</span>
            </div>
          </div>
          {drawerOpen && (
            <button
              autoFocus
              className={styles.closeButton}
              type="button"
              aria-label="Close platform navigation"
              onClick={() => setDrawerOpen(false)}
            >
              <X size={20} aria-hidden="true" />
            </button>
          )}
        </div>

        <nav aria-label="Platform navigation">
          <span className={styles.navLabel}>Workspace</span>
          {primaryNavigation
            .filter((item) => canAccessPage(principal, item.to))
            .map(({ end, icon: Icon, label, to }) => (
              <NavLink
                className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ""}`}
                end={end}
                key={to}
                to={to}
                title={label}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            ))}
          {canAccessPage(principal, "/platform/users") || canAccessPage(principal, "/platform/roles") ? (
            <div className={styles.navGroup}>
              <button
                type="button"
                className={`${styles.groupToggle} ${accessRouteActive ? styles.groupActive : ""}`}
                aria-expanded={accessExpanded}
                aria-controls="user-access-management-navigation"
                onClick={() => setAccessExpanded((expanded) => !expanded)}
              >
                <ShieldCheck size={18} aria-hidden="true" />
                <span>User Access Management</span>
                <ChevronDown className={accessExpanded ? styles.chevronOpen : ""} size={15} aria-hidden="true" />
              </button>
              {accessExpanded && (
                <div id="user-access-management-navigation" className={styles.subnav}>
                  {accessNavigation
                    .filter((item) => canAccessPage(principal, item.to))
                    .map(({ icon: Icon, label, to }) => (
                      <NavLink
                        className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ""}`}
                        key={to}
                        to={to}
                        title={label}
                      >
                        <Icon size={17} aria-hidden="true" />
                        <span>{label}</span>
                      </NavLink>
                    ))}
                </div>
              )}
            </div>
          ) : null}
          {catalogNavigation
            .filter((item) => canAccessPage(principal, item.to))
            .map(({ end, icon: Icon, label, to }) => (
              <NavLink
                className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ""}`}
                end={end}
                key={to}
                to={to}
                title={label}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <ShieldCheck size={16} aria-hidden="true" />
          <div>
            <strong>Secure console</strong>
            <span>{formatRoleLabel(principal.role)} · Platform access</span>
          </div>
        </div>
      </aside>

      <main
        className={styles.main}
        aria-hidden={drawerOpen || undefined}
        inert={drawerOpen || undefined}
      >
        {logoutError && (
          <div className={styles.logoutError} role="alert">
            <strong>Could not sign out.</strong> {logoutError}
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
};
