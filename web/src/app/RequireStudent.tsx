import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { useSession } from "../session/session";

export function RequireStudent({ children }: { children: ReactNode }) {
  const s = useSession();
  if (!s) return <Navigate to="/" replace />;
  if (s.role === "staff") return <Navigate to="/staff" replace />;
  return <>{children}</>;
}
