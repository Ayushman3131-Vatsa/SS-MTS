import { Navigate } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { FullPageLoader } from "../../shared/ui/FullPageLoader/FullPageLoader";

export const RootRoute = () => {
  const { principal, status } = useSession();
  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }
  return (
    <Navigate
      to={principal ? getPrincipalHome(principal) : "/login"}
      replace
    />
  );
};

export const NotFoundRoute = () => {
  const { principal } = useSession();
  return (
    <Navigate
      to={principal ? getPrincipalHome(principal) : "/login"}
      replace
    />
  );
};
