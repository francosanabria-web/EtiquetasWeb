import { NavLink } from "react-router-dom";
import { modulosSidebar, type ModuloNav, type Rol } from "../config/navegacion";

type Props = {
  rol: Rol;
};

function ItemInterno({ mod }: { mod: ModuloNav }) {
  if (!mod.ruta) return null;
  return (
    <NavLink
      to={mod.ruta}
      end={mod.ruta === "/"}
      className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
    >
      <span className="nav-icon" aria-hidden>
        {mod.icono}
      </span>
      <span className="nav-label">{mod.titulo}</span>
    </NavLink>
  );
}

function ItemExterno({ mod }: { mod: ModuloNav }) {
  return (
    <a
      className="nav-item nav-item-ext"
      href={mod.href}
      target="_blank"
      rel="noopener noreferrer"
    >
      <span className="nav-icon" aria-hidden>
        {mod.icono}
      </span>
      <span className="nav-label">{mod.titulo}</span>
      <span className="nav-ext-badge" title="Abre en nueva pestaña">
        ↗
      </span>
    </a>
  );
}

function ItemProximo({ mod }: { mod: ModuloNav }) {
  return (
    <span className="nav-item nav-item-disabled" aria-disabled="true" title="Próximamente">
      <span className="nav-icon" aria-hidden>
        {mod.icono}
      </span>
      <span className="nav-label">{mod.titulo}</span>
      <span className="nav-prox-badge">Próximamente</span>
    </span>
  );
}

export default function SidebarNav({ rol }: Props) {
  const items = modulosSidebar(rol);

  return (
    <nav className="sidebar-nav" aria-label="Módulos del sistema">
      {items.map((mod) => {
        if (mod.tipo === "proximo") {
          return <ItemProximo key={mod.id} mod={mod} />;
        }
        if (mod.tipo === "externo") {
          return <ItemExterno key={mod.id} mod={mod} />;
        }
        return <ItemInterno key={mod.id} mod={mod} />;
      })}
    </nav>
  );
}
