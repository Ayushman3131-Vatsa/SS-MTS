import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type PropsWithChildren, useState } from "react";

import { ApiError } from "../../../../shared/api/errors";

export const TaskManagementProvider = ({ children }: PropsWithChildren) => {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        staleTime: 15_000,
        retry: (attempt, error) => attempt < 2 && (!(error instanceof ApiError) || error.status >= 500),
      },
      mutations: { retry: false },
    },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

