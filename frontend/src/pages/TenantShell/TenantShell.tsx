import {
  BookOpen,
  BriefcaseBusiness,
  CalendarDays,
  ChartNoAxesCombined,
  ChartSpline,
  ClipboardCheck,
  Clock,
  Headphones,
  LayoutDashboard,
  LogOut,
  Menu,
  Monitor,
  ReceiptText,
  SlidersHorizontal,
  UserRound,
  Users,
  UserSearch,
  WalletCards,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { getPrincipalHome } from "../../entities/session/model/routing";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { BrandMark } from "../../shared/ui/BrandMark/BrandMark";
import { Button } from "../../shared/ui/Button/Button";
import styles from "./TenantShell.module.css";

const iconByKey: Record<string, LucideIcon> = {
  "book-open": BookOpen,
  "briefcase-business": BriefcaseBusiness,
  "calendar-days": CalendarDays,
  "chart-no-axes-combined": ChartNoAxesCombined,
  "chart-spline": ChartSpline,
  "clipboard-check": ClipboardCheck,
  clock: Clock,
  headphones: Headphones,
  monitor: Monitor,
  "receipt-text": ReceiptText,
  "user-round": UserRound,
  users: Users,
  "user-search": UserSearch,
  "wallet-cards": WalletCards,
};

export const TenantShell = () => {
  const { logout, principal } = useSession();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => setDrawerOpen(false), [location.pathname]);

  if (!principal || principal.principal_type !== "tenant_user") {
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
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <button
            type="button"
            aria-label="Open workspace navigation"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={19} />
          </button>
          <BrandMark />
        </div>
        <div className={styles.identity}>
          <span>
            <strong>{principal.name}</strong>
            <small>{principal.role}</small>
          </span>
          <i aria-hidden="true">{principal.name.slice(0, 1).toUpperCase()}</i>
          <Button
            type="button"
            variant="ghost"
            loading={isLoggingOut}
            loadingLabel="Signing out…"
            onClick={handleLogout}
          >
            {!isLoggingOut && <LogOut size={16} aria-hidden="true" />}
            {!isLoggingOut && "Sign out"}
          </Button>
        </div>
      </header>

      {drawerOpen && (
        <button
          className={styles.backdrop}
          type="button"
          aria-label="Close workspace navigation"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      <aside className={`${styles.sidebar} ${drawerOpen ? styles.open : ""}`}>
        <div className={styles.workspace}>
          <span><Users size={17} /></span>
          <div>
            <strong>{principal.tenant.org_name}</strong>
            <small>{principal.tenant.workspace_slug}</small>
          </div>
          <button type="button" aria-label="Close navigation" onClick={() => setDrawerOpen(false)}>
            <X size={19} />
          </button>
        </div>
        <nav>
          <p>Workspace</p>
          <NavLink
            end
            to={getPrincipalHome(principal)}
            className={({ isActive }) => isActive ? styles.active : ""}
          >
            <LayoutDashboard size={17} />
            <span>{principal.role === "Employee" ? "My work" : "Overview"}</span>
          </NavLink>
          {principal.role === "Tenant Admin" && (
            <NavLink
              to="/app/configurations"
              className={({ isActive }) => isActive ? styles.active : ""}
            >
              <SlidersHorizontal size={17} />
              <span>Configurations</span>
            </NavLink>
          )}
          {principal.tenant.offerings.length > 0 && <p>Licensed offerings</p>}
          {principal.tenant.offerings.map((offering) => {
            const Icon = iconByKey[offering.icon_key] ?? BriefcaseBusiness;
            return (
              <NavLink
                key={offering.offering_id}
                to={`/app/modules/${offering.route_slug}`}
                className={({ isActive }) => isActive ? styles.active : ""}
                title={offering.display_name}
              >
                <Icon size={17} />
                <span>{offering.display_name}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className={styles.license}>
          <ClipboardCheck size={16} />
          <span>
            <strong>{principal.tenant.offerings.length} licensed modules</strong>
            <small>Managed by your platform provider</small>
          </span>
        </div>
      </aside>

      <main className={styles.main}>
        {logoutError && <div className={styles.error} role="alert">{logoutError}</div>}
        <Outlet />
      </main>
    </div>
  );
};
