/**
 * PersonalMailPrefs — Checklist de preferencias de mail por personal.
 * Muestra 2 switches: "Gastos diario" y "Activos fuera".
 * Carga via GET /api/personal/{id}/mail-prefs, guarda via PUT.
 */

import { useState, useEffect, useCallback } from "react";
import { getPersonalMailPrefs, setPersonalMailPrefs, type MailPrefs } from "../../api/personalClient";

type Props = {
  personalId: number;
  personalNombre: string;
  token: string;
};

const TIPOS_MAIL = [
  { key: "diario_gastos", label: "Gastos diario" },
  { key: "activos_fuera", label: "Activos fuera" },
];

export default function PersonalMailPrefs({ personalId, personalNombre, token }: Props) {
  const [prefs, setPrefs] = useState<MailPrefs>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const data = await getPersonalMailPrefs(token, personalId);
      setPrefs(data);
    } catch {
      // Silencioso si la API falla
    } finally {
      setLoading(false);
    }
  }, [token, personalId]);

  useEffect(() => { void cargar(); }, [cargar]);

  const cambiarPref = async (key: string, valor: boolean) => {
    const nuevos = { ...prefs, [key]: valor };
    setPrefs(nuevos);
    setError(null);
    setSaving(true);
    try {
      await setPersonalMailPrefs(token, personalId, nuevos);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar prefs.");
      // Revertir
      setPrefs(prefs);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <span className="sol-hint">Cargando prefs…</span>;
  }

  return (
    <div className="personal-mail-prefs">
      <span className="personal-mail-prefs-label" title={personalNombre}>
        {personalNombre}:
      </span>
      <div className="personal-mail-prefs-checks">
        {TIPOS_MAIL.map(({ key, label }) => (
          <label key={key} className="sol-check">
            <input
              type="checkbox"
              checked={!!prefs[key]}
              onChange={(e) => cambiarPref(key, e.target.checked)}
              disabled={saving}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
      {error && <span className="error" role="status">{error}</span>}
    </div>
  );
}
