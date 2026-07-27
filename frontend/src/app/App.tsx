import { RouterProvider } from "react-router-dom";

import { AuthProvider } from "./providers/AuthProvider";
import { router } from "./router/router";

export const App = () => (
  <AuthProvider>
    <RouterProvider router={router} />
  </AuthProvider>
);
