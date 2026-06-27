import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Usuario } from "../config/modulos";
import { autenticarDemo } from "./demoUsers";

const STORAGE_KEY = "panol_shell_session";

type AuthCtx = {
  usuario: Usuario | null;
  iniciarSesion: (email: string, clave: string) => Promise<string | null>;
  cerrarSesion: () => void;
};

const AuthContext = createContext<AuthCtx | null>(null);

function leerSesion(): Usuario | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Usuario;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(() => leerSesion());

  const iniciarSesion = useCallback(async (email: string, clave: string) => {
    // Futuro: Firebase Auth signInWithEmailAndPassword + custom claims (rol).
    const u = autenticarDemo(email, clave);
    if (!u) return "Usuario o contraseña incorrectos.";
    setUsuario(u);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
    return null;
  }, []);

  const cerrarSesion = useCallback(() => {
    setUsuario(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const value = useMemo(
    () => ({ usuario, iniciarSesion, cerrarSesion }),
    [usuario, iniciarSesion, cerrarSesion]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}
