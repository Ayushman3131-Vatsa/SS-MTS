import { Navigate, useSearchParams } from "react-router-dom";

export const DefaultRolesPage = () => {
  const [searchParams] = useSearchParams();
  const next = new URLSearchParams(searchParams);
  next.set("type", "tenant");
  const suffix = next.toString();
  return <Navigate to={suffix ? `/platform/roles?${suffix}` : "/platform/roles?type=tenant"} replace />;
};
