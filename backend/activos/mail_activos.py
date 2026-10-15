# -*- coding: utf-8 -*-
"""Envio diario de activos fuera de planta — 08:00 L-V, sin adjunto, a todo el personal habilitado.

Usa misma config SMTP que reportes (PANOL_SMTP_*) y destinatarios via personal_mail_prefs (activos_fuera).
No arranca scheduler: lo dispara Task Scheduler via run_mail_activos_0800.bat
"""

from __future__ import annotations
import os, sys
from pathlib import Path
from datetime import date, datetime
import html as _html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Cargar env de reportes para SMTP y destinatarios (reportes tiene _personal_destinatarios)
def _cargar_env_reportes():
    for p in [REPORTES_PATH / ".env", REPORTES_PATH.parent / ".env"]:
        if p.is_file():
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v

# REPORTES_PATH se inserta solo localmente en _smtp_creds/_destinatarios para no sombrear store de activos
REPORTES_PATH = Path(__file__).resolve().parent.parent / "reportes"
_cargar_env_reportes()

def _smtp_creds():
    # Reusa logica de reportes.config - insertar temporalmente REPORTES_PATH
    if str(REPORTES_PATH) not in sys.path:
        sys.path.insert(0, str(REPORTES_PATH))
    try:
        import config as rep_cfg  # noqa
    except Exception:
        pass
    user = (os.environ.get("PANOL_SMTP_USER") or os.environ.get("PANOL_SMTP_FROM") or "").strip()
    pwd = (os.environ.get("PANOL_SMTP_PASSWORD") or "").strip()
    from_addr = (os.environ.get("PANOL_SMTP_FROM") or user).strip()
    host = os.environ.get("PANOL_SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("PANOL_SMTP_PORT", "587"))
    if not user or not pwd:
        raise RuntimeError("SMTP no configurado PANOL_SMTP_USER/PASSWORD")
    return host, port, user, pwd, from_addr

def _dedup_mails(mails: list[str]) -> list[str]:
    """Dedup case-insensitive preservando primer ocurrencia."""
    seen: set[str] = set()
    out: list[str] = []
    for m in mails:
        key = m.strip().lower()
        if not key or "@" not in key:
            continue
        if key not in seen:
            seen.add(key)
            out.append(m.strip())
    return out


def _destinatarios_activos(mail_tipo: str = "activos_fuera"):
    # Replica logica de reportes.mail_jobs._personal_destinatarios sin importar reportes (evita colision de config)
    if os.environ.get("REPORTES_MAIL_USAR_PERSONAL", "0").strip().lower() in ("0", "false", "no", "off", ""):
        # fallback a env vacio si no usa personal
        return []
    try:
        import pymysql
        # Leer DB vars como hace reportes.config (usa SALIDAS_DB_* o REPORTES_DB_*)
        host = os.environ.get("REPORTES_DB_HOST") or os.environ.get("SALIDAS_DB_HOST") or os.environ.get("DB_HOST") or "127.0.0.1"
        port = int(os.environ.get("REPORTES_DB_PORT") or os.environ.get("SALIDAS_DB_PORT") or os.environ.get("DB_PORT") or "3306")
        user = os.environ.get("REPORTES_DB_USER") or os.environ.get("SALIDAS_DB_USER") or os.environ.get("DB_USER") or "root"
        pwd = os.environ.get("REPORTES_DB_PASSWORD") or os.environ.get("SALIDAS_DB_PASSWORD") or os.environ.get("DB_PASSWORD") or ""
        db = os.environ.get("REPORTES_DB_NAME") or os.environ.get("SALIDAS_DB_NAME") or os.environ.get("DB_NAME") or "panol"
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd, database=db, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", (db, "personal_mail_prefs"))
            table_exists = cur.fetchone()["c"] > 0
            if table_exists:
                cur.execute("SELECT COUNT(*) AS c FROM personal_mail_prefs WHERE mail_tipo = %s", (mail_tipo,))
                has_prefs = cur.fetchone()["c"] > 0
                if has_prefs:
                    cur.execute("""SELECT p.email FROM personal p INNER JOIN personal_mail_prefs pmp ON pmp.personal_id = p.id AND pmp.mail_tipo = %s AND pmp.habilitado = 1 WHERE p.activo = 1 AND p.email IS NOT NULL AND p.email <> ''""", (mail_tipo,))
                else:
                    cur.execute("SELECT email FROM personal WHERE activo=1 AND email IS NOT NULL AND email <> ''")
            else:
                cur.execute("SELECT email FROM personal WHERE activo=1 AND email IS NOT NULL AND email <> ''")
            rows = cur.fetchall()
            mails = [str(r["email"]).strip() for r in rows if str(r["email"]).strip() and "@" in str(r["email"])]
            return _dedup_mails(mails)
    except Exception as e:
        print(f"fallback destinatarios error: {e}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass

def _bg(d):
    try:
        d=int(float(d))
    except:
        d=0
    if d>30:
        return "#FFC7CE"
    if d>21:
        return "#FFEB9C"
    return "#C6EFCE"


def notify_cambio(evento: str, registro: dict) -> None:
    """Dispara mail inmediato tras create/edit/regreso.

    Se ejecuta en hilo separado (thread + try/except) para nunca bloquear la respuesta.
    Respeta ACTIVOS_FOTOS_ENABLED. Formato: asunto/cuerpo minimos + TODO formato.
    El caller debe pasar un diccionario 'registro' con los datos relevantes.
    """
    # Respeta feature flag
    from db import ACTIVOS_FOTOS_ENABLED
    if not ACTIVOS_FOTOS_ENABLED:
        return

    try:
        # Ejecutar en hilo separado para no bloquear respuesta
        import threading
        import time as _time

        def _send():
            try:
                # Datos minimos del registro
                act_id = registro.get("id", "")
                act_desc = registro.get("equipo", "")
                sector = registro.get("sector", "")
                usuario = registro.get("usuario", "")
                fecha = _time.strftime("%Y-%m-%d %H:%M:%S")
                cambio = registro.get("cambio", "")

                # Asunto minimo
                asunto = f"Activos: {evento} - ID {act_id}"

                # Cuerpo minimo (formato pending - TODO)
                cuerpo = f"""\
Activo ID: {act_id}
Descripcion: {act_desc}
Sector: {sector}
Usuario: {usuario}
Fecha: {fecha}
Cambio: {cambio}
                """

                # Enviar via SMTP (misma logica que run_activos_si_habilitado)
                import os, sys
                from pathlib import Path
                from datetime import date, datetime
                import html as _html
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText

                REPORTES_PATH = Path(__file__).resolve().parent.parent / "reportes"

                def _cargar_env_reportes():
                    for p in [REPORTES_PATH / ".env", REPORTES_PATH.parent / ".env"]:
                        if p.is_file():
                            for raw in p.read_text(encoding="utf-8").splitlines():
                                line = raw.strip()
                                if not line or line.startswith("#") or "=" not in line:
                                    continue
                                k, _, v = line.partition("=")
                                k, v = k.strip(), v.strip().strip('"').strip("'")
                                if k and k not in os.environ:
                                    os.environ[k] = v

                _cargar_env_reportes()

                def _smtp_creds():
                    if str(REPORTES_PATH) not in sys.path:
                        sys.path.insert(0, str(REPORTES_PATH))
                    try:
                        import config as rep_cfg  # noqa
                    except Exception:
                        pass
                    user = (os.environ.get("PANOL_SMTP_USER") or os.environ.get("PANOL_SMTP_FROM") or "").strip()
                    pwd = (os.environ.get("PANOL_SMTP_PASSWORD") or "").strip()
                    from_addr = (os.environ.get("PANOL_SMTP_FROM") or user).strip()
                    host = os.environ.get("PANOL_SMTP_HOST", "smtp.gmail.com").strip()
                    port = int(os.environ.get("PANOL_SMTP_PORT", "587"))
                    if not user or not pwd:
                        return
                    return host, port, user, pwd, from_addr

                creds = _smtp_creds()
                if not creds:
                    # Si no hay credenciales, solo loguear y retornar
                    print(f"notify_cambio: SMTP no configurado, evento={evento}, id={act_id}")
                    return

                host, port, user, pwd, from_addr = creds

                msg = MIMEMultipart("mixed")
                msg["From"] = from_addr
                msg["To"] = "pañol"  # destinatario designo
                msg["Subject"] = asunto
                txt = f"Activos: {evento} - ID {act_id} - {fecha}"
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(txt, "plain", "utf-8"))
                msg.attach(alt)

                with smtplib.SMTP(host, port, timeout=45) as s:
                    s.starttls()
                    s.login(user, pwd)
                    s.sendmail(from_addr, ["pañol@panol.local"], msg.as_string())
            except Exception as e:
                # Nunca lanzar error al caller - try/except completo
                print(f"notify_cambio error (silenciado): {e}")

        t = threading.Thread(target=_send, daemon=True)
        t.start()
    except Exception:
        # Fallo absoluto: no bloquear caller
        print(f"notify_cambio outer error (silenciado): {__import__('sys').exc_info()[1]}")


def alerta_sobreextendido() -> dict:
    """Verifica registros fuera_de_planta sin fecha_regreso y envia alerts.

    - DIAS_AVISO=21: alerta advisory si supera los 21 dias
    - DIAS_ALERTA=30: alerta critica si supera los 30 dias
    - Solo envia si no tiene fecha_regreso (aun esta fuera)
    - Loggea el evento en consola (o integrate con logger formal despues)
    Returns dict con el resumen de alerts enviadas.
    """
    from db import get_connection, ACTIVOS_DB_ENABLED
    from config import DIAS_AVISO, DIAS_ALERTA
    from mail_activos import notify_cambio

    if not ACTIVOS_DB_ENABLED:
        return {"enviado": False, "motivo": "ACTIVOS_DB_ENABLED=0", "advisory": 0, "critical": 0}

    try:
        conn = get_connection()
        with conn.cursor() as cur:
            # Query: fuera_de_planta sin fecha_regreso
            cur.execute(
                """
                SELECT id, equipo, fecha_salida, usuario_creador_id
                FROM salida_activos
                WHERE estado = 'fuera_de_planta' AND fecha_regreso IS NULL
                """,
            )
            rows = cur.fetchall()

        advisory_count = 0
        critical_count = 0
        ahora = date.today()

        for row in rows:
            db_id = row["id"]
            equipo = row["equipo"]
            fecha_salida = row["fecha_salida"]
            if isinstance(fecha_salida, date):
                dias_fuera = (ahora - fecha_salida).days
            else:
                # Formato string YYYY-MM-DD
                try:
                    from datetime import datetime
                    fs = datetime.strptime(str(fecha_salida), "%Y-%m-%d").date()
                    dias_fuera = (ahora - fs).days
                except Exception:
                    continue

            usuario_id = row.get("usuario_creador_id")

            # Determinar nivel de alerta
            if dias_fuera >= DIAS_ALERTA:
                evento = "alerta_critica"
                mensaje = f"Alerta: superado limite de {DIAS_ALERTA} dias — requiere accion inmediata"
                # Enviar advisory critica
                try:
                    registro = {
                        "id": db_id,
                        "equipo": equipo,
                        "sector": "",
                        "usuario": usuario_id,
                        "cambio": f"{evento}: {dias_fuera} dias fuera",
                    }
                    notify_cambio(evento, registro)
                    critical_count += 1
                except Exception:
                    pass
            elif dias_fuera >= DIAS_AVISO:
                evento = "alerta_advisory"
                mensaje = f"Aviso: superado limite de {DIAS_AVISO} dias"
                # Enviar advisory
                try:
                    registro = {
                        "id": db_id,
                        "equipo": equipo,
                        "sector": "",
                        "usuario": usuario_id,
                        "cambio": f"{evento}: {dias_fuera} dias fuera",
                    }
                    notify_cambio(evento, registro)
                    advisory_count += 1
                except Exception:
                    pass
            # else: below threshold, no alert

        conn.close()
        return {
            "enviado": True,
            "advisory": advisory_count,
            "critical": critical_count,
            "total_revisados": len(rows),
        }
    except Exception as e:
        print(f"alerta_sobreextendido error: {e}")
        return {"enviado": False, "motivo": str(e), "advisory": 0, "critical": 0}

def armar_html_activos(fecha=None):
    """Genera HTML de activos fuera con formato fijo corregido."""
    from store import ActivosStore
    from service import activos_resumen
    s = ActivosStore.get()
    s.refresh()
    data = activos_resumen(s)
    lista = sorted(data.get("lista_fuera", []), key=lambda x: x.get("dias_fuera",0), reverse=True)
    criticos = len([x for x in lista if x.get("dias_fuera",0)>30])
    prom = data.get("dias_promedio_fuera",0)
    fecha = fecha or date.today()
    fecha_badge = fecha.strftime("%d/%m/%Y")
    fecha_footer = datetime.now().strftime("%d/%m/%Y %H:%M")
    def esc(v): return _html.escape(str(v or ""))
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Activos fuera de planta - Pa&ntilde;ol</title>
<style>
  body {{ margin:0; padding:0; background:#f6f8fb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#1a202c; }}
  .wrapper {{ width:100%; background:#f6f8fb; padding:16px 0; }}
  .container {{ max-width:1200px; width:100%; margin:0 auto; background:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 16px rgba(0,0,0,0.06); box-sizing:border-box; }}
  .header {{ background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%); color:#fff; padding:28px 24px; }}
  .header h1 {{ margin:0; font-size:20px; font-weight:700; letter-spacing:-0.02em; color:#fff; }}
  .header p {{ margin:8px 0 0 0; font-size:13px; opacity:0.9; color:#fff; }}
  .badge {{ display:inline-block; background:rgba(255,255,255,0.18); border:1px solid rgba(255,255,255,0.25); border-radius:999px; padding:4px 12px; font-size:12px; font-weight:600; margin-top:12px; color:#fff; }}
  .summary {{ display:flex; gap:16px; padding:20px 24px 0 24px; flex-wrap:wrap; }}
  .card {{ flex:1; min-width:140px; background:#f7fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px; }}
  .card-label {{ font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:#4a5568; font-weight:600; }}
  .card-value {{ font-size:18px; font-weight:700; color:#000000; margin-top:4px; }}
  .content {{ padding:20px 24px; }}
  .table-wrap {{ overflow-x:visible; margin:12px 0 8px 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:11px; }}
  th {{ background:#1a365d; color:#fff; text-align:left; padding:6px 8px; font-weight:600; white-space:nowrap; }}
  td {{ padding:6px 8px; border:1px solid #e2e8f0; color:#000000; }}
  .footer {{ padding:18px 24px; background:#f7fafc; border-top:1px solid #e2e8f0; font-size:11px; color:#718096; text-align:center; }}
  .cta {{ display:inline-block; margin-top:14px; background:#2b6cb0; color:#fff; text-decoration:none; padding:10px 18px; border-radius:8px; font-size:13px; font-weight:600; }}
  @media only screen and (max-width: 640px) {{
    .container {{ margin:0 8px; max-width:100%; }}
    .header, .content, .summary, .footer {{ padding-left:16px; padding-right:16px; }}
    .summary {{ flex-direction:column; }}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="container">
    <div class="header">
      <h1>Activos fuera de planta</h1>
      <p>Equipos y repuestos fuera de planta &mdash; Detalle en el cuerpo del mail</p>
      <div class="badge">{fecha_badge} &nbsp;&#8226;&nbsp; {len(lista)} activos</div>
    </div>
    <div class="summary">
      <div class="card">
        <div class="card-label">Fuera de planta</div>
        <div class="card-value">{len(lista)}</div>
      </div>
      <div class="card">
        <div class="card-label">D&iacute;as promedio</div>
        <div class="card-value">{prom}</div>
      </div>
      <div class="card">
        <div class="card-label">Cr&iacute;ticos &gt;30 d&iacute;as</div>
        <div class="card-value">{criticos}</div>
      </div>
    </div>
    <div class="content">
      <div class="table-wrap">
        <table>
          <thead><tr><th>D&iacute;as fuera</th><th>Equipo</th><th>Cantidad</th><th>Observaciones</th><th>Proveedor</th><th>Sector</th></tr></thead>
          <tbody>"""
    for it in lista:
        bgc = _bg(it.get("dias_fuera",0))
        html += f"""<tr><td style="background:{bgc}; text-align:center; font-weight:700; color:#000000;">{esc(it.get('dias_fuera',''))}</td><td style="background:{bgc}; color:#000000;">{esc(it.get('equipo',''))}</td><td style="background:{bgc}; text-align:center; color:#000000;">{esc(it.get('cantidad',1))}</td><td style="background:{bgc}; color:#000000;">{esc(it.get('observaciones',''))}</td><td style="background:{bgc}; color:#000000;">{esc(it.get('proveedor',''))}</td><td style="background:{bgc}; color:#000000;">{esc(it.get('sector',''))}</td></tr>"""
    html += f"""</tbody>
        </table>
      </div>
      <p style="text-align:center; margin:22px 0 0 0;">
        <a class="cta" href="http://localhost:5180/activos">Ver detalle completo en portal &rarr;</a>
      </p>
    </div>
    <div class="footer">
      Sistemas pa&ntilde;ol - Mantenimiento - {fecha_footer}
    </div>
  </div>
</div>
</body>
</html>
"""
    return html, len(lista)

def _sentinel_path(fecha: date) -> Path:
    """Archivo centinela para evitar duplicado intra-día."""
    base = Path(__file__).resolve().parent.parent.parent / "scripts" / "logs"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base / f"mail_activos_{fecha.isoformat()}.sent"


def run_activos_si_habilitado(fecha=None, destinatarios=None, forzar=False):
    # Flag para desactivar si hace falta
    if not forzar:
        # reuse REPORTES_MAIL_ACTIVOS_ENABLED if exists, else check env
        enabled = os.environ.get("REPORTES_MAIL_ACTIVOS_ENABLED", "1").strip().lower() not in ("0","false","no","off","")
        if not enabled:
            return {"enviado": False, "motivo": "REPORTES_MAIL_ACTIVOS_ENABLED=0"}
    fecha = fecha or date.today()
    # ── Anti-duplicado: si ya se envió hoy y no se fuerza con destinatarios explícitos, no reenviar ──
    sentinel = _sentinel_path(fecha)
    if destinatarios is None and sentinel.exists():
        # Si forzar=True y ya existe centinela, lo consideramos duplicado salvo que el caller pase destinatarios explícitos
        # Para no romper el forzar manual del bat, permitimos reenvío solo si han pasado > 5 minutos desde el centinela
        # o si el archivo es de otro día (ya distinto iso). Caso scheduler: segundo disparo el mismo día debe ser bloqueado.
        try:
            age_min = (datetime.now().timestamp() - sentinel.stat().st_mtime) / 60
            if age_min < 60 and forzar:
                # Duplicado intra-hora por scheduler doble disparo -> bloquear
                return {"enviado": False, "motivo": "duplicado_bloqueado", "sentinel": str(sentinel), "edad_min": round(age_min, 1)}
        except Exception:
            return {"enviado": False, "motivo": "duplicado_bloqueado", "sentinel": str(sentinel)}
    html, cant = armar_html_activos(fecha)
    dests = destinatarios if destinatarios is not None else _destinatarios_activos()
    if not dests:
        raise RuntimeError("Sin destinatarios para activos_fuera")
    dests = _dedup_mails(dests)
    host, port, user, pwd, from_addr = _smtp_creds()
    asunto = f"Activos fuera de planta - {fecha.strftime('%d/%m/%Y')}"
    txt = f"Activos fuera de planta - {fecha.isoformat()} - {cant} activos. Ver detalle en cuerpo del mail."
    msg = MIMEMultipart("mixed")
    msg["From"] = from_addr
    msg["To"] = ", ".join(dests)
    msg["Subject"] = asunto
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(txt, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)
    with smtplib.SMTP(host, port, timeout=45) as s:
        s.starttls()
        s.login(user, pwd)
        s.sendmail(from_addr, dests, msg.as_string())
    # Marcar centinela solo para envíos de scheduler (destinatarios=None) -> no bloquear tests manuales con dest explícito
    if destinatarios is None:
        try:
            sentinel.write_text(f"{datetime.now().isoformat()} cant={cant} dests={len(dests)}\n", encoding="utf-8")
        except Exception:
            pass
    return {"enviado": True, "tipo": "activos", "fecha": fecha.isoformat(), "activos": cant, "destinatarios": dests}

if __name__ == "__main__":
    import json
    print(json.dumps(run_activos_si_habilitado(forzar=True), indent=2, ensure_ascii=False))
