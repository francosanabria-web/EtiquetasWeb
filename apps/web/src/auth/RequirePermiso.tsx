import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { permisoDe, type ModuloId } from "../config/navegacion";

/** Bloquea el acceso por URL a un módulo si el usuario no tiene permiso. */
export function RequirePermiso({ modulo }: { modulo: ModuloId }) {
  const { usuario } = useAuth();
  if (!usuario) return <Navigate to="/login" replace />;
  if (permisoDe(usuario, modulo) === "sin_acceso") return <Navigate to="/" replace />;
  return <Outlet />;
}
