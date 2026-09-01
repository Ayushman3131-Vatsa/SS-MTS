import {
  BookOpen,
  BriefcaseBusiness,
  CalendarDays,
  ChevronDown,
  ChartNoAxesCombined,
  ChartSpline,
  ClipboardCheck,
  Clock,
  Headphones,
  KeyRound,
  LayoutDashboard,
  ListChecks,
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
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { getPrincipalHome, getTenantLoginPath, useTenantAppPath } from "../../entities/session/model/routing";
import { canAccessOffering, canAccessPage } from "../../entities/session/model/page-access";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { BrandMark } from "../../shared/ui/BrandMark/BrandMark";
import { Button } from "../../shared/ui/Button/Button";
import { UserAvatar } from "../../shared/ui/UserAvatar/UserAvatar";
import { formatRoleLabel } from "../../shared/utils/user-display";
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
  const { clearNotice, logout, notice, principal } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const appPath = useTenantAppPath();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const taskRouteActive = location.pathname.includes("/app/task-management");
  const accessRouteActive = location.pathname.includes("/app/users") || location.pathname.includes("/app/roles");
  const taskTenantId = principal?.principal_type === "tenant_user" ? principal.tenant.tenant_id : "unknown";
  const hasTaskOffering = canAccessOffering(principal, "TASK_MANAGEMENT");
  const taskExpansionKey = `task-management-navigation:${taskTenantId}`;
  const [taskExpanded, setTaskExpanded] = useState(() => taskRouteActive);
  const [accessExpanded, setAccessExpanded] = useState(accessRouteActive);

  useEffect(() => setDrawerOpen(false), [location.pathname]);

  useEffect(() => {
    if (accessRouteActive) {
      setAccessExpanded(true);
    }
  }, [accessRouteActive]);

  useEffect(() => {
    if (taskRouteActive) {
      setTaskExpanded(true);
      return;
    }
    setTaskExpanded(hasTaskOffering && window.localStorage.getItem(taskExpansionKey) === "expanded");
  }, [hasTaskOffering, taskExpansionKey, taskRouteActive]);

  useEffect(() => {
    if (taskTenantId !== "unknown" && hasTaskOffering) {
      window.localStorage.setItem(taskExpansionKey, taskExpanded ? "expanded" : "collapsed");
    }
  }, [hasTaskOffering, taskExpanded, taskExpansionKey, taskTenantId]);

  if (!principal || principal.principal_type !== "tenant_user") {
    return null;
  }

  const taskOffering = principal.tenant.offerings.find(
    (offering) => offering.code === "TASK_MANAGEMENT",
  );
  const showOverview = canAccessPage(principal, "/app/overview");
  const showUsers = canAccessPage(principal, "/app/users");
  const showRoles = canAccessPage(principal, "/app/roles");
  const showAccessManagement = showUsers || showRoles;
  const showConfigurations = canAccessPage(principal, "/app/configurations");
  const showTaskOverview = canAccessPage(principal, "/app/task-management");
  const showTaskProjects = canAccessPage(principal, "/app/task-management/projects");
  const showTaskMyWork = canAccessPage(principal, "/app/task-management/my-work");
  const showTaskAll = canAccessPage(principal, "/app/task-management/tasks");
  const visibleOfferings = principal.tenant.offerings.filter((offering) =>
    canAccessOffering(principal, offering.code),
  );

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setLogoutError(null);
    try {
      const loginPath = getTenantLoginPath(principal);
      await logout();
      navigate(loginPath, { replace: true });
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
          <UserAvatar name={principal.name} size="md" />
          <span className={styles.identityText}>
            <strong>{principal.name}</strong>
            <small>{formatRoleLabel(principal.role)}</small>
          </span>
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
            <small>{principal.tenant.tenant_code}</small>
          </div>
          <button type="button" aria-label="Close navigation" onClick={() => setDrawerOpen(false)}>
            <X size={19} />
          </button>
        </div>
        <nav>
          <p>Workspace</p>
          {showOverview && (
            <NavLink
              end
              to={getPrincipalHome(principal)}
              className={({ isActive }) => isActive ? styles.active : ""}
            >
              <LayoutDashboard size={17} />
              <span>Overview</span>
            </NavLink>
          )}
          {showAccessManagement && (
            <div className={styles.navGroup}>
              <button
                type="button"
                className={`${styles.groupToggle} ${accessRouteActive ? styles.groupActive : ""}`}
                aria-expanded={accessExpanded}
                aria-controls="user-access-management-navigation"
                onClick={() => setAccessExpanded((expanded) => !expanded)}
              >
                <Users size={17} />
                <span>User Access Management</span>
                <ChevronDown className={accessExpanded ? styles.chevronOpen : ""} size={15} />
              </button>
              {accessExpanded && (
                <div id="user-access-management-navigation" className={styles.subnav}>
                  {showUsers && (
                    <NavLink
                      to={appPath("/app/users")}
                      className={({ isActive }) => isActive ? styles.active : ""}
                    >
                      <Users size={15} />
                      <span>Users</span>
                    </NavLink>
                  )}
                  {showRoles && (
                    <NavLink
                      to={appPath("/app/roles")}
                      className={({ isActive }) => isActive ? styles.active : ""}
                    >
                      <KeyRound size={15} />
                      <span>Roles & permissions</span>
                    </NavLink>
                  )}
                </div>
              )}
            </div>
          )}
          {showConfigurations && (
            <NavLink
              to={appPath("/app/configurations")}
              className={({ isActive }) => isActive ? styles.active : ""}
            >
              <SlidersHorizontal size={17} />
              <span>Configurations</span>
            </NavLink>
          )}
          {visibleOfferings.length > 0 && <p>Licensed offerings</p>}
          {hasTaskOffering && taskOffering && (
            <div className={styles.navGroup}>
              <button
                type="button"
                className={`${styles.groupToggle} ${taskRouteActive ? styles.groupActive : ""}`}
                aria-expanded={taskExpanded}
                aria-controls="task-management-navigation"
                onClick={() => setTaskExpanded((expanded) => !expanded)}
              >
                <ClipboardCheck size={17} />
                <span>{taskOffering.display_name}</span>
                <ChevronDown className={taskExpanded ? styles.chevronOpen : ""} size={15} />
              </button>
              {taskExpanded && (
                <div id="task-management-navigation" className={styles.subnav}>
                  {showTaskOverview && (
                    <NavLink end to={appPath("/app/task-management")} className={({ isActive }) => isActive ? styles.active : ""}>
                      <LayoutDashboard size={15} /><span>Overview</span>
                    </NavLink>
                  )}
                  {showTaskProjects && (
                    <NavLink to={appPath("/app/task-management/projects")} className={({ isActive }) => isActive ? styles.active : ""}>
                      <BriefcaseBusiness size={15} /><span>Projects</span>
                    </NavLink>
                  )}
                  {showTaskMyWork && (
                    <NavLink to={appPath("/app/task-management/my-work")} className={({ isActive }) => isActive ? styles.active : ""}>
                      <UserRound size={15} /><span>My Work</span>
                    </NavLink>
                  )}
                  {showTaskAll && (
                    <NavLink to={appPath("/app/task-management/tasks")} className={({ isActive }) => isActive ? styles.active : ""}>
                      <ListChecks size={15} /><span>All Tasks</span>
                    </NavLink>
                  )}
                </div>
              )}
            </div>
          )}
          {visibleOfferings.filter((offering) => offering.code !== "TASK_MANAGEMENT").map((offering) => {
            const Icon = iconByKey[offering.icon_key] ?? BriefcaseBusiness;
            const moduleRoute = `/app/modules/${offering.route_slug}`;
            if (!canAccessPage(principal, moduleRoute)) {
              return null;
            }
            return (
              <NavLink
                key={offering.offering_id}
                to={appPath(`/app/modules/${offering.route_slug}`)}
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
        {notice && <div className={styles.accessNotice} role="status"><span>{notice}</span><button type="button" onClick={clearNotice}>Dismiss</button></div>}
        {logoutError && <div className={styles.error} role="alert">{logoutError}</div>}
        <Outlet />
      </main>
    </div>
  );
};
