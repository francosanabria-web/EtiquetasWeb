import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import ModuloPlaceholder from "./pages/ModuloPlaceholder";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<HomePage />} />
            <Route
              path="/modulos/panol"
              element={<ModuloPlaceholder titulo="Pañol — Buscador" />}
            />
            <Route
              path="/modulos/salidas"
              element={<ModuloPlaceholder titulo="Salidas de pañol" />}
            />
            <Route
              path="/modulos/inventario"
              element={<ModuloPlaceholder titulo="Inventario" />}
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
