import { type FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { usuario, iniciarSesion } = useAuth();
  const [identificador, setIdentificador] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setCargando(true);
    setError(null);
    const err = await iniciarSesion(identificador, clave);
    setCargando(false);
    if (err) setError(err);
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={enviar}>
        <h1>Sistemas Pañol</h1>
        <p className="sub">Portal integrado de gestión</p>

        <label>
          Usuario
          <input
            type="text"
            autoComplete="username"
            value={identificador}
            onChange={(e) => setIdentificador(e.target.value)}
            placeholder="Usuario"
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
      </form>
    </div>
  );
}
