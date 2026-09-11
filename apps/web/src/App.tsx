import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { lazy, Suspense } from "react";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { RequirePermiso } from "./auth/RequirePermiso";
import ErrorBoundary from "./components/ErrorBoundary";
import AppShell from "./layouts/AppShell";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import ActivosFueraPage from "./pages/ActivosFueraPage";
import MinutaListadoPage from "./modules/minuta/MinutaListadoPage";
import MinutaReunionPage from "./modules/minuta/MinutaReunionPage";
import SolicitudesPage from "./modules/solicitudes/SolicitudesPage";
import UsuariosPage from "./modules/usuarios/UsuariosPage";
import ReportesPage from "./modules/reportes/ReportesPage";
import SalidasPage from "./modules/salidas/SalidasPage";
import PersonalPage from "./modules/personal/PersonalPage";
import CajasPage from "./modules/cajas/CajasPage";

const KpiDashboard = lazy(() => import("./components/kpis/KpiDashboard"));

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<AppShell />}>
                <Route path="/" element={<HomePage />} />
                <Route element={<RequirePermiso modulo="salidas" />}>
                  <Route path="/salidas" element={<SalidasPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="reportes" />}>
                  <Route path="/reportes" element={<ReportesPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="activos" />}>
                  <Route path="/activos" element={<ActivosFueraPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="minuta" />}>
                  <Route path="/minuta" element={<MinutaListadoPage />} />
                  <Route path="/minuta/:reunionId" element={<MinutaReunionPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="solicitudes" />}>
                  <Route path="/solicitudes" element={<SolicitudesPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="kpis" />}>
                  <Route
                    path="/kpis"
                    element={
                      <Suspense fallback={<p className="sub">Cargando KPIs…</p>}>
                        <KpiDashboard />
                      </Suspense>
                    }
                  />
                </Route>
                <Route element={<RequirePermiso modulo="usuarios" />}>
                  <Route path="/usuarios" element={<UsuariosPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="personal" />}>
                  <Route path="/admin/personal" element={<PersonalPage />} />
                </Route>
                <Route element={<RequirePermiso modulo="cajas" />}>
                  <Route path="/admin/cajas" element={<CajasPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
