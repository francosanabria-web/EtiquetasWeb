import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import {
  MODULOS,
  etiquetaRol,
  type ModuloId,
  type NivelPermiso,
  type PermisosUsuario,
  type Rol,
  type Usuario,
} from "../../config/navegacion";
import {
  actualizarUsuario,
  crearUsuario,
  eliminarUsuario,
  fetchCatalogo,
  listarUsuarios,
  setPassword,
  type CatalogoUsuarios,
} from "../../api/usuariosClient";

const LABEL_MODULO: Record<string, string> = Object.fromEntries(
  MODULOS.map((m) => [m.id, m.titulo]),
);
const LABEL_NIVEL: Record<NivelPermiso, string> = {
  sin_acceso: "Sin acceso",
  consulta: "Consulta",
  escritura: "Escritura",
};

export default function UsuariosPage() {
  const { usuario: actual, token, refrescar } = useAuth();
  const [lista, setLista] = useState<Usuario[]>([]);
  const [catalogo, setCatalogo] = useState<CatalogoUsuarios | null>(null);
  const [sel, setSel] = useState<Usuario | null>(null);
  const [creando, setCreando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!token) return;
    setCargando(true);
    setError(null);
    try {
      const [cat, us] = await Promise.all([fetchCatalogo(), listarUsuarios(token)]);
      setCatalogo(cat);
      setLista(us);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar los usuarios.");
    } finally {
      setCargando(false);
    }
  }, [token]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const modulos = (catalogo?.modulos ?? []) as ModuloId[];
  const roles = catalogo?.roles ?? ["admin", "panol", "supervisor", "jefatura"];
  const niveles = catalogo?.niveles ?? ["sin_acceso", "consulta", "escritura"];

  const tras = useCallback(
    async (u: Usuario | null, texto: string) => {
      setAviso(texto);
      await cargar();
      if (u && actual && u.id === actual.id) await refrescar();
      setSel((prev) => (u ? lista.find((x) => x.id === u.id) ?? u : prev));
    },
    [cargar, actual, refrescar, lista],
  );

  return (
    <div className="page-content sol-page">
      <header className="page-header sol-header">
        <div>
          <h1>Usuarios</h1>
          <p className="sub">Alta de usuarios, contraseñas y permisos por módulo. Corre en la red interna.</p>
        </div>
        <button type="button" className="btn-primary" onClick={() => { setCreando(true); setSel(null); }}>
          + Nuevo usuario
        </button>
      </header>

      {error && <p className="error" role="status">{error}</p>}
      {aviso && <p className="minuta-ok" role="status">{aviso}</p>}

      <div className={`sol-layout${sel ? " con-detalle" : ""}`}>
        <div className="sol-table-wrap">
          {cargando ? (
            <p className="sol-hint">Cargando…</p>
          ) : (
            <table className="sol-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Nombre</th>
                  <th>Rol</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((u) => (
                  <tr
                    key={u.id}
                    className={sel?.id === u.id ? "selected" : ""}
                    onClick={() => { setSel(u); setCreando(false); }}
                  >
                    <td><strong>{u.usuario}</strong></td>
                    <td>{u.nombre}</td>
                    <td>{etiquetaRol(u.rol)}</td>
                    <td>
                      <span className={`sol-estado sol-estado-${u.activo ? "cumplido" : "cancelado"}`}>
                        {u.activo ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {sel && catalogo && (
          <EditorUsuario
            key={sel.id}
            usuario={sel}
            esYo={actual?.id === sel.id}
            token={token!}
            modulos={modulos}
            roles={roles}
            niveles={niveles}
            plantillas={catalogo.plantillas}
            onCerrar={() => setSel(null)}
            onGuardado={(u) => void tras(u, "Cambios guardados.")}
            onEliminado={() => { setSel(null); void tras(null, "Usuario eliminado."); }}
            onError={(m) => setError(m)}
          />
        )}
      </div>

      {creando && catalogo && (
        <div className="sol-modal-backdrop" role="dialog" aria-modal="true">
          <div className="sol-modal sol-modal-wide">
            <FormCrear
              token={token!}
              roles={roles}
              onCancelar={() => setCreando(false)}
              onCreado={(u) => { setCreando(false); void tras(u, `Usuario "${u.usuario}" creado.`); setSel(u); }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function MatrizPermisos({
  modulos,
  niveles,
  permisos,
  onChange,
}: {
  modulos: ModuloId[];
  niveles: NivelPermiso[];
  permisos: PermisosUsuario;
  onChange: (mod: ModuloId, nivel: NivelPermiso) => void;
}) {
  return (
    <div className="usr-matriz">
      {modulos.map((mod) => (
        <label key={mod} className="usr-matriz-fila">
          <span>{LABEL_MODULO[mod] ?? mod}</span>
          <select value={permisos[mod] ?? "sin_acceso"} onChange={(e) => onChange(mod, e.target.value as NivelPermiso)}>
            {niveles.map((n) => (
              <option key={n} value={n}>{LABEL_NIVEL[n] ?? n}</option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}

function EditorUsuario({
  usuario,
  esYo,
  token,
  modulos,
  roles,
  niveles,
  plantillas,
  onCerrar,
  onGuardado,
  onEliminado,
  onError,
}: {
  usuario: Usuario;
  esYo: boolean;
  token: string;
  modulos: ModuloId[];
  roles: Rol[];
  niveles: NivelPermiso[];
  plantillas: Record<Rol, PermisosUsuario>;
  onCerrar: () => void;
  onGuardado: (u: Usuario) => void;
  onEliminado: () => void;
  onError: (m: string) => void;
}) {
  const [nombre, setNombre] = useState(usuario.nombre);
  const [rol, setRol] = useState<Rol>(usuario.rol);
  const [activo, setActivo] = useState(!!usuario.activo);
  const [permisos, setPermisos] = useState<PermisosUsuario>(usuario.permisos);
  const [nuevaClave, setNuevaClave] = useState("");
  const [guardando, setGuardando] = useState(false);

  const guardar = async () => {
    setGuardando(true);
    try {
      const u = await actualizarUsuario(token, usuario.id, { nombre, rol, activo, permisos });
      onGuardado(u);
    } catch (e) {
      onError(e instanceof Error ? e.message : "No se pudo guardar.");
    } finally {
      setGuardando(false);
    }
  };

  const resetear = async () => {
    if (nuevaClave.length < 4) {
      onError("La contraseña debe tener al menos 4 caracteres.");
      return;
    }
    try {
      await setPassword(token, usuario.id, nuevaClave);
      setNuevaClave("");
      onGuardado(usuario);
    } catch (e) {
      onError(e instanceof Error ? e.message : "No se pudo cambiar la contraseña.");
    }
  };

  const borrar = async () => {
    if (!window.confirm(`¿Eliminar al usuario "${usuario.usuario}"? Esta acción no se puede deshacer.`)) return;
    try {
      await eliminarUsuario(token, usuario.id);
      onEliminado();
    } catch (e) {
      onError(e instanceof Error ? e.message : "No se pudo eliminar.");
    }
  };

  const aplicarPlantilla = () => setPermisos({ ...plantillas[rol] });

  return (
    <aside className="sol-detalle" aria-label="Editar usuario">
      <div className="sol-detalle-head">
        <h2>{usuario.usuario}</h2>
        <button type="button" className="btn-ghost btn-sm" onClick={onCerrar}>Cerrar</button>
      </div>

      <div className="sol-detalle-edit">
        <label>
          Nombre
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </label>
        <label>
          Rol base
          <select value={rol} onChange={(e) => setRol(e.target.value as Rol)}>
            {roles.map((r) => (<option key={r} value={r}>{etiquetaRol(r)}</option>))}
          </select>
        </label>
        <label className="usr-check">
          <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} disabled={esYo} />
          <span>Activo{esYo ? " (no podés desactivarte a vos mismo)" : ""}</span>
        </label>

        <div className="usr-matriz-head">
          <h3>Permisos por módulo</h3>
          <button type="button" className="btn-ghost btn-sm" onClick={aplicarPlantilla}>
            Aplicar plantilla del rol
          </button>
        </div>
        <MatrizPermisos
          modulos={modulos}
          niveles={niveles}
          permisos={permisos}
          onChange={(mod, nivel) => setPermisos((p) => ({ ...p, [mod]: nivel }))}
        />

        <button type="button" className="btn-primary btn-sm" disabled={guardando} onClick={() => void guardar()}>
          {guardando ? "Guardando…" : "Guardar cambios"}
        </button>
      </div>

      <div className="sol-detalle-edit usr-bloque">
        <h3>Restablecer contraseña</h3>
        <label>
          Nueva contraseña
          <input type="password" value={nuevaClave} onChange={(e) => setNuevaClave(e.target.value)} placeholder="mínimo 4 caracteres" />
        </label>
        <button type="button" className="btn-ghost btn-sm" onClick={() => void resetear()}>
          Cambiar contraseña
        </button>
      </div>

      {!esYo && (
        <button type="button" className="btn-ghost sol-borrar" onClick={() => void borrar()}>
          Eliminar usuario
        </button>
      )}
    </aside>
  );
}

function FormCrear({
  token,
  roles,
  onCancelar,
  onCreado,
}: {
  token: string;
  roles: Rol[];
  onCancelar: () => void;
  onCreado: (u: Usuario) => void;
}) {
  const [usuario, setUsuario] = useState("");
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [rol, setRol] = useState<Rol>("panol");
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const rolLabel = useMemo(() => etiquetaRol(rol), [rol]);

  const enviar = async () => {
    setError(null);
    setGuardando(true);
    try {
      const u = await crearUsuario(token, { usuario: usuario.trim().toLowerCase(), nombre: nombre.trim(), clave, rol });
      onCreado(u);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo crear el usuario.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <form
      className="sol-form"
      onSubmit={(e) => { e.preventDefault(); void enviar(); }}
    >
      <h2>Nuevo usuario</h2>
      {error && <p className="error" role="status">{error}</p>}
      <p className="sol-hint">
        Los permisos arrancan según la plantilla del rol <strong>{rolLabel}</strong>; después los ajustás en detalle.
      </p>
      <div className="sol-grid-2">
        <label>
          Usuario *
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)} placeholder="ej. fsanabria" required />
        </label>
        <label>
          Rol *
          <select value={rol} onChange={(e) => setRol(e.target.value as Rol)}>
            {roles.map((r) => (<option key={r} value={r}>{etiquetaRol(r)}</option>))}
          </select>
        </label>
      </div>
      <label>
        Nombre y apellido
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre visible" />
      </label>
      <label>
        Contraseña *
        <input type="password" value={clave} onChange={(e) => setClave(e.target.value)} placeholder="mínimo 4 caracteres" required />
      </label>
      <div className="sol-form-actions">
        <button type="button" className="btn-ghost" onClick={onCancelar} disabled={guardando}>Cancelar</button>
        <button type="submit" className="btn-primary" disabled={guardando}>
          {guardando ? "Creando…" : "Crear usuario"}
        </button>
      </div>
    </form>
  );
}
