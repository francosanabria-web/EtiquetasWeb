import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Usuario } from "../config/navegacion";
import { login, logout, me } from "../api/usuariosClient";

const STORAGE_KEY = "panol_shell_session";

type Session = { usuario: Usuario; token: string };

type AuthCtx = {
  usuario: Usuario | null;
  token: string | null;
  iniciarSesion: (usuario: string, clave: string) => Promise<string | null>;
  cerrarSesion: () => void;
  refrescar: () => Promise<void>;
};

/** True when the /me failure means the token is no longer valid (local sign-out). */
function esNoAutorizado(e: unknown): boolean {
  if (!(e instanceof Error)) return false;
  return /401|no autorizad|token/i.test(e.message);
}

/**
 * Normalizes the login identifier to the plain username expected by the
 * usuarios backend: accepts "admin" and "admin@panol.local" (any
 * "x@panol.local"), returning "x". Other inputs are returned trimmed.
 */
export function normalizeUsername(input: string): string {
  const trimmed = input.trim();
  const at = trimmed.indexOf("@");
  return at > 0 ? trimmed.slice(0, at) : trimmed;
}

const AuthContext = createContext<AuthCtx | null>(null);

function leerSesion(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Session>;
    // Discard legacy sessions stored as a plain Usuario (no token).
    if (!parsed || typeof parsed.token !== "string" || !parsed.usuario) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed as Session;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => leerSesion());

  const iniciarSesion = useCallback(async (identificador: string, clave: string) => {
    try {
      const res = await login(normalizeUsername(identificador), clave);
      const next: Session = { usuario: res.usuario, token: res.token };
      setSession(next);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return null;
    } catch (e) {
      return e instanceof Error ? e.message : "No se pudo iniciar sesión.";
    }
  }, []);

  const cerrarSesion = useCallback(() => {
    const token = session?.token;
    if (token) {
      void logout(token).catch(() => {});
    }
    setSession(null);
    localStorage.removeItem(STORAGE_KEY);
  }, [session]);

  const limpiarSesionLocal = useCallback(() => {
    setSession(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const refrescar = useCallback(async () => {
    const token = session?.token;
    if (!token) return;
    try {
      const usuario = await me(token);
      const next: Session = { usuario, token };
      setSession(next);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch (e) {
      if (esNoAutorizado(e)) {
        limpiarSesionLocal();
      }
      // Transient network failure: keep the current session as-is.
    }
  }, [session, limpiarSesionLocal]);

  useEffect(() => {
    void refrescar();
    // Sync the persisted session against /me only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo(
    () => ({
      usuario: session?.usuario ?? null,
      token: session?.token ?? null,
      iniciarSesion,
      cerrarSesion,
      refrescar,
    }),
    [session, iniciarSesion, cerrarSesion, refrescar]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}
