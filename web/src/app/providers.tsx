import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import { useEffect, type ReactNode } from "react";
import { bindClockToQueries } from "../session/clock";
import { session } from "../session/session";
import { setTransport, DEFAULT_API } from "../api/transport";
import { ApiError } from "../api/transport";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // transport already retries GETs once on network/5xx; don't stack retries on top, and never retry 4xx
      retry: (count, err) => count < 1 && !(err instanceof ApiError && err.status >= 400 && err.status < 500),
    },
    mutations: { retry: false },
  },
});

setTransport("live", { base: DEFAULT_API, token: () => session.token() });

export function Providers({ children }: { children: ReactNode }) {
  useEffect(() => bindClockToQueries(queryClient), []);
  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </QueryClientProvider>
  );
}
