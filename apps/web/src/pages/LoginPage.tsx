import { type FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { usuario, iniciarSesion } = useAuth();
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setCargando(true);
    setError(null);
    const err = await iniciarSesion(email, clave);
    setCargando(false);
    if (err) setError(err);
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={enviar}>
        <h1>Pañol</h1>
        <p className="sub">Sistema integrado de gestión</p>

        <label>
          Usuario / email
          <input
            type="text"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@panol.local"
            required
          />
        </label>

        <label>
          Contraseña
          <input
            type="password"
            autoComplete="current-password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            required
          />
        </label>

        {error && <p className="error">{error}</p>}

        <button type="submit" disabled={cargando}>
          {cargando ? "Ingresando…" : "Iniciar sesión"}
        </button>

        <details className="demo-hint">
          <summary>Cuentas de prueba (solo desarrollo)</summary>
          <ul>
            <li><strong>Admin:</strong> admin@panol.local / admin123</li>
            <li><strong>Pañolero:</strong> panolero@panol.local / panol123</li>
            <li><strong>Consulta:</strong> consulta@panol.local / consulta123</li>
          </ul>
        </details>
      </form>
    </div>
  );
}
