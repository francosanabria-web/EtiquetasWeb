import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function RequireAuth() {
  const { usuario } = useAuth();
  if (!usuario) return <Navigate to="/login" replace />;
  return <Outlet />;
}
