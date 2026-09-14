import { modulosInicio } from "../config/navegacion";
import { etiquetaRol } from "../auth/demoUsers";
import { useAuth } from "../auth/AuthContext";
import ModuloCard from "../components/ModuloCard";

export default function HomePage() {
  const { usuario } = useAuth();
  if (!usuario) return null;

  const modulos = modulosInicio(usuario);

  return (
    <div className="page-content">
      <header className="page-header">
        <div>
          <h1>Bienvenido, {usuario.nombre}</h1>
          <p className="sub">
            Rol: <strong>{etiquetaRol(usuario.rol)}</strong> — acceso directo a los módulos
          </p>
        </div>
      </header>

      <section className="grid-modulos">
        {modulos.map((m) => (
          <ModuloCard key={m.id} mod={m} />
        ))}
      </section>
    </div>
  );
}
