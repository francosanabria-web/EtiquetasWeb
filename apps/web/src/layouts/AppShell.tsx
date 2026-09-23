import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { etiquetaRol } from "../config/navegacion";
import { useAuth } from "../auth/AuthContext";
import SidebarNav from "../components/SidebarNav";

const THEME_KEY = "panol_theme";
const SIDEBAR_KEY = "panol_sidebar_collapsed";

function aplicarTema(theme: "light" | "dark") {
  document.documentElement.setAttribute("data-theme", theme);
}

export default function AppShell() {
  const { usuario, cerrarSesion } = useAuth();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    try {
      const t = localStorage.getItem(THEME_KEY);
      return t === "dark" ? "dark" : "light";
    } catch {
      return "light";
    }
  });

  useEffect(() => {
    aplicarTema(theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  if (!usuario) return null;

  return (
    <div className={`app-layout${collapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">SP</span>
          <div className="brand-text">
            <strong>Sistemas Pañol</strong>
            <span className="brand-sub">Portal integrado</span>
          </div>
          <button
            type="button"
            className="sidebar-toggle"
            title={collapsed ? "Expandir menú" : "Achicar menú"}
            aria-label={collapsed ? "Expandir menú" : "Achicar menú"}
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
        <SidebarNav usuario={usuario} />
        <div className="sidebar-foot">
          <p className="user-name">{usuario.nombre}</p>
          <p className="user-role">{etiquetaRol(usuario.rol)}</p>
          <label className="theme-switch">
            <input
              type="checkbox"
              checked={theme === "dark"}
              onChange={(e) => setTheme(e.target.checked ? "dark" : "light")}
            />
            <span>{theme === "dark" ? "Modo oscuro" : "Modo claro"}</span>
          </label>
          <button type="button" className="btn-ghost btn-sm btn-full btn-logout" onClick={cerrarSesion}>
            <span className="logout-full">Cerrar sesión</span>
            <span className="logout-short" aria-hidden>
              Salir
            </span>
          </button>
        </div>
      </aside>

      <div className="main-panel">
        <Outlet />
      </div>
    </div>
  );
}
