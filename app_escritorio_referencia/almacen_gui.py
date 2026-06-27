import os
import sys
import html
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import pandas as pd
from tkcalendar import DateEntry
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import threading 
from datetime import datetime, timedelta, date
import traceback
from pandas.api.types import is_string_dtype

# --- INTEGRACIÓN FIREBASE ---
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    firebase_admin = None

# GPS INTERNO
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base unificada (maestro + stock mín + importancia). Si no existe, se intenta cargar master_codes.xlsx (legado).
BASE_DATOS_DEFAULT = os.path.join(BASE_DIR, "base_datos.xlsx")
MASTER_LEGACY = os.path.join(BASE_DIR, "master_codes.xlsx")
HOJA_ARTICULOS = "ARTICULOS"
HISTORIAL_PATH = os.path.join(BASE_DIR, "master_salidas.xlsx")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")
LAST_MAIL_FILE = os.path.join(BASE_DIR, ".ultimo_mail.txt")
LAST_MAIL_GASTOS_FILE = os.path.join(BASE_DIR, ".ultimo_mail_gastos.txt")
LAST_MAIL_SEGUIMIENTO_FILE = os.path.join(BASE_DIR, ".ultimo_mail_seguimiento.txt")
JSON_KEY = os.path.join(BASE_DIR, "serviceAccountKey.json")
CARPETA_IMPORTAR = os.path.join(BASE_DIR, "importar_stock")
SALIDA_ACTIVOS_PATH = os.path.join(BASE_DIR, "salida_activos.xlsx")
SEGUIMIENTO_REPARACION_LEGACY = os.path.join(BASE_DIR, "seguimiento_salidas_reparacion.xlsx")
CRITICIDAD_OPCIONES_MAESTRO = ("CRÍTICO", "ALTA FRECUENCIA", "BASE")

# Orden de sectores en mail y tablas de gastos
ORDEN_SECTORES_GASTOS = [
    ('MANTENIMIENTO', 'Mantenimiento'),
    ('EDILICIO', 'Edilicio'),
    ('PROYECTOS', 'Proyectos'),
    ('PRODUCCION', 'Producción'),
]

# Colores HTML por sector (mail de gastos)
ESTILO_SECTOR_HTML = {
    'MANTENIMIENTO': {'bg': '#D6EAF8', 'border': '#2980B9', 'title': '#1A5276', 'th': '#2980B9'},
    'EDILICIO': {'bg': '#ECF0F1', 'border': '#95A5A6', 'title': '#566573', 'th': '#7F8C8D'},
    'PROYECTOS': {'bg': '#D5F5E3', 'border': '#27AE60', 'title': '#1E8449', 'th': '#27AE60'},
    'PRODUCCION': {'bg': '#FCF3CF', 'border': '#F4D03F', 'title': '#9A7D0A', 'th': '#D4AC0D'},
}

# --- INICIALIZAR FIREBASE ---
# La app de escritorio usa cuenta de servicio (serviceAccountKey.json); la app móvil usa reglas Firestore.
# Despliegue de reglas: ver REGLAS_FIREBASE.txt y firestore.rules en esta carpeta.
firebase_conectado = False
firebase_proyecto_id = ""
if firebase_admin:
    try:
        if not os.path.exists(JSON_KEY):
            print(f"Firebase: falta {os.path.basename(JSON_KEY)} en la carpeta del programa.")
        elif not firebase_admin._apps:
            cred = credentials.Certificate(JSON_KEY)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_conectado = True
        try:
            firebase_proyecto_id = db.project
        except Exception:
            firebase_proyecto_id = ""
    except Exception as e:
        print(f"Modo Local (Firebase Offline): {e}")

class AlmacenApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SistemasPañol")
        self.root.geometry("1650x980")
        
        self.master_dict = {}
        self.config_df = pd.DataFrame()
        self.correos_df = pd.DataFrame()
        self.categoria_map = {} 
        self.search_cache = [] 
        
        self.save_lock = threading.RLock()
        self.master_file_path = BASE_DATOS_DEFAULT if os.path.exists(BASE_DATOS_DEFAULT) else MASTER_LEGACY

        self.meses_nombres = {
            1: "Enero.", 2: "Febrero.", 3: "Marzo.", 4: "Abril.", 5: "Mayo.", 6: "Junio.",
            7: "Julio.", 8: "Agosto.", 9: "Septiembre.", 10: "Octubre.", 11: "Noviembre.", 12: "Diciembre.",
        }
        self.tipos_comprobante = ["PAÑOL", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "PROYECTOS"]
        self.lista_operarios = ["AA", "AB", "AC", "AD", "AE", "AF", "AG"]
        self.sectores_operario = ["MANTENIMIENTO", "EDILICIO", "PRODUCCION", "PROYECTOS", "AUTOELEVADORES"]
        self.operarios_proyectos = ["MACCARONI", "VALENZUELA"]
        self.sector_operarios_map = {}

        # Debe inicializarse antes de auto_load_all() porque allí se evalúa el envío programado.
        self.scheduler_iniciado = False
        self.envio_auto_en_progreso = False
        self._formulario_orden_bloqueada = False
        self._salidas_pendientes = {}

        self.setup_ui()
        self.auto_load_all()
        self.iniciar_programador_730()

    def _set_cell_numeric_safe(self, df, idx, col, value):
        """Permite guardar números aunque la columna venga tipada como texto."""
        try:
            if col in df.columns and is_string_dtype(df[col]):
                df[col] = pd.to_numeric(df[col], errors='coerce')
        except Exception:
            pass
        df.at[idx, col] = value

    def _asegurar_sectores_base(self):
        # PAÑOL no es un sector operativo: se excluye del desplegable de Sector.
        vals = [
            str(v).strip().upper()
            for v in (self.sectores_operario or [])
            if str(v).strip() and str(v).strip().upper() != "PAÑOL"
        ]
        if "AUTOELEVADORES" not in vals:
            vals.append("AUTOELEVADORES")
        self.sectores_operario = vals

    def _formato_fecha_escrita(self, fecha_val):
        """Fecha escrita como 15/5/2026 (día y mes sin cero a la izquierda)."""
        if fecha_val is None:
            return ""
        try:
            if isinstance(fecha_val, pd.Timestamp):
                if pd.isna(fecha_val):
                    return ""
                fecha_val = fecha_val.date()
            elif isinstance(fecha_val, datetime):
                fecha_val = fecha_val.date()
            if isinstance(fecha_val, date):
                return f"{fecha_val.day}/{fecha_val.month}/{fecha_val.year}"
        except Exception:
            pass
        return ""

    def _nombre_mes_escrito(self, mes):
        """Mes como Mayo. (primera mayúscula, resto minúscula, punto final)."""
        try:
            return self.meses_nombres.get(int(mes), "")
        except (TypeError, ValueError):
            return ""

    def _fecha_sin_hora_str(self, fecha_val):
        """Devuelve fecha escrita (ej. 15/5/2026) sin hora para Excel e informes."""
        if fecha_val is None:
            return ""
        try:
            if isinstance(fecha_val, (datetime, date, pd.Timestamp)):
                out = self._formato_fecha_escrita(fecha_val)
                if out:
                    return out
            if isinstance(fecha_val, str):
                txt = fecha_val.strip()
                if not txt or txt.lower() in ('nan', 'nat', 'none'):
                    return ""
                dt = pd.to_datetime(txt, dayfirst=True, errors='coerce')
                if pd.isna(dt):
                    return txt
                return self._formato_fecha_escrita(dt)
            if isinstance(fecha_val, (int, float)) and not isinstance(fecha_val, bool):
                x = float(fecha_val)
                if pd.isna(x):
                    return ""
                if 20000 <= x <= 120000:
                    base = pd.Timestamp('1899-12-30')
                    dt = base + pd.Timedelta(days=x)
                    return self._formato_fecha_escrita(dt)
            dt = pd.to_datetime(fecha_val, dayfirst=True, errors='coerce')
            if pd.isna(dt):
                return "" if (isinstance(fecha_val, float) and pd.isna(fecha_val)) else str(fecha_val).strip()
            return self._formato_fecha_escrita(dt)
        except Exception:
            return str(fecha_val).strip()

    def _formato_pesos_ar(self, valor):
        """Formato tipo $ 1.449.001 (enteros, separador miles punto)."""
        try:
            x = float(valor)
        except (TypeError, ValueError):
            return "$ 0"
        entero = int(round(x))
        s = f"{abs(entero):,}".replace(',', '.')
        if entero < 0:
            return f"- $ {s}"
        return f"$ {s}"

    def _formato_precio_unit_ui(self, valor):
        """Precio unitario en pantalla: $, miles con punto, decimales con coma (lectura tipo AR)."""
        try:
            x = float(valor)
        except (TypeError, ValueError):
            return "$ 0"
        if pd.isna(x):
            return "$ 0"
        neg = x < 0
        x = abs(x)
        ent = int(x)
        frac = int(round((x - ent) * 100))
        if frac >= 100:
            ent += 1
            frac = 0
        s_int = f"{ent:,}".replace(',', '.')
        if abs(x - ent) < 1e-9 and frac == 0:
            body = s_int
        else:
            body = f"{s_int},{frac:02d}"
        if neg:
            return f"- $ {body}"
        return f"$ {body}"

    def _parse_precio_ui_a_float(self, txt):
        """Interpreta el texto del campo Precio Unit. ($, miles '.', decimales ',')."""
        if txt is None:
            return 0.0
        t = str(txt).strip().replace('$', '').replace(' ', '')
        if not t or t.lower() in ('nan', '-', '—'):
            return 0.0
        t = t.replace('\u00a0', '')
        if ',' in t and '.' in t:
            if t.rfind(',') > t.rfind('.'):
                t = t.replace('.', '').replace(',', '.')
            else:
                t = t.replace(',', '')
        elif ',' in t:
            parts = t.split(',')
            if len(parts[-1]) <= 2:
                t = ','.join(parts[:-1]).replace('.', '') + '.' + parts[-1]
            else:
                t = t.replace(',', '')
        else:
            last = t.split('.')[-1]
            if '.' in t and len(last) == 3 and len(t) > 4:
                t = t.replace('.', '')
        try:
            return float(t)
        except ValueError:
            return 0.0

    def _normalizar_tipo_comprobante_agrupacion(self, val):
        """PAÑ y PAÑOL se consideran el mismo tipo al agrupar totales (ej. reporte mensual)."""
        if pd.isna(val):
            return val
        s = str(val).strip().upper()
        if s in ("PAÑ", "PAÑOL"):
            return "PAÑOL"
        return str(val).strip()

    def _ruta_archivo_salidas_dia(self, fecha_d):
        return os.path.join(BASE_DIR, f"salidas_{fecha_d.strftime('%d-%m-%Y')}.xlsx")

    def _normalizar_texto_ui(self, txt):
        return str(txt or "").strip().lower()

    def _set_upper_entry(self, var):
        val = var.get()
        up = val.upper()
        if val != up:
            var.set(up)

    def _enforzar_mayusculas_campos_solicitud(self):
        """Máquina y operario (texto libre) en mayúsculas; orden se deja tal cual el usuario."""
        for v in (self.maquina_var, self.ope_det_var):
            v.trace_add("write", lambda *_args, vv=v: self._set_upper_entry(vv))

    def _es_columna_monto(self, col_name):
        n = self._norm_header_imp(str(col_name)).replace(" ", "_")
        return n in {"precio_unitario", "monto_total_salida"}

    def _es_columna_numero_entero_excel(self, col_name):
        n = self._norm_header_imp(str(col_name)).replace(" ", "_")
        return n in {"numero_orden", "año", "ano"}

    def _ruta_archivo_salida_activos(self):
        if os.path.exists(SALIDA_ACTIVOS_PATH):
            return SALIDA_ACTIVOS_PATH
        if os.path.exists(SEGUIMIENTO_REPARACION_LEGACY):
            return SEGUIMIENTO_REPARACION_LEGACY
        return SALIDA_ACTIVOS_PATH

    def _normalizar_orden_para_excel(self, val):
        s = str(val or "").strip()
        if not s:
            return None
        s = s.replace(",", ".")
        try:
            f = float(s)
            if f == int(f):
                return int(f)
            return f
        except ValueError:
            return s

    def _normalizar_criticidad_maestro(self, val):
        v = str(val or "").strip().upper().replace("_", " ")
        if not v or v in ("NAN", "NONE"):
            return "BASE"
        if "CRIT" in v:
            return "CRÍTICO"
        if "ALTA" in v and ("FREQ" in v.replace(" ", "") or "FRECUENCIA" in v):
            return "ALTA FRECUENCIA"
        if v in CRITICIDAD_OPCIONES_MAESTRO:
            return v
        return "BASE"

    def _col_precio_unitario_df(self, df):
        if df is None or df.empty:
            return None
        for c in df.columns:
            nh = self._norm_header_imp(str(c)).replace(" ", "_")
            if nh == "precio_unitario":
                return c
        for c in df.columns:
            nh = self._norm_header_imp(str(c))
            if nh == "costo.uni" or nh == "costouni" or ("costo" in nh and "uni" in nh):
                return c
        for c in df.columns:
            if "precio" in self._norm_header_imp(str(c)):
                return c
        return None

    def _limpiar_columnas_precio_duplicadas_df(self, df):
        """Mantiene precio_unitario; elimina costo.uni u otras columnas de precio duplicadas."""
        if df is None or df.empty:
            return df
        out = df.copy()
        precio_cols = []
        for c in out.columns:
            nh = self._norm_header_imp(str(c)).replace(" ", "_")
            if nh in ("precio_unitario", "costo.uni", "costouni") or (
                "costo" in nh and "uni" in nh
            ) or nh == "precio":
                precio_cols.append(c)
        if len(precio_cols) <= 1:
            return out
        keep = None
        for c in precio_cols:
            if self._norm_header_imp(str(c)).replace(" ", "_") == "precio_unitario":
                keep = c
                break
        if keep is None:
            keep = precio_cols[0]
        for c in precio_cols:
            if c != keep:
                out = out.drop(columns=[c])
        if keep != "precio_unitario":
            out = out.rename(columns={keep: "precio_unitario"})
        return out

    def _apply_uppercase_to_df(self, df):
        if df is None or df.empty:
            return df
        out = df.copy()
        skip_cols = set()
        for c in out.columns:
            nh = self._norm_header_imp(str(c)).replace(" ", "_")
            if nh == "mes":
                skip_cols.add(c)
        for c in out.columns:
            if c in skip_cols:
                continue
            if pd.api.types.is_object_dtype(out[c]):
                out[c] = out[c].apply(lambda x: str(x).upper() if pd.notna(x) else x)
        return out

    def _aplicar_formato_monto_ws(self, ws, wb, df):
        money_fmt = wb.add_format({'num_format': '$ #,##0.00', 'border': 1})
        int_fmt = wb.add_format({'num_format': '0', 'border': 1})
        for col_num, col_name in enumerate(df.columns):
            if self._es_columna_monto(col_name):
                for r in range(len(df)):
                    val = pd.to_numeric(df.iloc[r, col_num], errors='coerce')
                    ws.write_number(r + 1, col_num, 0.0 if pd.isna(val) else float(val), money_fmt)
            elif self._es_columna_numero_entero_excel(col_name):
                for r in range(len(df)):
                    val = df.iloc[r, col_num]
                    num = pd.to_numeric(val, errors='coerce')
                    if pd.notna(num):
                        ws.write_number(r + 1, col_num, int(num) if num == int(num) else float(num), int_fmt)
                    else:
                        txt = str(val).strip() if pd.notna(val) else ""
                        ws.write(r + 1, col_num, txt, int_fmt)

    def _cargar_relaciones_sector_operario_desde_config(self):
        self.sector_operarios_map = {}
        if self.config_df is None or self.config_df.empty:
            self._asegurar_sectores_base()
            return
        cols_norm = {self._norm_header_imp(str(c)).replace(" ", "_"): c for c in self.config_df.columns}
        col_sector = cols_norm.get("sector")
        col_operario = cols_norm.get("operario") or cols_norm.get("operarios")
        if not col_sector or not col_operario:
            return
        tmp_map = {}
        for _, row in self.config_df.iterrows():
            s = str(row.get(col_sector, "")).strip()
            o = str(row.get(col_operario, "")).strip()
            if not s:
                continue
            s_key = self._resolver_sector_texto(s) or self._normalizar_texto_ui(s)
            if s_key not in tmp_map:
                tmp_map[s_key] = []
            if o and o not in tmp_map[s_key]:
                tmp_map[s_key].append(o)
        self.sector_operarios_map = tmp_map
        self._asegurar_sectores_base()

    def _normalizar_df_salidas_gastos(self, df_raw, fecha_contexto=None):
        cols_lower = {str(c).strip().lower(): c for c in df_raw.columns}
        col_operario = cols_lower.get("operario")
        col_monto = cols_lower.get("monto_total_salida")
        if not col_operario or not col_monto:
            return None, None, None, "Faltan columnas OPERARIO o MONTO_TOTAL_SALIDA."
        df = df_raw.copy()
        if "FECHA" in df.columns:
            df["FECHA"] = df["FECHA"].apply(self._fecha_sin_hora_str)
            if fecha_contexto is not None:
                fb = self._formato_fecha_escrita(fecha_contexto) if isinstance(fecha_contexto, (date, datetime)) else str(fecha_contexto)
                bad = df["FECHA"].astype(str).str.strip()
                mask_fill = bad.isin(["", "nan", "NaT", "None", "NaN"]) | df["FECHA"].isna()
                df.loc[mask_fill, "FECHA"] = fb
        df[col_monto] = pd.to_numeric(df[col_monto], errors='coerce').fillna(0.0)
        col_sector_guardado = cols_lower.get("sector")
        if col_sector_guardado and col_sector_guardado in df.columns:
            # Respetar el sector elegido al registrar (OPERARIO suele ser nombre de persona, no el sector)
            def _sector_por_fila(row):
                v = row.get(col_sector_guardado)
                if pd.notna(v) and str(v).strip():
                    return str(v).strip().upper()
                return self._clasificar_sector(row[col_operario])

            df["SECTOR"] = df.apply(_sector_por_fila, axis=1)
        else:
            df["SECTOR"] = df[col_operario].apply(self._clasificar_sector)
        df = self._deduplicar_filas_movimientos_gastos(df)
        return df, col_operario, col_monto, ""

    def _deduplicar_filas_movimientos_gastos(self, df):
        """Quita líneas duplicadas (mismo movimiento repetido en master + diario o filas gemelas)."""
        if df is None or df.empty or len(df) < 2:
            return df
        cols_lower = {str(c).strip().lower(): c for c in df.columns}

        def ccol(*names):
            for n in names:
                if n.lower() in cols_lower:
                    return cols_lower[n.lower()]
            return None

        c_fecha = ccol("fecha")
        c_cod = ccol("codigo")
        c_cant = ccol("cantidad")
        c_monto = ccol("monto_total_salida")
        c_op = ccol("operario")
        c_ord = ccol("numero_orden")
        c_comp = ccol("tipo_comprobante")
        c_sec = ccol("sector")
        bloques = []
        if c_fecha:
            bloques.append(df[c_fecha].astype(str).str.strip())
        if c_cod:
            bloques.append(df[c_cod].astype(str).str.strip().str.upper())
        if c_cant:
            bloques.append(pd.to_numeric(df[c_cant], errors="coerce").round(8))
        if c_monto:
            bloques.append(pd.to_numeric(df[c_monto], errors="coerce").round(4))
        if c_sec:
            bloques.append(df[c_sec].astype(str).str.strip().str.upper())
        if c_op:
            bloques.append(df[c_op].astype(str).str.strip().str.upper())
        if c_ord:
            bloques.append(df[c_ord].astype(str).str.strip().str.upper())
        if c_comp:
            bloques.append(df[c_comp].astype(str).str.strip().str.upper())
        if not bloques:
            return df.drop_duplicates().reset_index(drop=True)
        mat = pd.concat(bloques, axis=1)
        ok = ~mat.duplicated(keep="first")
        return df[ok].reset_index(drop=True)

    def _filtrar_master_salidas_por_dia(self, df_raw, fecha_d):
        """Filtra filas de master_salidas cuya FECHA coincide con fecha_d (incl. números seriales Excel)."""
        if df_raw is None or df_raw.empty or "FECHA" not in df_raw.columns:
            return None
        serie = df_raw["FECHA"]
        fd = pd.to_datetime(serie, dayfirst=True, errors='coerce')
        mask_nat = fd.isna() & serie.notna()
        if mask_nat.any():
            num = pd.to_numeric(serie[mask_nat], errors='coerce')
            fd_alt = pd.to_datetime(num, unit='D', origin='1899-12-30', errors='coerce')
            fd = fd.copy()
            fd.loc[mask_nat] = fd_alt
        mask = fd.dt.date == fecha_d
        sub = df_raw.loc[mask].copy()
        return sub if not sub.empty else None

    def _cargar_movimientos_fecha_gastos(self, fecha_d):
        """Usa primero el Excel diario `salidas_DD-MM-AAAA.xlsx` junto al ejecutable; si no existe o está vacío, master_salidas."""
        path_diario = self._ruta_archivo_salidas_dia(fecha_d)
        err_master = None

        if os.path.exists(path_diario):
            try:
                df_dia = pd.read_excel(path_diario)
            except Exception as ex:
                return None, None, None, f"No se pudo leer {path_diario}: {ex}"
            if df_dia is not None and not df_dia.empty:
                return self._normalizar_df_salidas_gastos(df_dia, fecha_contexto=fecha_d)

        if os.path.exists(HISTORIAL_PATH):
            try:
                df_master = pd.read_excel(HISTORIAL_PATH)
            except Exception as ex:
                df_master = None
                err_master = str(ex)
            else:
                sub_m = self._filtrar_master_salidas_por_dia(df_master, fecha_d)
                if sub_m is not None and not sub_m.empty:
                    return self._normalizar_df_salidas_gastos(sub_m, fecha_contexto=fecha_d)

        if err_master:
            return None, None, None, f"No se pudo leer master_salidas: {err_master}"
        return None, None, None, (
            f"No hay datos para {self._formato_fecha_escrita(fecha_d)} "
            f"(sin archivo {os.path.basename(path_diario)} ni filas en master_salidas)."
        )

    def _coleccionar_sectores_presentes_en_mes(self, fecha_ref):
        """Todos los códigos de sector que aparecen en movimientos del mes (hasta fecha_ref)."""
        year, month = fecha_ref.year, fecha_ref.month
        d = date(year, month, 1)
        codes = set()
        while d.month == month and d <= fecha_ref:
            df, _, _, _ = self._cargar_movimientos_fecha_gastos(d)
            if df is not None and not df.empty and "SECTOR" in df.columns:
                codes.update(str(s).strip().upper() for s in df["SECTOR"].dropna().unique())
            d += timedelta(days=1)
        return codes

    def _orden_sectores_para_informe(self, codigos_presentes):
        """Orden fijo conocido primero; el resto alfabético por código."""
        if not codigos_presentes:
            return list(ORDEN_SECTORES_GASTOS)
        orden = []
        vistos = set()
        for code, etiqueta in ORDEN_SECTORES_GASTOS:
            if code in codigos_presentes:
                orden.append((code, etiqueta))
                vistos.add(code)
        extras = sorted(c for c in codigos_presentes if c not in vistos)
        for code in extras:
            orden.append((code, code.replace("_", " ").title()))
        return orden

    def _totales_mes_por_dia_y_sector(self, fecha_ref, orden_sectores):
        """Para cada día del mes hasta fecha_ref: suma de montos por sector (claves según orden_sectores + dinámicas)."""
        year, month = fecha_ref.year, fecha_ref.month
        dias_mes = []
        d = date(year, month, 1)
        while d.month == month and d <= fecha_ref:
            dias_mes.append(d)
            d += timedelta(days=1)
        codes_base = [c for c, _ in orden_sectores]
        totales = {}
        for fd in dias_mes:
            df, _, col_m, err = self._cargar_movimientos_fecha_gastos(fd)
            key = self._formato_fecha_escrita(fd)
            totales[key] = {c: 0.0 for c in codes_base}
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                sec = row["SECTOR"]
                if sec not in totales[key]:
                    totales[key][sec] = 0.0
                totales[key][sec] += float(row[col_m])
        return totales, dias_mes

    def _estilo_sector_html(self, code_sector):
        code = str(code_sector or "").strip().upper()
        return ESTILO_SECTOR_HTML.get(code, {
            'bg': '#F8F9F9', 'border': '#BDC3C7', 'title': '#2C3E50', 'th': '#5D6D7E',
        })

    def _tabla_html_simple(self, titulo, cabeceras, filas, code_sector=None):
        esc = html.escape
        est = self._estilo_sector_html(code_sector) if code_sector else {
            'bg': '#FFFFFF', 'border': '#ccc', 'title': '#222', 'th': '#1F4E78',
        }
        th = ''.join(
            f'<th style="padding:6px;background:{est["th"]};color:#fff;border:1px solid {est["border"]};">'
            f'{esc(str(h))}</th>'
            for h in cabeceras
        )
        trs = []
        for fila in filas:
            tds = ''.join(
                f'<td style="padding:4px 8px;border:1px solid {est["border"]};background:{est["bg"]};">'
                f'{esc(str(c))}</td>'
                for c in fila
            )
            trs.append(f'<tr>{tds}</tr>')
        body = ''.join(trs)
        return (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 8px 0;'
            f'color:{est["title"]};"><b>{esc(titulo)}</b></p>'
            f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;'
            f'margin-bottom:16px;border:2px solid {est["border"]};">'
            f'<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'
        )

    def _tabla_html_coloreada(self, titulo, cabeceras, filas, leyenda_dias=True):
        """Tabla HTML donde cada fila trae su color de fondo.
        `filas` = lista de tuplas (bg_hex, (celda1, celda2, ...))."""
        esc = html.escape
        borde = '#999'
        th = ''.join(
            f'<th style="padding:6px;background:#1F4E78;color:#fff;border:1px solid {borde};">'
            f'{esc(str(h))}</th>'
            for h in cabeceras
        )
        trs = []
        for bg, fila in filas:
            tds = ''.join(
                f'<td style="padding:4px 8px;border:1px solid {borde};background:{bg};color:#1a1a1a;">'
                f'{esc(str(c))}</td>'
                for c in fila
            )
            trs.append(f'<tr>{tds}</tr>')
        leyenda = ''
        if leyenda_dias:
            leyenda = (
                '<p style="font-family:Arial,sans-serif;font-size:12px;margin:4px 0 10px 0;color:#333;">'
                'Referencia: '
                '<span style="background:#C6EFCE;padding:2px 8px;border:1px solid #999;">≤ 21 días</span> &nbsp; '
                '<span style="background:#FFEB9C;padding:2px 8px;border:1px solid #999;">22 a 30 días</span> &nbsp; '
                '<span style="background:#FFC7CE;padding:2px 8px;border:1px solid #999;">+ de 30 días</span></p>'
            )
        return (
            f'<p style="font-family:Arial,sans-serif;font-size:14px;margin:16px 0 8px 0;'
            f'color:#222;"><b>{esc(titulo)}</b></p>'
            f'{leyenda}'
            f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;'
            f'margin-bottom:16px;border:2px solid {borde};">'
            f'<thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
        )

    def _bloque_resumen_sector_html(self, num, etiqueta, code, g_dia, acum):
        esc = html.escape
        est = self._estilo_sector_html(code)
        return (
            f'<div style="font-family:Arial,sans-serif;margin:12px 0;padding:12px 14px;'
            f'background:{est["bg"]};border-left:5px solid {est["border"]};border-radius:4px;">'
            f'<p style="margin:0 0 6px 0;font-size:15px;color:{est["title"]};">'
            f'<b>{num}. {esc(etiqueta)}</b></p>'
            f'<p style="margin:0;font-size:13px;color:#333;">'
            f'Gasto del día: <b>{esc(self._formato_pesos_ar(g_dia))}</b><br/>'
            f'Total acumulado del mes: <b>{esc(self._formato_pesos_ar(acum))}</b></p></div>'
        )

    def _normalizar_linea_gasto(self, val):
        """Agrupa comprobante como línea (L1…L7, PAÑOL, etc.) para totales de mantenimiento."""
        if pd.isna(val):
            return "OTROS"
        s = str(val).strip().upper()
        if not s:
            return "OTROS"
        norm = self._normalizar_tipo_comprobante_agrupacion(val)
        if norm:
            s = str(norm).strip().upper()
        if s in ("PAÑ", "PAÑOL"):
            return "PAÑOL"
        for ln in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
            if s == ln or s.startswith(ln + " "):
                return ln
        if s == "PROYECTOS":
            return "PROYECTOS"
        return s

    def _orden_lineas_gasto(self):
        base = ["PAÑOL"] + [f"L{i}" for i in range(1, 8)] + ["PROYECTOS"]
        return base

    def _gastos_por_linea_mantenimiento_mes(self, fecha_ref):
        """Total gastado por línea (comprobante) en mantenimiento, mes en curso hasta fecha_ref."""
        year, month = fecha_ref.year, fecha_ref.month
        d = date(year, month, 1)
        bloques = []
        while d.month == month and d <= fecha_ref:
            df_d, _, _, _ = self._cargar_movimientos_fecha_gastos(d)
            if df_d is not None and not df_d.empty:
                bloques.append(df_d)
            d += timedelta(days=1)
        if not bloques:
            return []
        df = pd.concat(bloques, ignore_index=True)
        df_m = df[df["SECTOR"].astype(str).str.upper() == "MANTENIMIENTO"].copy()
        if df_m.empty or "TIPO_COMPROBANTE" not in df_m.columns:
            return []
        col_m = "MONTO_TOTAL_SALIDA"
        df_m[col_m] = pd.to_numeric(df_m[col_m], errors="coerce").fillna(0.0)
        df_m["_LINEA"] = df_m["TIPO_COMPROBANTE"].apply(self._normalizar_linea_gasto)
        grp = df_m.groupby("_LINEA", dropna=False)[col_m].sum()
        orden_pref = self._orden_lineas_gasto()
        filas = []
        vistos = set()
        for ln in orden_pref:
            if ln in grp.index:
                filas.append((ln, float(grp[ln])))
                vistos.add(ln)
        for ln in sorted(grp.index, key=lambda x: str(x)):
            if ln not in vistos:
                filas.append((str(ln), float(grp[ln])))
        return filas

    def _parse_fecha_ui_a_date(self, val):
        if val is None:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, pd.Timestamp):
            if pd.isna(val):
                return None
            return val.date()
        txt = str(val).strip()
        if not txt or txt.lower() in ("nan", "nat", "none", "-", ""):
            return None
        dt = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.date()

    def _calcular_dias_fuera_planta(self, fecha_salida, fecha_regreso=None):
        fs = self._parse_fecha_ui_a_date(fecha_salida)
        if not fs:
            return 0
        fr = self._parse_fecha_ui_a_date(fecha_regreso)
        fin = fr if fr else date.today()
        return max(0, (fin - fs).days)

    def _normalizar_celda_fecha_seguimiento(self, val):
        """Fecha de salida/regreso: vacío real o formato día/mes/año para Excel y listas."""
        if val is None:
            return ""
        try:
            if pd.isna(val):
                return ""
        except (TypeError, ValueError):
            pass
        txt = str(val).strip() if not isinstance(val, (datetime, date, pd.Timestamp)) else ""
        if txt.lower() in ("nan", "nat", "none", "-", "", "0", "0.0"):
            if not isinstance(val, (datetime, date, pd.Timestamp)):
                return ""
        d = self._parse_fecha_ui_a_date(val)
        if d is None or d.year < 1990:
            return ""
        return self._fecha_sin_hora_str(d)

    def _tiene_fecha_regreso_valida(self, val):
        """Fecha de regreso real (no vacía ni artefacto de Excel)."""
        return bool(self._normalizar_celda_fecha_seguimiento(val))

    def _normalizar_cantidad_seguimiento(self, val):
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return 1
            s = str(val).strip().replace(",", ".")
            if not s or s.lower() in ("nan", "-"):
                return 1
            return max(1, int(float(s)))
        except (TypeError, ValueError):
            return 1

    def _normalizar_numero_documento_seguimiento(self, val):
        """Pedido, OC y remito sin sufijo .0 de Excel."""
        if val is None:
            return ""
        try:
            if pd.isna(val):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            x = float(val)
            if pd.isna(x):
                return ""
            if abs(x - round(x)) < 1e-9:
                return str(int(round(x)))
            return str(val).strip()
        s = str(val).strip()
        if not s or s.lower() in ("nan", "nat", "none", "-"):
            return ""
        if s.endswith(".0"):
            base = s[:-2]
            if base.isdigit() or (base.startswith("-") and base[1:].isdigit()):
                return base
        return s.upper()

    def _texto_ui(self, val, vacio="-"):
        """Evita mostrar nan/None en pantalla, mail y tablas."""
        if val is None:
            return vacio
        try:
            if pd.isna(val):
                return vacio
        except (TypeError, ValueError):
            pass
        s = str(val).strip()
        if not s or s.lower() in ("nan", "nat", "none", "<na>"):
            return vacio
        return s

    def _columnas_seguimiento_planta(self):
        return [
            "NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO", "SECTOR", "CODIGO", "EQUIPO_REPUESTO", "CANTIDAD",
            "NRO_SERIE", "FECHA_SALIDA", "PROVEEDOR", "FECHA_REGRESO", "ESTADO_AL_INGRESO",
            "OBSERVACIONES", "DIAS_FUERA", "ESTADO",
        ]

    def _label_con_asterisco_obligatorio(self, parent, texto, row, column=0, sticky="e", **grid_kw):
        """Etiqueta de campo obligatorio con asterisco rojo."""
        padx = grid_kw.pop("padx", 5)
        pady = grid_kw.pop("pady", 4)
        celda = ttk.Frame(parent)
        celda.grid(row=row, column=column, sticky=sticky, padx=padx, pady=pady, **grid_kw)
        ttk.Label(celda, text=texto).pack(side="left")
        tk.Label(celda, text=" *", fg="#c0392b", font=("Arial", 11, "bold")).pack(side="left")
        return celda

    def _mapear_columnas_excel_seguimiento(self, df):
        """Traduce encabezados del Excel (con espacios) a nombres internos del sistema."""
        if df is None or df.empty:
            return df
        canon = set(self._columnas_seguimiento_planta())
        alias = {
            "DESCRIPCION": "EQUIPO_REPUESTO",
            "EQUIPO_REPUESTO": "EQUIPO_REPUESTO",
            "EQUIPO/REPUESTO": "EQUIPO_REPUESTO",
            "FALLAS/OBSERVACIONES": "OBSERVACIONES",
            "NRO_DE_SERIE": "NRO_SERIE",
            "NUMERO_DE_PEDIDO": "NUMERO_PEDIDO",
            "NUMERO_DE_OC": "NUMERO_OC",
            "NUMERO_DE_REMITO": "NUMERO_REMITO",
            "NRO_REMITO": "NUMERO_REMITO",
            "CANT": "CANTIDAD",
            "DIAS": "DIAS_FUERA",
            "ESTADO": "ESTADO",
            "ESTADO_AL_INGRESO": "ESTADO_AL_INGRESO",
            "ESTADO_INGRESO": "ESTADO_AL_INGRESO",
            "SECTOR": "SECTOR",
        }
        nuevas = {}
        for c in df.columns:
            key = str(c).strip().upper().replace(" ", "_")
            dest = alias.get(key, key)
            if dest in canon:
                nuevas[c] = dest
            elif key in canon:
                nuevas[c] = key
        if nuevas:
            df = df.rename(columns=nuevas)
        return df

    def _normalizar_df_seguimiento_planta(self, df):
        cols = self._columnas_seguimiento_planta()
        out = df.copy() if df is not None else pd.DataFrame()
        if "DESCRIPCION" in out.columns and "EQUIPO_REPUESTO" not in out.columns:
            out["EQUIPO_REPUESTO"] = out["DESCRIPCION"]
        for c in cols:
            if c not in out.columns:
                out[c] = ""
        out = out[cols].copy()
        for c in out.columns:
            if c in ("DIAS_FUERA", "ESTADO"):
                continue
            if c == "CANTIDAD":
                out[c] = out[c].apply(self._normalizar_cantidad_seguimiento)
            elif c in ("FECHA_SALIDA", "FECHA_REGRESO"):
                out[c] = out[c].apply(self._normalizar_celda_fecha_seguimiento)
            elif c in ("NUMERO_PEDIDO", "NUMERO_OC", "NUMERO_REMITO"):
                out[c] = out[c].apply(self._normalizar_numero_documento_seguimiento)
            else:
                out[c] = out[c].apply(lambda x: "" if pd.isna(x) else str(x).strip())
        dias_list = []
        for i in out.index:
            est = str(out.at[i, "ESTADO"]).strip().upper()
            if not est:
                if self._tiene_fecha_regreso_valida(out.at[i, "FECHA_REGRESO"]):
                    est = "INGRESADO_A_PLANTA"
                else:
                    est = "FUERA_DE_PLANTA"
                out.at[i, "ESTADO"] = est
            if est == "FUERA_DE_PLANTA":
                out.at[i, "FECHA_REGRESO"] = ""
                out.at[i, "ESTADO_AL_INGRESO"] = ""
            elif est == "INGRESADO_A_PLANTA" and not self._tiene_fecha_regreso_valida(out.at[i, "FECHA_REGRESO"]):
                out.at[i, "FECHA_REGRESO"] = self._normalizar_celda_fecha_seguimiento(date.today())
            fs = out.at[i, "FECHA_SALIDA"]
            fr = out.at[i, "FECHA_REGRESO"]
            fr_ok = est == "INGRESADO_A_PLANTA" and self._tiene_fecha_regreso_valida(fr)
            dias_list.append(self._calcular_dias_fuera_planta(fs, fr if fr_ok else None))
        out["DIAS_FUERA"] = dias_list
        return out

    def _seguimiento_fila_pendiente(self, row):
        est = self._texto_ui(row.get("ESTADO"), vacio="").upper().replace(" ", "_")
        if est == "INGRESADO_A_PLANTA":
            return False
        if est == "FUERA_DE_PLANTA":
            return True
        return not self._tiene_fecha_regreso_valida(row.get("FECHA_REGRESO"))

    def _etiqueta_equipo_seguimiento(self, row):
        eq = self._texto_ui(row.get("EQUIPO_REPUESTO"), vacio="(sin nombre)")
        cod = self._texto_ui(row.get("CODIGO"), vacio="")
        serie = self._texto_ui(row.get("NRO_SERIE"), vacio="")
        cant = self._normalizar_cantidad_seguimiento(row.get("CANTIDAD"))
        partes = [eq]
        if cant > 1:
            partes.append(f"x{cant}")
        if cod and cod != "-":
            partes.append(f"Cód. {cod}")
        if serie and serie != "-":
            partes.append(f"S/N {serie}")
        return " | ".join(partes)

    def _clave_agrupacion_seguimiento(self, row):
        """Agrupa por OC, remito o pedido (en ese orden) si el número está cargado."""
        oc = self._texto_ui(row.get("NUMERO_OC"), vacio="")
        rem = self._texto_ui(row.get("NUMERO_REMITO"), vacio="")
        ped = self._texto_ui(row.get("NUMERO_PEDIDO"), vacio="")
        if oc and oc != "-":
            return ("OC", oc)
        if rem and rem != "-":
            return ("REMITO", rem)
        if ped and ped != "-":
            return ("PEDIDO", ped)
        return None

    def _seg_iid_a_indice_df(self, iid):
        if not iid or str(iid).startswith("grp_"):
            return None
        try:
            return int(iid)
        except ValueError:
            return None

    def _cargar_df_seguimiento_reparacion(self):
        cols = self._columnas_seguimiento_planta()
        ruta = self._ruta_archivo_salida_activos()
        if os.path.exists(ruta):
            try:
                xls = pd.ExcelFile(ruta)
                partes = []
                for nombre in ("FUERA_DE_PLANTA", "INGRESADO_A_PLANTA"):
                    if nombre in xls.sheet_names:
                        partes.append(pd.read_excel(xls, sheet_name=nombre))
                if not partes:
                    partes.append(pd.read_excel(xls, sheet_name=xls.sheet_names[0]))
                df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=cols)
                df = self._mapear_columnas_excel_seguimiento(df)
            except Exception:
                df = pd.DataFrame(columns=cols)
        else:
            df = pd.DataFrame(columns=cols)
        return self._normalizar_df_seguimiento_planta(df)

    def _color_dias_fuera(self, dias):
        """Devuelve el color de fondo según los días fuera de planta.
        >30 días: rojo · >21 días: amarillo/naranja · resto: verde."""
        try:
            d = int(float(dias))
        except (ValueError, TypeError):
            d = 0
        if d > 30:
            return '#FFC7CE'
        if d > 21:
            return '#FFEB9C'
        return '#C6EFCE'

    def _escribir_hoja_excel_formateada(self, ws, wb, df, ordenar_por_dias=False, colorear_por_dias=False):
        df_excel = self._apply_uppercase_to_df(df) if not df.empty else df
        if ordenar_por_dias and not getattr(df_excel, "empty", True) and "DIAS_FUERA" in df_excel.columns:
            df_excel = df_excel.copy()
            df_excel["__orden_dias"] = pd.to_numeric(df_excel["DIAS_FUERA"], errors="coerce").fillna(0)
            df_excel = (
                df_excel.sort_values("__orden_dias", ascending=False)
                .drop(columns=["__orden_dias"])
                .reset_index(drop=True)
            )
        header_fmt = wb.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1, 'align': 'center'})
        base_fmt = wb.add_format({'border': 1})
        date_fmt = wb.add_format({'num_format': 'dd/mm/yyyy', 'border': 1, 'align': 'center'})
        dias_fmt = wb.add_format({'border': 1, 'bold': True, 'font_color': '#C00000', 'align': 'center'})
        fmt_cache = {}

        def _fmt(role, bg):
            key = (role, bg)
            if key not in fmt_cache:
                spec = {'border': 1}
                if role == 'date':
                    spec['num_format'] = 'dd/mm/yyyy'
                    spec['align'] = 'center'
                elif role == 'dias':
                    spec['bold'] = True
                    spec['align'] = 'center'
                if bg:
                    spec['bg_color'] = bg
                fmt_cache[key] = wb.add_format(spec)
            return fmt_cache[key]

        cols_hoja = list(df.columns) if len(getattr(df, "columns", [])) else self._columnas_seguimiento_planta()
        if getattr(df_excel, "empty", True):
            for col_num, col_name in enumerate(cols_hoja):
                ws.write(0, col_num, str(col_name).replace("_", " "), header_fmt)
            return
        bg_filas = []
        if colorear_por_dias and "DIAS_FUERA" in df_excel.columns:
            for r in range(len(df_excel)):
                bg_filas.append(self._color_dias_fuera(df_excel["DIAS_FUERA"].iloc[r]))
        else:
            bg_filas = [None] * len(df_excel)
        for col_num, col_name in enumerate(df_excel.columns):
            titulo = str(col_name).replace("_", " ")
            ws.write(0, col_num, titulo, header_fmt)
            max_len = len(titulo)
            for r in range(len(df_excel)):
                val = df_excel.iloc[r, col_num]
                txt = self._texto_ui(val, vacio="")
                bg = bg_filas[r]
                f_base = _fmt('base', bg) if bg else base_fmt
                f_date = _fmt('date', bg) if bg else date_fmt
                f_dias = _fmt('dias', bg) if bg else dias_fmt
                if str(col_name) == "DIAS_FUERA":
                    try:
                        ws.write_number(r + 1, col_num, int(txt) if txt not in ("", "-") else 0, f_dias)
                    except ValueError:
                        ws.write(r + 1, col_num, txt, f_base)
                elif str(col_name) == "CANTIDAD":
                    try:
                        ws.write_number(r + 1, col_num, self._normalizar_cantidad_seguimiento(val), f_base)
                    except ValueError:
                        ws.write(r + 1, col_num, txt, f_base)
                elif str(col_name) in ("FECHA_SALIDA", "FECHA_REGRESO"):
                    d = self._parse_fecha_ui_a_date(val)
                    if d:
                        ws.write_datetime(r + 1, col_num, datetime(d.year, d.month, d.day), f_date)
                    else:
                        ws.write(r + 1, col_num, "", f_base)
                else:
                    ws.write(r + 1, col_num, txt, f_base)
                max_len = max(max_len, len(str(txt)))
            ws.set_column(col_num, col_num, min(max(12, int(max_len) + 2), 42), base_fmt)
        if len(df_excel) > 0 and len(df_excel.columns) > 0:
            ws.autofilter(0, 0, len(df_excel), len(df_excel.columns) - 1)
        ws.freeze_panes(1, 0)

    def _guardar_df_seguimiento_reparacion(self, df):
        cols = self._columnas_seguimiento_planta()
        with self.save_lock:
            df_save = self._normalizar_df_seguimiento_planta(df)
            if df_save.empty:
                df_fuera = pd.DataFrame(columns=cols)
                df_ingresado = pd.DataFrame(columns=cols)
            else:
                mask_pend = df_save.apply(self._seguimiento_fila_pendiente, axis=1)
                df_fuera = df_save[mask_pend].copy()
                df_ingresado = df_save[~mask_pend].copy()
            if df_fuera.empty:
                df_fuera = pd.DataFrame(columns=cols)
            if df_ingresado.empty:
                df_ingresado = pd.DataFrame(columns=cols)
            with pd.ExcelWriter(SALIDA_ACTIVOS_PATH, engine='xlsxwriter') as writer:
                wb = writer.book
                for nombre, df_h in (("FUERA_DE_PLANTA", df_fuera), ("INGRESADO_A_PLANTA", df_ingresado)):
                    pd.DataFrame(columns=cols).to_excel(writer, sheet_name=nombre, index=False)
                    es_fuera = nombre == "FUERA_DE_PLANTA"
                    self._escribir_hoja_excel_formateada(
                        writer.sheets[nombre], wb, df_h,
                        ordenar_por_dias=es_fuera, colorear_por_dias=es_fuera,
                    )

    def _columnas_tree_seguimiento_fuera(self):
        return (
            "Pedido", "OC", "Remito", "Sector", "Código", "Equipo/repuesto", "Cant.", "Serie",
            "Salida", "Proveedor", "Días", "Fallas/Obs.",
        )

    def _columnas_tree_seguimiento_ingresado(self):
        return (
            "Pedido", "OC", "Remito", "Sector", "Código", "Equipo/repuesto", "Cant.", "Serie", "Salida",
            "Regreso", "Estado ingreso", "Proveedor", "Días", "Fallas/Obs.",
        )

    def _anchos_tree_seguimiento(self, incluir_regreso=False):
        if incluir_regreso:
            return (52, 48, 52, 72, 60, 125, 36, 62, 68, 68, 90, 82, 36, 82)
        return (52, 48, 52, 72, 60, 125, 36, 62, 68, 82, 36, 82)

    def _valores_fila_tree_seguimiento(self, row, incluir_regreso=False):
        dias = int(row.get("DIAS_FUERA", 0) or 0)
        cant = self._normalizar_cantidad_seguimiento(row.get("CANTIDAD"))
        base = (
            self._normalizar_numero_documento_seguimiento(row.get("NUMERO_PEDIDO")) or "-",
            self._normalizar_numero_documento_seguimiento(row.get("NUMERO_OC")) or "-",
            self._normalizar_numero_documento_seguimiento(row.get("NUMERO_REMITO")) or "-",
            self._texto_ui(row.get("SECTOR")),
            self._texto_ui(row.get("CODIGO")),
            self._texto_ui(row.get("EQUIPO_REPUESTO")),
            cant,
            self._texto_ui(row.get("NRO_SERIE")),
            self._fecha_sin_hora_str(row.get("FECHA_SALIDA")),
        )
        if incluir_regreso:
            return base + (
                self._fecha_sin_hora_str(row.get("FECHA_REGRESO")),
                self._texto_ui(row.get("ESTADO_AL_INGRESO")),
                self._texto_ui(row.get("PROVEEDOR")),
                dias,
                self._texto_ui(row.get("OBSERVACIONES")),
            )
        return base + (
            self._texto_ui(row.get("PROVEEDOR")),
            dias,
            self._texto_ui(row.get("OBSERVACIONES")),
        )

    def _configurar_tree_seguimiento(self, tree, incluir_regreso=False):
        cols = self._columnas_tree_seguimiento_ingresado() if incluir_regreso else self._columnas_tree_seguimiento_fuera()
        tree.configure(columns=cols, show="tree headings", selectmode="extended")
        tree.heading("#0", text="")
        tree.column("#0", width=200, minwidth=80, stretch=True)
        for c, w in zip(cols, self._anchos_tree_seguimiento(incluir_regreso)):
            tree.heading(c, text=c)
            tree.column(c, width=w, minwidth=36, stretch=False)

    def _texto_grupo_seguimiento(self, tipo, numero, filas):
        n = len(filas)
        total_cant = sum(self._normalizar_cantidad_seguimiento(r.get("CANTIDAD")) for _, r in filas)
        titulos = {"OC": "OC", "REMITO": "Remito", "PEDIDO": "Pedido"}
        tit = titulos.get(tipo, tipo)
        return f"▸ {tit} {numero}  ({n} ítems, {total_cant} u.)"

    def _valores_fila_grupo_seguimiento(self, items, incluir_regreso=False):
        """Resumen del grupo: suma cantidades; equipo y fallas vacíos hasta desplegar."""
        _, ref = items[0]
        total_cant = sum(self._normalizar_cantidad_seguimiento(r.get("CANTIDAD")) for _, r in items)
        max_dias = max((int(r.get("DIAS_FUERA", 0) or 0) for _, r in items), default=0)
        ped = self._normalizar_numero_documento_seguimiento(ref.get("NUMERO_PEDIDO"))
        oc = self._normalizar_numero_documento_seguimiento(ref.get("NUMERO_OC"))
        rem = self._normalizar_numero_documento_seguimiento(ref.get("NUMERO_REMITO"))
        sec = self._texto_ui(ref.get("SECTOR"))
        if incluir_regreso:
            return (
                ped, oc, rem, sec, "", "", total_cant, "",
                self._fecha_sin_hora_str(ref.get("FECHA_SALIDA")),
                "", "", self._texto_ui(ref.get("PROVEEDOR"), vacio=""), max_dias, "",
            )
        return (
            ped, oc, rem, sec, "", "", total_cant, "",
            self._fecha_sin_hora_str(ref.get("FECHA_SALIDA")),
            self._texto_ui(ref.get("PROVEEDOR"), vacio=""), max_dias, "",
        )

    def _texto_busqueda_fila_seguimiento(self, row):
        partes = [
            self._texto_ui(row.get("NUMERO_PEDIDO")),
            self._texto_ui(row.get("NUMERO_OC")),
            self._texto_ui(row.get("NUMERO_REMITO")),
            self._texto_ui(row.get("SECTOR")),
            self._texto_ui(row.get("CODIGO")),
            self._texto_ui(row.get("EQUIPO_REPUESTO")),
            self._texto_ui(row.get("NRO_SERIE")),
            self._texto_ui(row.get("PROVEEDOR")),
            self._texto_ui(row.get("OBSERVACIONES")),
            self._texto_ui(row.get("ESTADO_AL_INGRESO")),
        ]
        return " ".join(partes).upper()

    def _seg_aplica_filtros_preview(self, filas):
        if not hasattr(self, "seg_filtro_var"):
            return filas
        texto = self.seg_filtro_var.get().strip().upper()
        sector = ""
        if hasattr(self, "seg_filtro_sector_var"):
            sector = self.seg_filtro_sector_var.get().strip().upper()
        if sector in ("", "TODOS"):
            sector = ""
        out = []
        for idx, row in filas:
            if sector and self._texto_ui(row.get("SECTOR")).upper() != sector:
                continue
            if texto:
                blob = self._texto_busqueda_fila_seguimiento(row)
                palabras = texto.split()
                if not all(p in blob for p in palabras):
                    continue
            out.append((idx, row))
        return out

    def _llenar_tree_seguimiento_agrupado(self, tree, filas, incluir_regreso=False):
        """filas: list of (idx, row). Agrupa por OC, remito o pedido si hay varios ítems."""
        solos = []
        grupos = {}
        for idx, row in filas:
            clave = self._clave_agrupacion_seguimiento(row)
            if clave is None:
                solos.append((idx, row))
            else:
                grupos.setdefault(clave, []).append((idx, row))

        for idx, row in solos:
            tree.insert("", "end", iid=str(idx), text="", values=self._valores_fila_tree_seguimiento(row, incluir_regreso))

        for (tipo, numero), items in sorted(grupos.items(), key=lambda x: (x[0][0], x[0][1])):
            if len(items) == 1:
                idx, row = items[0]
                tree.insert("", "end", iid=str(idx), text="", values=self._valores_fila_tree_seguimiento(row, incluir_regreso))
                continue
            safe_num = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(numero))
            grp_id = f"grp_{tipo}_{safe_num}"
            tree.insert(
                "", "end", iid=grp_id, open=False,
                text=self._texto_grupo_seguimiento(tipo, numero, items),
                values=self._valores_fila_grupo_seguimiento(items, incluir_regreso),
            )
            for idx, row in items:
                tree.insert(
                    grp_id, "end", iid=str(idx), text="  └",
                    values=self._valores_fila_tree_seguimiento(row, incluir_regreso),
                )

    def _refrescar_vistas_seguimiento(self):
        if not hasattr(self, "tree_seguimiento_fuera"):
            return
        self.tree_seguimiento_fuera.delete(*self.tree_seguimiento_fuera.get_children())
        self.tree_seguimiento_ingresado.delete(*self.tree_seguimiento_ingresado.get_children())
        df = self._cargar_df_seguimiento_reparacion()
        if df.empty:
            return
        fuera, ing = [], []
        for idx, row in df.iterrows():
            if self._seguimiento_fila_pendiente(row):
                fuera.append((idx, row))
            else:
                ing.append((idx, row))
        fuera = self._seg_aplica_filtros_preview(fuera)
        ing = self._seg_aplica_filtros_preview(ing)
        self._llenar_tree_seguimiento_agrupado(self.tree_seguimiento_fuera, fuera, incluir_regreso=False)
        self._llenar_tree_seguimiento_agrupado(self.tree_seguimiento_ingresado, ing, incluir_regreso=True)

    def _seg_toggle_grupo_tree(self, event, tree):
        iid = tree.identify_row(event.y)
        if not iid or not str(iid).startswith("grp_"):
            return
        tree.item(iid, open=not tree.item(iid, "open"))

    def _refrescar_tree_seguimiento(self):
        self._refrescar_vistas_seguimiento()

    def _generar_cuerpo_mail_seguimiento_reparacion(self):
        df = self._cargar_df_seguimiento_reparacion()
        lineas_txt = ["Salida de activos — equipos aún fuera de planta.", ""]
        hoy = date.today()
        if df.empty:
            lineas_txt.append("No hay registros en el archivo de seguimiento.")
            html_body = '<p style="font-family:Arial,sans-serif;">No hay registros en el archivo de seguimiento.</p>'
            return "\n".join(lineas_txt), html_body

        pendientes = []
        for idx, row in df.iterrows():
            if not self._seguimiento_fila_pendiente(row):
                continue
            dias = int(row.get("DIAS_FUERA", 0) or 0)
            pendientes.append((idx, row, dias))

        if not pendientes:
            lineas_txt.append(f"Al {self._formato_fecha_escrita(hoy)}: no hay equipos pendientes de regreso.")
            html_body = (
                f'<p style="font-family:Arial,sans-serif;">Al <b>{html.escape(self._formato_fecha_escrita(hoy))}</b> '
                f'no hay equipos pendientes de regreso a planta.</p>'
            )
            return "\n".join(lineas_txt), html_body

        # Mayor cantidad de días fuera de planta primero.
        pendientes.sort(key=lambda p: p[2], reverse=True)
        lineas_txt.append(f"Pendientes ({len(pendientes)}):")
        filas_html = []
        for _idx, row, dias in pendientes:
            lineas_txt.append(
                f"  • {self._etiqueta_equipo_seguimiento(row)} | Sector: {self._texto_ui(row.get('SECTOR'))} | "
                f"Pedido: {self._texto_ui(row.get('NUMERO_PEDIDO'))} | "
                f"OC: {self._texto_ui(row.get('NUMERO_OC'))} | Remito: {self._texto_ui(row.get('NUMERO_REMITO'))} | "
                f"Salida: {self._fecha_sin_hora_str(row.get('FECHA_SALIDA'))} | "
                f"Proveedor: {self._texto_ui(row.get('PROVEEDOR'))} | Días fuera de planta: {dias}"
            )
            filas_html.append((
                self._color_dias_fuera(dias),
                (
                    self._texto_ui(row.get("EQUIPO_REPUESTO")),
                    str(self._normalizar_cantidad_seguimiento(row.get("CANTIDAD"))),
                    self._texto_ui(row.get("CODIGO")),
                    self._texto_ui(row.get("NRO_SERIE")),
                    self._texto_ui(row.get("SECTOR")),
                    self._texto_ui(row.get("NUMERO_PEDIDO")),
                    self._texto_ui(row.get("NUMERO_OC")),
                    self._texto_ui(row.get("NUMERO_REMITO")),
                    self._fecha_sin_hora_str(row.get("FECHA_SALIDA")),
                    self._texto_ui(row.get("PROVEEDOR")),
                    dias,
                    self._texto_ui(row.get("OBSERVACIONES")),
                ),
            ))
        cab = [
            "Equipo/repuesto", "Cant.", "Código", "Nº serie", "Sector", "Nº pedido", "Nº OC", "Nº remito",
            "Fecha salida", "Proveedor", "Días fuera de planta", "Fallas/Observaciones",
        ]
        html_body = self._tabla_html_coloreada(
            "Equipos fuera de planta (ordenados por días, con código de color)",
            cab,
            filas_html,
        )
        return "\n".join(lineas_txt), html_body

    def _enviar_mail_seguimiento_reparacion(self, destino=None):
        destino = (destino or "").strip() or self._correo_destinatario_primario()
        if not destino or self.correos_df.empty:
            return False, "Sin destinatario configurado."
        txt, html_b = self._generar_cuerpo_mail_seguimiento_reparacion()
        asunto = f"Salida de activos — equipos fuera de planta ({date.today().strftime('%Y-%m-%d')})"
        intro_txt = "Recordatorio diario de equipos que aún no regresaron a planta.\n\n"
        intro_html = (
            '<p style="font-family:Arial,sans-serif;font-size:13px;color:#1a5276;">'
            'Recordatorio diario de equipos que aún no regresaron a planta.</p>'
        )
        ruta_adj = self._ruta_archivo_salida_activos()
        adjunto = ruta_adj if os.path.exists(ruta_adj) else None
        if adjunto:
            self._enviar_mail_gastos_adjunto(asunto, intro_txt + txt, intro_html + html_b, destino, adjunto)
        else:
            conf = self.correos_df.iloc[0]
            msg = MIMEMultipart()
            msg['From'] = str(conf['remitente'])
            msg['To'] = str(destino)
            msg['Subject'] = asunto
            alt = MIMEMultipart('alternative')
            alt.attach(MIMEText(intro_txt + txt, 'plain', 'utf-8'))
            alt.attach(MIMEText(intro_html + html_b, 'html', 'utf-8'))
            msg.attach(alt)
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(str(conf['remitente']).strip(), str(conf['password']).strip())
            server.send_message(msg)
            server.quit()
        return True, ""

    def _escribir_excel_formateado(self, path, df, sheet_name="Datos", highlight_col=None, mostrar_total=False):
        with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
            df_excel = self._apply_uppercase_to_df(df)
            df_excel.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            wb = writer.book

            header_fmt = wb.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1, 'align': 'center'})
            base_fmt = wb.add_format({'border': 1})
            highlight_fmt = wb.add_format({'bold': True, 'font_color': '#C00000', 'border': 1})

            for col_num, col_name in enumerate(df_excel.columns):
                ws.write(0, col_num, str(col_name), header_fmt)
                max_len = max(len(str(col_name)), df_excel.iloc[:, col_num].astype(str).str.len().max() if not df_excel.empty else 0)
                ws.set_column(col_num, col_num, min(max(12, int(max_len) + 2), 45), base_fmt)

            if not df_excel.empty:
                ws.autofilter(0, 0, len(df_excel), len(df_excel.columns) - 1)
            ws.freeze_panes(1, 0)

            if highlight_col and highlight_col in df_excel.columns and not df_excel.empty:
                h_idx = df_excel.columns.get_loc(highlight_col)
                for r in range(len(df_excel)):
                    ws.write(r + 1, h_idx, df_excel.iloc[r, h_idx], highlight_fmt)
            self._aplicar_formato_monto_ws(ws, wb, df_excel)

            if mostrar_total:
                total_col = len(df_excel.columns) + 1
                ws.write(0, total_col, "TOTAL ARTICULOS", header_fmt)
                ws.write(1, total_col, len(df_excel), base_fmt)

    def _df_articulos_principal(self):
        if HOJA_ARTICULOS in self.master_dict:
            return self.master_dict[HOJA_ARTICULOS]
        for _, df in self.master_dict.items():
            if 'codigo' in df.columns:
                return df
        return None

    def _col_importancia(self, df):
        if df is None:
            return None
        # Priorizar IMPORTANCIA; usar CRITICIDAD sólo como respaldo real.
        preferida = None
        respaldo = None
        for c in df.columns:
            norm = self._norm_header_imp(str(c)).replace('_', '')
            if norm == 'importancia':
                preferida = c
                break
            if norm == 'criticidad' and respaldo is None:
                respaldo = c
        if preferida is not None:
            return preferida
        if respaldo is not None:
            return respaldo
        return None

    def _correo_destinatario_primario(self):
        if self.correos_df.empty:
            return ""
        row = self.correos_df.iloc[0]
        lower_map = {str(k).strip().lower(): k for k in row.index}
        for want in ('destinatario', 'destino', 'email', 'correo', 'mail', 'para', 'to'):
            if want in lower_map:
                v = str(row[lower_map[want]]).strip()
                if v and v.lower() not in ('nan', 'none'):
                    return v
        return ""

    def _col_correos_destino(self):
        if self.correos_df.empty:
            return None
        lower_map = {str(c).strip().lower(): c for c in self.correos_df.columns}
        for want in ('destinatario', 'destino', 'email', 'correo', 'mail', 'para', 'to'):
            if want in lower_map:
                return lower_map[want]
        return None

    def _col_correos_tipo(self):
        if self.correos_df.empty:
            return None
        lower_map = {str(c).strip().lower(): c for c in self.correos_df.columns}
        for want in ('tipo', 'tipos', 'reporte', 'reportes', 'envio', 'envios', 'recibe'):
            if want in lower_map:
                return lower_map[want]
        return None

    def _correos_por_tipo(self, tipo):
        """Lista de destinatarios para un tipo de reporte.
        tipo: 'general' (reposición, gastos, mensual) o 'activos' (salida de activos).

        Columna 'tipo' de la hoja correos (define el ruteo, sin excepciones):
          - 'pañol'      -> recibe TODOS los reportes (general + salida de activos).
          - 'supervisor' -> recibe SÓLO salida de activos.
        Sin columna 'tipo' -> compatibilidad: el destinatario primario recibe todo.
        Cada celda admite varios correos separados por coma o punto y coma.
        """
        if self.correos_df.empty:
            return []
        dest_col = self._col_correos_destino()
        if dest_col is None:
            return []
        tipo_col = self._col_correos_tipo()
        if tipo_col is None:
            primario = self._correo_destinatario_primario()
            return [primario] if primario else []

        seleccion = []
        for _, row in self.correos_df.iterrows():
            celda = str(row.get(dest_col, '')).strip()
            if not celda or celda.lower() in ('nan', 'none'):
                continue
            t = self._norm_header_imp(str(row.get(tipo_col, ''))).replace('ñ', 'n').strip()
            if t in ('nan', 'none'):
                t = ''
            es_panol = ('panol' in t)
            es_supervisor = ('supervisor' in t)
            incluir = es_panol if tipo == 'general' else (es_panol or es_supervisor)
            if not incluir:
                continue
            for parte in celda.replace(';', ',').split(','):
                e = parte.strip()
                if e and e.lower() not in ('nan', 'none'):
                    seleccion.append(e)
        out = []
        for e in seleccion:
            if e not in out:
                out.append(e)
        return out

    def _destinos_str(self, tipo):
        return ", ".join(self._correos_por_tipo(tipo))

    def _log_mail_automatico(self, mensaje):
        try:
            path = os.path.join(BASE_DIR, "mail_automatico.log")
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} {mensaje}\n")
        except Exception:
            pass

    def _col_stock_actual_maestro(self, df):
        """Stock disponible: compatible con nombres tipo stock actual, cantidad, stock (excluye columnas de mínimo)."""
        if df is None or df.empty:
            return None
        scored = []
        for c in df.columns:
            nhr = self._norm_header_imp(str(c)).replace('_', '').replace(' ', '')
            if 'precio' in nhr or nhr == 'codigo':
                continue
            if 'importancia' in nhr:
                continue
            if (('min' in nhr or 'minimo' in nhr) and 'act' not in nhr and 'actual' not in nhr
                    and 'cant' not in nhr and 'disp' not in nhr):
                continue
            score = 0
            if 'actual' in nhr or nhr.endswith('act'):
                score += 100
            if 'dispon' in nhr:
                score += 90
            if 'stock' in nhr and 'min' not in nhr:
                score += 70
            if 'cant' in nhr or 'qty' in nhr:
                score += 65
            if 'minimo' in nhr or (nhr.startswith('min') and 'stock' not in nhr):
                score -= 100
            if score > 0:
                scored.append((score, c))
        if scored:
            scored.sort(key=lambda x: -x[0])
            return scored[0][1]
        for c in df.columns:
            sl = str(c).lower()
            nh = self._norm_header_imp(str(c)).replace('_', '').replace(' ', '')
            if 'minimo' in nh or nh == 'min' or (nh.endswith('min') and 'act' not in nh and 'cant' not in nh):
                continue
            if 'stock' in sl or 'act' in sl or 'cant' in sl:
                return c
        return None

    def _col_stock_minimo_maestro(self, df):
        if df is None:
            return None
        for c in df.columns:
            nh = self._norm_header_imp(str(c)).replace('_', '').replace(' ', '')
            if nh in ('min', 'minimo') or 'minimo' in nh or nh.endswith('min'):
                return c
        return None

    def _coincide_importancia_cat(self, val, cat_ui):
        """cat_ui: 'criticos' | 'alta frecuencia' | 'base'"""
        v_raw = str(val).strip()
        c_raw = str(cat_ui).strip()
        if not v_raw or v_raw.lower() == 'nan':
            return False
        # Normaliza tildes/espacios para comparar CRITICO/CRÍTICO sin ambigüedad.
        v = self._norm_header_imp(v_raw).replace('_', ' ')
        c = self._norm_header_imp(c_raw).replace('_', ' ')
        if v == c:
            return True
        if c == 'criticos' and ('crit' in v):
            return True
        if c == 'alta frecuencia' and (('alta' in v and 'freq' in v.replace(' ', '')) or 'alta frecuencia' in v):
            return True
        if c == 'base' and ('base' in v or v == 'bas'):
            return True
        return False

    def _obtener_reposicion_df(self, cat):
        df = self._df_articulos_principal()
        if df is None:
            return None, None
        col_imp = self._col_importancia(df)
        c_a = self._col_stock_actual_maestro(df)
        c_m = self._col_stock_minimo_maestro(df)
        if not c_a or not c_m:
            return HOJA_ARTICULOS, None

        if col_imp:
            mask_imp = df[col_imp].apply(lambda x: self._coincide_importancia_cat(x, cat))
            df = df[mask_imp].copy()
        df_repo = df[pd.to_numeric(df[c_a], errors='coerce') <= pd.to_numeric(df[c_m], errors='coerce')].copy()
        if df_repo.empty:
            return HOJA_ARTICULOS, df_repo

        df_repo['A_REPONER'] = pd.to_numeric(df_repo[c_m], errors='coerce') - pd.to_numeric(df_repo[c_a], errors='coerce')
        df_repo = df_repo[df_repo['A_REPONER'] > 0].copy()
        return HOJA_ARTICULOS, df_repo

    def actualizar_contadores_reposicion(self):
        if not all(hasattr(self, v) for v in ("count_crit_var", "count_alta_var", "count_base_var")):
            return
        for cat, tk_var in [('criticos', self.count_crit_var), ('alta frecuencia', self.count_alta_var), ('base', self.count_base_var)]:
            _, df_repo = self._obtener_reposicion_df(cat)
            cantidad = 0 if df_repo is None else len(df_repo)
            tk_var.set(f"({cantidad})")

    def _norm_header_imp(self, name):
        s = str(name).strip().lower()
        for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u')):
            s = s.replace(a, b)
        return s.strip()

    def _df_import_prep_columns(self, df):
        df = df.copy()
        seen = {}
        nuevas = []
        for idx, c in enumerate(df.columns):
            base = self._norm_header_imp(c)
            base = ''.join(base.split())
            if not base:
                base = f"columna_{idx}"
            seen[base] = seen.get(base, 0) + 1
            if seen[base] > 1:
                base = f"{base}_{seen[base]}"
            nuevas.append(base)
        df.columns = nuevas
        return df

    def _col_codigo_en_import(self, columnas_norm):
        for cand in ('codigo', 'cod', 'code', 'sku', 'articulo_codigo'):
            if cand in columnas_norm:
                return cand
        for cn in columnas_norm:
            if cn.startswith('codigo') or cn == 'articulo_cod':
                return cn
        return None

    def _valor_import_util(self, val):
        """True si viene un dato en la planilla para fusionar (no pisar BD con NaN ni celdas vacías)."""
        if val is None:
            return False
        try:
            if pd.isna(val):
                return False
        except (TypeError, ValueError):
            pass
        if isinstance(val, str):
            if not val.strip():
                return False
            if val.strip().lower() in ('nan', '#n/a'):
                return False
        return True

    def _aplicar_celda_import(self, df, idx, dest_col, val):
        """Escribe desde import sólo valores útiles y evita errores de dtype número/texto."""
        if not self._valor_import_util(val):
            return
        dn_raw = self._norm_header_imp(str(dest_col)).replace('_', '').replace(' ', '')
        dn = ''.join(c for c in dn_raw.lower() if c.isalnum())
        es_numerico = any(
            k in dn for k in ('precio', 'minimo', 'stock', 'cantidad', 'cant', 'stkactual', 'stockactual')
        ) or dn in ('min', 'pu', 'punit')
        try:
            if es_numerico:
                num = pd.to_numeric(val, errors='coerce')
                if pd.isna(num):
                    return
                if self._es_columna_precio_dest(dest_col):
                    actual = pd.to_numeric(df.at[idx, dest_col] if dest_col in df.columns else None, errors='coerce')
                    # Si import trae 0, conserva precio manual existente > 0.
                    if float(num) == 0.0 and pd.notna(actual) and float(actual) > 0.0:
                        return
                self._set_cell_numeric_safe(df, idx, dest_col, float(num))
            else:
                if dest_col not in df.columns:
                    df[dest_col] = ''
                esc = val if isinstance(val, str) else val
                if isinstance(esc, str):
                    esc = esc.strip()
                df.at[idx, dest_col] = esc
        except Exception:
            try:
                if dest_col not in df.columns:
                    df[dest_col] = ''
                df.at[idx, dest_col] = str(val).strip() if isinstance(val, str) else val
            except Exception:
                pass

    def _map_import_col_a_maestro(self, col_fuente, columnas_maestro):
        """Mapea columna de la planilla de import a columna del maestro/stock_min (por nombre o semántica)."""
        cols = list(columnas_maestro)
        if not cols:
            return None
        nfs = {''.join(self._norm_header_imp(c).split()): c for c in cols}
        n_f = ''.join(col_fuente.split())

        if n_f in nfs:
            return nfs[n_f]

        cnf = ''.join(filter(str.isalnum, col_fuente))
        for d in cols:
            d_nf = ''.join(filter(str.isalnum, ''.join(str(d).split())))
            if cnf and cnf == d_nf:
                return d

        nh = self._norm_header_imp(col_fuente).replace('_', '')
        nh = ''.join(nh.split())

        if nh == 'articulocodigo' or nh == 'codigoarticulo':
            return None

        if any(k in nh for k in ('ubic', 'pos', 'estant', 'loca', 'almacen')):
            return next((c for c in cols if any(
                k in self._norm_header_imp(c).replace('_', '') for k in ('ubic', 'pos', 'estant', 'loca', 'almacen')
            )), None)
        if nh in ('costouni', 'costo.uni') or ('costo' in nh and 'uni' in nh):
            dest = next((c for c in cols if self._norm_header_imp(str(c)).replace(" ", "_") == 'precio_unitario'), None)
            if dest:
                return dest
            return next((c for c in cols if 'precio' in self._norm_header_imp(c)), None)
        if 'precio' in nh or nh == 'pu' or nh == 'punit':
            return next((c for c in cols if 'precio' in self._norm_header_imp(c)), None)
        if 'stock' in nh and 'min' not in nh:
            return next((c for c in cols if (
                ('stock' in self._norm_header_imp(c) or 'act' in self._norm_header_imp(c))
                and 'min' not in self._norm_header_imp(c)
            )), None)
        if 'min' in nh or nh == 'minimo':
            return next((c for c in cols if 'min' in self._norm_header_imp(c)), None)
        if any(k in nh for k in ('desc', 'detalle', 'nombre')) or nh == 'articulo' or ('art' in nh and 'cod' not in nh):
            return next((c for c in cols if any(
                k in self._norm_header_imp(c) for k in ('desc', 'articulo', 'det', 'nombre')
            ) and 'precio' not in self._norm_header_imp(c)), None)
        if 'importancia' in nh or 'criticidad' in nh:
            return next((c for c in cols if 'importancia' in self._norm_header_imp(str(c)).replace('_', '')), None)
        return None

    def _importancia_desde_nombre_hoja(self, sheet_name):
        sl = str(sheet_name).lower().replace('_', ' ')
        if 'crit' in sl:
            return 'criticos'
        if 'alta' in sl and 'freq' in sl.replace(' ', ''):
            return 'alta frecuencia'
        if 'base' in sl:
            return 'base'
        return 'base'

    def _columna_dest_es_stock_minimo_o_actual(self, dest_col):
        nh = ''.join(c for c in self._norm_header_imp(str(dest_col)).lower() if c.isalnum())
        if 'ubic' in nh or 'pos' in nh or 'estant' in nh:
            return True
        if 'min' in nh:
            return True
        if 'stock' in nh or 'act' in nh or nh == 'cant' or 'cantidad' in nh:
            return True
        return False

    def _fusionar_fila_detallado(self, df, idx, fila_imp, col_cod_imp):
        """Planilla detallada: actualiza mínimo y ubicación (stock actual viene del valorizado)."""
        for col_f in fila_imp.index:
            if col_f == col_cod_imp:
                continue
            val = fila_imp[col_f]
            col_dest = self._map_import_col_a_maestro(col_f, df.columns)
            if col_dest is None and self._es_columna_ubicacion(col_f):
                col_dest = next((c for c in df.columns if self._es_columna_ubicacion(c)), None)
            if col_dest is None:
                continue
            if self._es_columna_stock_actual_dest(col_dest):
                continue
            if not (self._es_columna_minimo_dest(col_dest) or self._es_columna_ubicacion(col_dest)):
                continue
            self._aplicar_celda_import(df, idx, col_dest, val)

    def _fusionar_fila_general_listado(self, df, idx, fila_imp, col_cod_imp, permitir_stock_actual=False):
        """Resto de datos; si es valorizado puede actualizar stock actual, nunca mínimo."""
        for col_f in fila_imp.index:
            if col_f == col_cod_imp:
                continue
            val = fila_imp[col_f]
            col_dest = self._map_import_col_a_maestro(col_f, df.columns)
            if col_dest is None and self._valor_import_util(val):
                col_dest = col_f
                self._asegurar_columna_vacia(df, col_dest)
            if col_dest is None:
                continue
            if self._columna_dest_es_stock_minimo_o_actual(col_dest):
                nh_f = ''.join(self._norm_header_imp(str(col_f)).split())
                if not self._es_columna_ubicacion(col_f) and not ('ubic' in nh_f):
                    if self._es_columna_minimo_dest(col_dest):
                        continue
                    if self._es_columna_stock_actual_dest(col_dest) and not permitir_stock_actual:
                        continue
            self._aplicar_celda_import(df, idx, col_dest, val)

    def _es_columna_ubicacion(self, col_name):
        nh = self._norm_header_imp(str(col_name)).replace('_', '')
        nh = ''.join(nh.split())
        return any(k in nh for k in ('ubic', 'pos', 'estant', 'loca', 'almacen'))

    def _obtener_ubicacion_desde_row(self, row, columnas):
        for c in columnas:
            if not self._es_columna_ubicacion(c):
                continue
            v = row.get(c, "")
            if self._valor_import_util(v):
                return str(v).strip().upper()
        return "N/A"

    def _construir_mapa_ubicaciones_master(self):
        mapa = {}
        for _, df in self.master_dict.items():
            col_cod = self._col_codigo_en_tabla(df.columns)
            if col_cod is None:
                continue
            for _, row in df.iterrows():
                cod = str(row.get(col_cod, "")).strip().upper()
                if not cod:
                    continue
                ubic = self._obtener_ubicacion_desde_row(row, df.columns)
                if ubic == "N/A":
                    continue
                mapa.setdefault(cod, [])
                mapa[cod].append(ubic)

        resolved = {}
        for cod, ubic_list in mapa.items():
            if not ubic_list:
                continue
            # Elige la ubicación más repetida para evitar tomar una hoja incorrecta por orden.
            freq = {}
            for u in ubic_list:
                freq[u] = freq.get(u, 0) + 1
            resolved[cod] = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[0][0]
        return resolved

    def sincronizar_ubicaciones_master_a_stockmin(self):
        """Legado: antes copiaba ubicación al stock_min; con base unificada no hace falta."""
        return

    def _col_codigo_en_tabla(self, columnas):
        for c in columnas:
            if str(c).strip().lower() == 'codigo':
                return c
            if self._norm_header_imp(str(c)).replace('_', '') == 'codigo':
                return c
        return None

    def _asegurar_columna_vacia(self, df, nombre):
        if nombre not in df.columns:
            df[nombre] = ''

    def _fusionar_fila_import_en_df(self, df, idx, fila_imp, col_cod_imp, permitir_nuevas_columnas=True):
        """Para un índice de fila existente: aplica todos los campos útiles del import sin borrar lo que ya había."""
        for col_f in fila_imp.index:
            if col_f == col_cod_imp:
                continue
            val = fila_imp[col_f]
            col_dest = self._map_import_col_a_maestro(col_f, df.columns)
            if col_dest is None and permitir_nuevas_columnas and self._valor_import_util(val):
                col_dest = col_f
                self._asegurar_columna_vacia(df, col_dest)
            if col_dest is None:
                continue
            self._aplicar_celda_import(df, idx, col_dest, val)

    def _es_archivo_detallado(self, nombre_archivo):
        n = str(nombre_archivo).lower()
        return 'detallado' in n

    def _es_archivo_valorizado(self, nombre_archivo):
        n = str(nombre_archivo).lower()
        return 'valorizado' in n

    def _es_columna_minimo_dest(self, dest_col):
        nh = ''.join(c for c in self._norm_header_imp(str(dest_col)).lower() if c.isalnum())
        return ('min' in nh) and ('admin' not in nh)

    def _es_columna_stock_actual_dest(self, dest_col):
        nh = ''.join(c for c in self._norm_header_imp(str(dest_col)).lower() if c.isalnum())
        if self._es_columna_minimo_dest(dest_col):
            return False
        return ('stock' in nh) or ('act' in nh) or (nh == 'cant') or ('cantidad' in nh)

    def _es_columna_precio_dest(self, dest_col):
        nh = ''.join(c for c in self._norm_header_imp(str(dest_col)).lower() if c.isalnum())
        return ("precio" in nh) or ("costouni" in nh)

    def _valor_cmp_import(self, val, es_numerico=False):
        if es_numerico:
            num = pd.to_numeric(val, errors='coerce')
            return None if pd.isna(num) else float(num)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        return str(val).strip().upper()

    def _hubo_cambio_relevante_import(self, antes, despues, columnas):
        for c in columnas:
            if c is None or c not in despues.index:
                continue
            es_num = self._es_columna_stock_actual_dest(c) or self._es_columna_precio_dest(c)
            a = self._valor_cmp_import(antes.get(c), es_numerico=es_num)
            d = self._valor_cmp_import(despues.get(c), es_numerico=es_num)
            if a != d:
                return True
        return False

    def importar_actualizacion_semanal(self):
        if not os.path.exists(CARPETA_IMPORTAR):
            os.makedirs(CARPETA_IMPORTAR)
            messagebox.showinfo("Carpeta Creada", f"Se ha creado la carpeta: {CARPETA_IMPORTAR}. Coloque los archivos allí y reintente.")
            return

        archivos = [f for f in os.listdir(CARPETA_IMPORTAR) if f.endswith('.xlsx')]
        if not archivos:
            messagebox.showwarning("Aviso", "No se encontraron planillas Excel en la carpeta de importación.")
            return

        if HOJA_ARTICULOS not in self.master_dict:
            messagebox.showerror(
                "Importación",
                "No hay base cargada. Coloque base_datos.xlsx o master_codes.xlsx en la carpeta del programa y reinicie.",
            )
            return

        if not messagebox.askyesno(
            "Confirmar Importación",
            "Se fusionarán las planillas por CÓDIGO en la hoja única ARTICULOS.\n"
            "• Archivo con «detallado» en el nombre: actualiza mínimo y ubicación.\n"
            "• Archivo con «valorizado» en el nombre: actualiza stock actual (y resto, sin pisar mínimo).\n"
            "• Otros archivos: actualizan resto de campos (sin pisar stock/mínimo).\n"
            "¿Continuar?"
        ):
            return

        archivos = sorted(archivos, key=lambda n: (0 if self._es_archivo_detallado(n) else 1, n.lower()))

        dlg = tk.Toplevel(self.root)
        dlg.title("Actualización de stock")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.geometry("720x520")
        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Procesando importación…", font=("Arial", 11, "bold")).pack(anchor="w")
        row_t = ttk.Frame(frm)
        row_t.pack(fill="both", expand=True, pady=8)
        txt = tk.Text(row_t, height=22, width=88, font=("Consolas", 9), wrap="word")
        scr = ttk.Scrollbar(row_t, command=txt.yview)
        txt.configure(yscrollcommand=scr.set)
        txt.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")
        cnt = ttk.Label(frm, text="", font=("Arial", 9))
        cnt.pack(anchor="w")

        def log_line(s):
            txt.insert("end", s + "\n")
            txt.see("end")
            dlg.update_idletasks()

        codigos_modificados = []
        codigos_nuevos = []

        try:
            for archivo in archivos:
                es_detallado = self._es_archivo_detallado(archivo)
                es_valorizado = self._es_archivo_valorizado(archivo)
                ruta = os.path.join(CARPETA_IMPORTAR, archivo)
                log_line(f"— {archivo} —")
                try:
                    xls_imp = pd.ExcelFile(ruta)
                except Exception as ex:
                    log_line(f"  ERROR al abrir: {ex}")
                    continue

                for sheet_name in xls_imp.sheet_names:
                    try:
                        raw = pd.read_excel(xls_imp, sheet_name=sheet_name, dtype=object)
                    except Exception as ex:
                        log_line(f"  Hoja «{sheet_name}»: {ex}")
                        continue

                    if raw is None or raw.dropna(how='all').empty:
                        continue

                    df_imp = raw.dropna(axis=1, how='all').copy()
                    df_imp.columns = list(df_imp.columns)
                    df_imp = self._df_import_prep_columns(df_imp)

                    col_cod = self._col_codigo_en_import(list(df_imp.columns))
                    if col_cod is None:
                        continue

                    df_imp[col_cod] = df_imp[col_cod].astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)
                    df_imp = df_imp[df_imp[col_cod].str.len() > 0]
                    df_imp = df_imp[~df_imp[col_cod].isin(('NAN', 'NONE', '', 'NAN.0'))]
                    if df_imp.empty:
                        continue

                    df_art = self.master_dict[HOJA_ARTICULOS]
                    col_cod_dest = self._col_codigo_en_tabla(df_art.columns)
                    if col_cod_dest is None:
                        raise ValueError("La base no tiene columna «codigo».")

                    for _, fila in df_imp.iterrows():
                        cod = fila[col_cod]
                        idx_m = df_art.index[df_art[col_cod_dest].astype(str).str.strip().str.upper() == cod].tolist()

                        if idx_m:
                            idx0 = idx_m[0]
                            row_antes = df_art.loc[idx0].copy()
                            if es_detallado:
                                self._fusionar_fila_detallado(df_art, idx0, fila, col_cod_imp=col_cod)
                            else:
                                self._fusionar_fila_general_listado(
                                    df_art, idx0, fila, col_cod_imp=col_cod, permitir_stock_actual=es_valorizado
                                )
                            col_stock = self._col_stock_actual_maestro(df_art)
                            col_precio = self._col_precio_unitario_df(df_art)
                            col_ubic = next((c for c in df_art.columns if self._es_columna_ubicacion(c)), None)
                            row_despues = df_art.loc[idx0]
                            if self._hubo_cambio_relevante_import(row_antes, row_despues, [col_stock, col_ubic, col_precio]):
                                codigos_modificados.append(cod)
                        else:
                            plantilla = list(df_art.columns)
                            cc_m = self._col_codigo_en_tabla(plantilla)
                            nueva_dict = {c: '' for c in plantilla}
                            nueva_dict[cc_m] = cod
                            if 'importancia' in plantilla:
                                nueva_dict['importancia'] = 'base'
                            self.master_dict[HOJA_ARTICULOS] = pd.concat(
                                [self.master_dict[HOJA_ARTICULOS], pd.DataFrame([nueva_dict])],
                                ignore_index=True, sort=False
                            )
                            df_art = self.master_dict[HOJA_ARTICULOS]
                            last_i = len(df_art) - 1
                            if es_detallado:
                                self._fusionar_fila_detallado(df_art, last_i, fila, col_cod_imp=col_cod)
                            else:
                                self._fusionar_fila_general_listado(
                                    df_art, last_i, fila, col_cod_imp=col_cod, permitir_stock_actual=es_valorizado
                                )
                            codigos_nuevos.append(cod)

                        mod_u = len(set(codigos_modificados))
                        new_u = len(set(codigos_nuevos))
                        cnt.config(text=f"Códigos actualizados (únicos): {mod_u}  |  Códigos nuevos (únicos): {new_u}")
                        dlg.update_idletasks()

            df_art = self.master_dict.get(HOJA_ARTICULOS)
            if df_art is not None and not df_art.empty:
                df_art = self._limpiar_columnas_precio_duplicadas_df(df_art)
                col_imp = self._col_importancia(df_art)
                if col_imp:
                    df_art[col_imp] = df_art[col_imp].apply(self._normalizar_criticidad_maestro)
                self.master_dict[HOJA_ARTICULOS] = df_art
            self.guardar_sistemas_simple()
            self.preparar_cache_buscador()
            self.actualizar_contadores_reposicion()

            mod_u = sorted(set(codigos_modificados))
            new_u = sorted(set(codigos_nuevos))
            col_cod = self._col_codigo_en_tabla(df_art.columns) if df_art is not None and not df_art.empty else None
            col_pre = self._col_precio_unitario_df(df_art) if df_art is not None and not df_art.empty else None
            sin_precio = []
            if df_art is not None and not df_art.empty and col_cod and col_pre:
                for _, rr in df_art.iterrows():
                    cod = str(rr.get(col_cod, "")).strip().upper()
                    if not cod:
                        continue
                    pv = pd.to_numeric(rr.get(col_pre), errors='coerce')
                    if pd.isna(pv) or float(pv) <= 0.0:
                        sin_precio.append(cod)
                sin_precio = sorted(set(sin_precio))
            log_line("")
            log_line(f"Finalizado. Artículos modificados (únicos): {len(mod_u)}")
            if mod_u:
                s = ", ".join(mod_u)
                if len(s) > 4000:
                    s = s[:4000] + "…"
                log_line(s)
            log_line(f"Códigos nuevos agregados (únicos): {len(new_u)}")
            log_line("")
            log_line(f"Códigos sin precio_unitario (>0): {len(sin_precio)}")
            if sin_precio:
                s2 = ", ".join(sin_precio)
                if len(s2) > 4000:
                    s2 = s2[:4000] + "…"
                log_line(s2)
            log_line("")
            log_line("Las celdas vacías en la importación no borran datos existentes.")
            ttk.Button(frm, text="Cerrar", command=dlg.destroy).pack(anchor="e", pady=(8, 0))

        except Exception as e:
            tb = traceback.format_exc()
            try:
                dlg.destroy()
            except Exception:
                pass
            messagebox.showerror("Error Critico", f"Fallo al sincronizar planillas: {str(e)}\n\n{tb[:1500]}")

    def setup_ui(self):
        self.main_container = tk.Frame(self.root, bg="#ecf0f1")
        self.main_container.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("Arial", 10, "bold"), padding=[10, 5])
        
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.tab_salidas = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_salidas, text="📦 Registro de salidas")
        self.setup_tab_salidas()

        self.tab_gastos = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_gastos, text="💸 Reportes")
        self.setup_tab_gastos()

        self.tab_seguimiento = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_seguimiento, text="🔧 Salida de activos")
        self.setup_tab_seguimiento()

        self.tab_config = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_config, text="⚙️ Configuración y datos")
        self.setup_tab_config()

        self.notebook.select(self.tab_salidas)

    def setup_tab_config(self):
        frm = ttk.Frame(self.tab_config, padding=20)
        frm.pack(fill="both", expand=True)
        frm_files = ttk.LabelFrame(frm, text=" Archivos de sistema ", padding=10)
        frm_files.pack(fill="x", pady=5)
        frm_files.columnconfigure(0, weight=1)
        frm_files.columnconfigure(1, weight=1)
        ttk.Button(frm_files, text="✏️ Editar artículo", command=self.abrir_editor).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(frm_files, text="🔄 Actualizar App Pañol", command=self.sincronizar_todo_a_firebase).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(frm_files, text="Actualización de stock", command=self.importar_actualizacion_semanal).grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky="ew")
        estado_nube = " | ☁️ Nube OK" if firebase_conectado else " | 🔴 Sin nube"
        if firebase_proyecto_id:
            estado_nube += f" | Proyecto: {firebase_proyecto_id}"
        self.lbl_status = ttk.Label(frm_files, text=f"Buscando archivos...{estado_nube}", font=("Arial", 8, "italic"))
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)

    def setup_tab_gastos(self):
        main = ttk.Frame(self.tab_gastos, padding=20)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        frm = ttk.Frame(main)
        frm.grid(row=0, column=0, sticky="nsew")
        font_lbl = ("Arial", 11)

        ttk.Label(
            frm,
            text="Reporte de gastos",
            font=("Arial", 14, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        sec_d = ttk.LabelFrame(frm, text="Reporte diario", padding=10)
        sec_d.pack(fill="x", pady=(4, 12))
        row = ttk.Frame(sec_d)
        row.pack(anchor="w", pady=6)
        ttk.Label(row, text="Día a reportar:", font=font_lbl).pack(side="left", padx=(0, 10))
        ayer = datetime.today().date() - timedelta(days=1)
        self.date_reporte_gastos = DateEntry(
            row, width=14, date_pattern="d/m/yyyy", font=font_lbl
        )
        self.date_reporte_gastos.set_date(ayer)
        self.date_reporte_gastos.pack(side="left", padx=(0, 12))

        def enviar_reporte_diario_correo(destino_manual=None):
            def work():
                try:
                    d = self.date_reporte_gastos.get_date()
                    archivo_diario, fecha_ref, cuerpo_txt, cuerpo_html, err = self._generar_reporte_gastos_sector(d)
                    if not archivo_diario:
                        self.root.after(
                            0,
                            lambda: messagebox.showerror(
                                "Gastos",
                                err or "No se pudo generar el reporte.",
                            ),
                        )
                        return
                    destino = destino_manual or self._correo_destinatario_primario()
                    if not destino:
                        self.root.after(
                            0,
                            lambda: messagebox.showwarning(
                                "Gastos",
                                "No hay destinatario en la hoja correos (primera fila).",
                            ),
                        )
                        return
                    asunto = f"Reporte Diario de Gasto por Sector ({fecha_ref.strftime('%Y-%m-%d')})"
                    intro_txt = "Adjunto reporte diario de gastos por sector.\n\n"
                    intro_html = (
                        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#1a5276;">'
                        "Reporte diario de gastos por sector.</p>"
                    )
                    self._enviar_mail_gastos_adjunto(
                        asunto,
                        intro_txt + cuerpo_txt,
                        intro_html + cuerpo_html,
                        destino,
                        archivo_diario,
                    )
                    self.root.after(
                        0,
                        lambda p=archivo_diario: messagebox.showinfo(
                            "Gastos",
                            f"Correo enviado correctamente.\nAdjunto: {os.path.basename(p)}",
                        ),
                    )
                except Exception as ex:
                    self.root.after(
                        0,
                        lambda: messagebox.showerror("Gastos", str(ex)),
                    )

            threading.Thread(target=work, daemon=True).start()

        ttk.Button(
            row,
            text="Exportar diario",
            command=lambda: self._exportar_reporte_diario_gastos_manual(self.date_reporte_gastos.get_date()),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Enviar diario", command=lambda: enviar_reporte_diario_correo()).pack(side="left")
        ttk.Button(
            row,
            text="Enviar diario a...",
            command=lambda: self._enviar_reporte_diario_destino_manual(enviar_reporte_diario_correo),
        ).pack(side="left", padx=(6, 0))

        sec_m = ttk.LabelFrame(frm, text="Reporte mensual", padding=10)
        sec_m.pack(fill="x", pady=(4, 0))
        row_m = ttk.Frame(sec_m)
        row_m.pack(anchor="w", pady=6)
        ttk.Label(row_m, text="Mes:", font=font_lbl).pack(side="left", padx=(0, 8))
        self.cmb_mes_reporte = ttk.Combobox(row_m, state="readonly", width=18)
        meses = [f"{i:02d}/{datetime.today().year}" for i in range(1, 13)]
        self.cmb_mes_reporte["values"] = meses
        self.cmb_mes_reporte.set(f"{datetime.today().month:02d}/{datetime.today().year}")
        self.cmb_mes_reporte.pack(side="left", padx=(0, 12))

        def enviar_mensual(destino_manual=None):
            def work():
                try:
                    mes_txt = self.cmb_mes_reporte.get().strip()
                    fecha_ref = datetime.strptime("01/" + mes_txt, "%d/%m/%Y").date()
                    archivo_mensual, cuerpo_txt, cuerpo_html, err = self._generar_reporte_mensual_gastos(fecha_ref)
                    if not archivo_mensual:
                        self.root.after(0, lambda: messagebox.showerror("Gastos", err or "No se pudo generar el mensual."))
                        return
                    destino = destino_manual or self._correo_destinatario_primario()
                    if not destino:
                        self.root.after(0, lambda: messagebox.showwarning("Gastos", "No hay destinatario en hoja correos."))
                        return
                    asunto = f"Reporte Mensual de Gastos ({fecha_ref.strftime('%m/%Y')})"
                    self._enviar_mail_gastos_adjunto(asunto, cuerpo_txt, cuerpo_html, destino, archivo_mensual)
                    self.root.after(0, lambda: messagebox.showinfo("Gastos", f"Correo mensual enviado.\nAdjunto: {os.path.basename(archivo_mensual)}"))
                except Exception as ex:
                    self.root.after(0, lambda: messagebox.showerror("Gastos", str(ex)))
            threading.Thread(target=work, daemon=True).start()

        ttk.Button(row_m, text="Exportar mensual", command=self._exportar_reporte_mensual_manual).pack(side="left", padx=(0, 6))
        ttk.Button(row_m, text="Enviar mensual", command=lambda: enviar_mensual()).pack(side="left")
        ttk.Button(
            row_m,
            text="Enviar mensual a...",
            command=lambda: self._enviar_reporte_mensual_destino_manual(enviar_mensual),
        ).pack(side="left", padx=(6, 0))

        sec_listas = ttk.LabelFrame(frm, text="Listas de compra", padding=10)
        sec_listas.pack(fill="x", pady=(12, 10))
        for cat, txt, color, attr in [
            ("criticos", "🚨 Lista críticos", "#c0392b", "count_crit_var"),
            ("alta frecuencia", "⚡ Lista alta frecuencia", "#d35400", "count_alta_var"),
            ("base", "📦 Lista base", "#2980b9", "count_base_var"),
        ]:
            row_l = ttk.Frame(sec_listas)
            row_l.pack(fill="x", pady=4)
            if not hasattr(self, attr):
                setattr(self, attr, tk.StringVar(value="(0)"))
            ttk.Button(row_l, text=txt, command=lambda c=cat: self.exportar_reposicion(c)).pack(side="left", fill="x", expand=True)
            ttk.Label(row_l, textvariable=getattr(self, attr), foreground=color, font=("Arial", 10, "bold")).pack(side="left", padx=6)
            ttk.Button(row_l, text="✉️", width=3, command=lambda c=cat: self.enviar_mail_manual(c)).pack(side="right")

        sec_out = ttk.LabelFrame(frm, text="Salidas e historial", padding=10)
        sec_out.pack(fill="x")
        r1 = ttk.Frame(sec_out); r1.pack(fill="x", pady=4)
        ttk.Button(r1, text="Exportar reporte diario", command=self.generar_diario_manual).pack(side="left", fill="x", expand=True)
        ttk.Button(r1, text="Enviar reporte diario a...", command=lambda: self._enviar_reporte_diario_destino_manual(enviar_reporte_diario_correo)).pack(side="right", padx=(6, 0))
        r2 = ttk.Frame(sec_out); r2.pack(fill="x", pady=4)
        ttk.Button(r2, text="Abrir historial", command=lambda: os.startfile(HISTORIAL_PATH) if os.path.exists(HISTORIAL_PATH) else None).pack(side="left", fill="x", expand=True)
        ttk.Button(r2, text="Enviar historial a...", command=self._enviar_historial_destino_manual).pack(side="right", padx=(6, 0))
        self.actualizar_contadores_reposicion()

    def _enviar_reporte_diario_destino_manual(self, callback_envio):
        dest = simpledialog.askstring("Mail", "Correo destino para reporte diario:", parent=self.root)
        if not dest:
            return
        callback_envio(destino_manual=dest.strip())

    def _enviar_reporte_mensual_destino_manual(self, callback_envio):
        dest = simpledialog.askstring("Mail", "Correo destino para reporte mensual:", parent=self.root)
        if not dest:
            return
        callback_envio(destino_manual=dest.strip())

    def _exportar_reporte_mensual_manual(self):
        mes_txt = self.cmb_mes_reporte.get().strip()
        fecha_ref = datetime.strptime("01/" + mes_txt, "%d/%m/%Y").date()
        archivo_mensual, _, _, err = self._generar_reporte_mensual_gastos(fecha_ref)
        if not archivo_mensual:
            return messagebox.showerror("Gastos", err or "No se pudo generar el mensual.")
        os.startfile(archivo_mensual)

    def _exportar_reporte_diario_gastos_manual(self, fecha_ref):
        archivo_diario, _, _, _, err = self._generar_reporte_gastos_sector(fecha_ref)
        if not archivo_diario:
            return messagebox.showerror("Gastos", err or "No se pudo generar el diario.")
        os.startfile(archivo_diario)

    def _enviar_historial_destino_manual(self):
        if not os.path.exists(HISTORIAL_PATH):
            return messagebox.showwarning("Historial", "No existe master_salidas.xlsx todavía.")
        dest = simpledialog.askstring("Mail", "Correo destino para historial:", parent=self.root)
        if not dest:
            return
        try:
            self._enviar_mail_con_adjunto(
                "Historial de salidas",
                "Adjunto historial de salidas.",
                dest.strip(),
                HISTORIAL_PATH,
            )
            messagebox.showinfo("Historial", "Historial enviado.")
        except Exception as ex:
            messagebox.showerror("Historial", str(ex))

    def setup_tab_seguimiento(self):
        self._asegurar_sectores_base()
        content_frame = ttk.Frame(self.tab_seguimiento, padding="20")
        content_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", fill="y", expand=False, padx=(0, 10))

        frm_form = ttk.LabelFrame(left_frame, text=" Registro de salida de planta ", padding=15)
        frm_form.pack(fill="both", expand=True, pady=5)
        frm_form.columnconfigure(1, weight=1)

        fecha_frame = ttk.LabelFrame(frm_form, text=" Fecha de salida * ", padding=10)
        fecha_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(
            fecha_frame, text="⚠️ Verifique la fecha antes de registrar",
            font=("Arial", 10, "bold"), foreground="#b03a2e",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.seg_fecha_salida = DateEntry(fecha_frame, width=14, date_pattern="d/m/yyyy", font=("Arial", 11, "bold"))
        self.seg_fecha_salida.grid(row=1, column=0, sticky="w")
        self.seg_fecha_salida.bind("<<DateEntrySelected>>", lambda e: self._actualizar_dias_fuera_seguimiento_ui())

        datos = ttk.Frame(frm_form)
        datos.grid(row=1, column=0, columnspan=2, sticky="ew")
        datos.columnconfigure(1, weight=1)
        r = 0

        ttk.Label(datos, text="Proveedor:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        self.seg_proveedor_var = tk.StringVar()
        ttk.Entry(datos, textvariable=self.seg_proveedor_var).grid(row=r, column=1, sticky="ew", pady=4)
        self.seg_proveedor_var.trace_add("write", lambda *_a: self._set_upper_entry(self.seg_proveedor_var))
        r += 1

        self._label_con_asterisco_obligatorio(datos, "Nº de remito:", r)
        self.seg_remito_var = tk.StringVar()
        ttk.Entry(datos, textvariable=self.seg_remito_var).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        ttk.Label(datos, text="Nº de pedido:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        self.seg_pedido_var = tk.StringVar()
        ttk.Entry(datos, textvariable=self.seg_pedido_var).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        ttk.Label(datos, text="Nº de OC:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        self.seg_oc_var = tk.StringVar()
        ttk.Entry(datos, textvariable=self.seg_oc_var).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        self._label_con_asterisco_obligatorio(datos, "Equipo/repuesto:", r)
        self.seg_equipo_var = tk.StringVar()
        ent_eq = ttk.Entry(datos, textvariable=self.seg_equipo_var, font=("Arial", 11, "bold"), width=46)
        ent_eq.grid(row=r, column=1, sticky="ew", pady=4)
        ent_eq.bind("<Return>", self.enfocar_siguiente)
        self.seg_equipo_var.trace_add("write", lambda *_a: self._set_upper_entry(self.seg_equipo_var))
        r += 1

        ttk.Label(datos, text="Nro. de serie:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        self.seg_serie_var = tk.StringVar()
        ttk.Entry(datos, textvariable=self.seg_serie_var).grid(row=r, column=1, sticky="ew", pady=4)
        self.seg_serie_var.trace_add("write", lambda *_a: self._set_upper_entry(self.seg_serie_var))
        r += 1

        ttk.Label(datos, text="Código:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        self.seg_codigo_var = tk.StringVar()
        self.ent_seg_cod = ttk.Entry(datos, textvariable=self.seg_codigo_var, font=("Arial", 11, "bold"))
        self.ent_seg_cod.grid(row=r, column=1, sticky="ew", pady=4)
        self.ent_seg_cod.bind("<Return>", self._seg_procesar_codigo)
        ttk.Label(datos, text="(opcional)", font=("Arial", 8, "italic")).grid(row=r + 1, column=1, sticky="w")
        r += 2

        ttk.Label(datos, text="Cantidad:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        self.seg_cantidad_var = tk.StringVar(value="1")
        ttk.Entry(datos, textvariable=self.seg_cantidad_var, width=8).grid(row=r, column=1, sticky="w", pady=4)
        r += 1

        ttk.Label(datos, text="Fallas/Observaciones:").grid(row=r, column=0, sticky="ne", padx=5, pady=4)
        self.seg_obs_var = tk.StringVar()
        ttk.Entry(datos, textvariable=self.seg_obs_var).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        self._label_con_asterisco_obligatorio(datos, "Sector:", r)
        self.seg_sector_var = tk.StringVar()
        self.cmb_seg_sector = ttk.Combobox(datos, textvariable=self.seg_sector_var, values=self.sectores_operario, state="normal")
        self.cmb_seg_sector.grid(row=r, column=1, sticky="ew", pady=4)
        self._configurar_combobox_predictivo(self.cmb_seg_sector, self.sectores_operario)
        r += 1

        ttk.Label(
            datos,
            text="El regreso se indica con «Marcar regreso» en la lista.",
            font=("Arial", 8, "italic"), foreground="#555",
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 6))
        r += 1

        self.seg_dias_var = tk.StringVar(value="0")
        ttk.Label(datos, text="Días fuera de planta:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        ttk.Label(datos, textvariable=self.seg_dias_var, font=("Arial", 14, "bold"), foreground="#c0392b").grid(
            row=r, column=1, sticky="w", pady=4
        )

        self.btn_seg_save = tk.Button(
            left_frame, text="REGISTRAR SALIDA DE PLANTA", bg="#27ae60", fg="white",
            font=("Arial", 11, "bold"), command=self._seg_registrar_salida,
        )
        self.btn_seg_save.pack(fill="x", pady=(10, 5))
        ttk.Button(left_frame, text="Reportar salida de equipos", command=self._seg_reportar_excel).pack(fill="x", pady=4)
        ttk.Button(left_frame, text="Enviar reporte a...", command=self._seg_enviar_reporte_destino_manual).pack(fill="x", pady=2)

        mid_frame = ttk.LabelFrame(content_frame, text=" Seguimiento de activos ", padding=5)
        mid_frame.pack(side="left", fill="both", expand=True, padx=10)

        frm_seg_filtro = ttk.Frame(mid_frame)
        frm_seg_filtro.pack(fill="x", pady=(0, 6))
        ttk.Label(frm_seg_filtro, text="Buscar:").pack(side="left", padx=(0, 4))
        self.seg_filtro_var = tk.StringVar()
        ent_seg_bus = ttk.Entry(frm_seg_filtro, textvariable=self.seg_filtro_var, width=28)
        ent_seg_bus.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.seg_filtro_var.trace_add("write", lambda *_a: self._refrescar_vistas_seguimiento())
        ttk.Label(frm_seg_filtro, text="Sector:").pack(side="left", padx=(0, 4))
        sectores_filtro = ["TODOS"] + list(self.sectores_operario)
        self.seg_filtro_sector_var = tk.StringVar(value="TODOS")
        cmb_seg_f_sec = ttk.Combobox(
            frm_seg_filtro, textvariable=self.seg_filtro_sector_var, values=sectores_filtro,
            state="readonly", width=16,
        )
        cmb_seg_f_sec.pack(side="left")
        cmb_seg_f_sec.bind("<<ComboboxSelected>>", lambda e: self._refrescar_vistas_seguimiento())

        ttk.Label(
            mid_frame,
            text="Arrastre el borde entre encabezados de columna para ajustar el ancho. Use Ctrl+clic para seleccionar varios ítems.",
            font=("Arial", 8, "italic"), foreground="#555",
        ).pack(anchor="w", pady=(0, 4))

        self.seg_preview_notebook = ttk.Notebook(mid_frame)
        self.seg_preview_notebook.pack(fill="both", expand=True)

        tab_fuera = ttk.Frame(self.seg_preview_notebook, padding=4)
        tab_ing = ttk.Frame(self.seg_preview_notebook, padding=4)
        self.seg_preview_notebook.add(tab_fuera, text="Activos fuera de planta")
        self.seg_preview_notebook.add(tab_ing, text="Activos ingresados a planta")

        self.tree_seguimiento_fuera = ttk.Treeview(tab_fuera, height=16)
        self._configurar_tree_seguimiento(self.tree_seguimiento_fuera, incluir_regreso=False)
        self.tree_seguimiento_fuera.pack(fill="both", expand=True)
        self.tree_seguimiento_fuera.bind("<Double-1>", self._seg_doble_clic_tree_fuera)

        self.tree_seguimiento_ingresado = ttk.Treeview(tab_ing, height=16)
        self._configurar_tree_seguimiento(self.tree_seguimiento_ingresado, incluir_regreso=True)
        self.tree_seguimiento_ingresado.pack(fill="both", expand=True)
        self.tree_seguimiento_ingresado.bind("<Double-1>", self._seg_doble_clic_tree_ing)

        btn_ing = ttk.Frame(tab_ing)
        btn_ing.pack(fill="x", pady=(5, 0))
        tk.Button(
            btn_ing, text="✏️ Editar datos", bg="#2980b9", fg="white",
            font=("Arial", 9, "bold"), command=self._seg_editar_ingresado_seleccionado,
        ).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(
            btn_ing, text="↩️ Restablecer a fuera de planta", bg="#e67e22", fg="white",
            font=("Arial", 9, "bold"), command=self._seg_restablecer_seleccionado,
        ).pack(side="left", fill="x", expand=True, padx=2)

        btn_f = ttk.Frame(tab_fuera)
        btn_f.pack(fill="x", pady=(5, 0))
        tk.Button(
            btn_f, text="✏️ Editar datos", bg="#2980b9", fg="white",
            font=("Arial", 9, "bold"), command=self._seg_editar_seleccionado,
        ).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(
            btn_f, text="✅ Marcar regreso", bg="#27ae60", fg="white",
            font=("Arial", 9, "bold"), command=self._seg_marcar_regreso,
        ).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(
            btn_f, text="🗑️ Limpiar formulario", bg="#c0392b", fg="white",
            font=("Arial", 9, "bold"), command=self._seg_limpiar_formulario,
        ).pack(side="right", fill="x", expand=True, padx=2)

        self._refrescar_vistas_seguimiento()

    def _seg_doble_clic_tree_fuera(self, event):
        iid = self.tree_seguimiento_fuera.identify_row(event.y)
        if iid and str(iid).startswith("grp_"):
            self._seg_toggle_grupo_tree(event, self.tree_seguimiento_fuera)
            return
        self._seg_editar_seleccionado()

    def _seg_limpiar_formulario(self):
        self.seg_pedido_var.set("")
        self.seg_oc_var.set("")
        self.seg_remito_var.set("")
        self.seg_codigo_var.set("")
        self.seg_equipo_var.set("")
        self.seg_cantidad_var.set("1")
        self.seg_serie_var.set("")
        self.seg_proveedor_var.set("")
        self.seg_sector_var.set("")
        self.seg_obs_var.set("")
        self.seg_dias_var.set("0")
        self.ent_seg_cod.focus_set()

    def _actualizar_dias_fuera_seguimiento_ui(self):
        if not hasattr(self, "seg_dias_var"):
            return
        fs = self.seg_fecha_salida.get_date()
        self.seg_dias_var.set(str(self._calcular_dias_fuera_planta(fs, None)))

    def _seg_procesar_codigo(self, event=None):
        cod = self.seg_codigo_var.get().strip().upper()
        if not cod:
            return "break"
        if not self.master_dict:
            return "break"
        for _, df in self.master_dict.items():
            if "codigo" not in df.columns:
                continue
            match = df[df["codigo"] == cod]
            if not match.empty:
                row = match.iloc[0]
                desc = next(
                    (str(row.get(c, "")).upper() for c in ["descripcion", "descripción", "detalle", "articulo"]
                     if c in df.columns), ""
                )
                if desc and not self.seg_equipo_var.get().strip():
                    self.seg_equipo_var.set(desc)
                break
        self._actualizar_dias_fuera_seguimiento_ui()
        return "break"

    def _seg_registrar_salida(self):
        equipo = self.seg_equipo_var.get().strip().upper()
        if not equipo:
            messagebox.showwarning("Salida de activos", "Ingrese el equipo o repuesto.", parent=self.root)
            return
        sector = self.seg_sector_var.get().strip().upper()
        if not sector:
            messagebox.showwarning("Salida de activos", "Seleccione el sector.", parent=self.root)
            return
        fs = self.seg_fecha_salida.get_date()
        cod = self.seg_codigo_var.get().strip().upper()
        cant = self._normalizar_cantidad_seguimiento(self.seg_cantidad_var.get())
        nueva = {
            "NUMERO_PEDIDO": self.seg_pedido_var.get().strip().upper(),
            "NUMERO_OC": self.seg_oc_var.get().strip().upper(),
            "NUMERO_REMITO": self._normalizar_numero_documento_seguimiento(self.seg_remito_var.get()),
            "SECTOR": sector,
            "CODIGO": cod,
            "EQUIPO_REPUESTO": equipo,
            "CANTIDAD": cant,
            "NRO_SERIE": self.seg_serie_var.get().strip().upper(),
            "FECHA_SALIDA": self._normalizar_celda_fecha_seguimiento(fs),
            "PROVEEDOR": self.seg_proveedor_var.get().strip().upper(),
            "FECHA_REGRESO": "",
            "OBSERVACIONES": self.seg_obs_var.get().strip().upper(),
            "ESTADO_AL_INGRESO": "",
            "DIAS_FUERA": self._calcular_dias_fuera_planta(fs, None),
            "ESTADO": "FUERA_DE_PLANTA",
        }
        try:
            df = self._cargar_df_seguimiento_reparacion()
            df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            self._guardar_df_seguimiento_reparacion(df)
            self._refrescar_vistas_seguimiento()
            self._seg_limpiar_formulario()
            messagebox.showinfo("Seguimiento", "Salida de planta registrada.", parent=self.root)
        except PermissionError:
            messagebox.showerror(
                "Seguimiento",
                "No se pudo guardar: cierre el archivo Excel de seguimiento si está abierto e intente de nuevo.",
                parent=self.root,
            )
        except Exception as ex:
            messagebox.showerror("Seguimiento", f"No se pudo registrar la salida:\n{ex}", parent=self.root)

    def _seg_indices_desde_tree(self, tree):
        indices = []
        for iid in tree.selection():
            if str(iid).startswith("grp_"):
                for child in tree.get_children(iid):
                    idx = self._seg_iid_a_indice_df(child)
                    if idx is not None:
                        indices.append(idx)
            else:
                idx = self._seg_iid_a_indice_df(iid)
                if idx is not None:
                    indices.append(idx)
        vistos = set()
        unicos = []
        for i in indices:
            if i not in vistos:
                vistos.add(i)
                unicos.append(i)
        return unicos

    def _seg_aplicar_ingreso_planta(self, df, indices, fecha_ingreso, estado_ingreso=""):
        fr_str = self._normalizar_celda_fecha_seguimiento(fecha_ingreso)
        est_ing = str(estado_ingreso).strip().upper()
        for idx in indices:
            if idx not in df.index:
                continue
            df.at[idx, "FECHA_REGRESO"] = fr_str
            df.at[idx, "ESTADO"] = "INGRESADO_A_PLANTA"
            df.at[idx, "ESTADO_AL_INGRESO"] = est_ing
            fs = df.at[idx, "FECHA_SALIDA"]
            df.at[idx, "DIAS_FUERA"] = self._calcular_dias_fuera_planta(fs, fecha_ingreso)

    def _seg_restablecer_fuera_planta(self, df, idx):
        df.at[idx, "ESTADO"] = "FUERA_DE_PLANTA"
        df.at[idx, "FECHA_REGRESO"] = ""
        df.at[idx, "ESTADO_AL_INGRESO"] = ""
        fs = df.at[idx, "FECHA_SALIDA"]
        df.at[idx, "DIAS_FUERA"] = self._calcular_dias_fuera_planta(fs, None)

    def _seg_dialogo_ingreso_planta(self, df, indices_preseleccionados=None):
        pendientes = df[df.apply(self._seguimiento_fila_pendiente, axis=1)]
        if pendientes.empty:
            messagebox.showwarning("Seguimiento", "No hay equipos pendientes de regreso.", parent=self.root)
            return None

        lista = [(idx, self._etiqueta_equipo_seguimiento(row)) for idx, row in pendientes.iterrows()]

        top = tk.Toplevel(self.root)
        top.title("Confirmar ingreso a planta")
        top.geometry("620x520")
        top.transient(self.root)
        top.grab_set()
        frm = ttk.Frame(top, padding=14)
        frm.pack(fill="both", expand=True)
        frm.rowconfigure(1, weight=1)
        frm.columnconfigure(0, weight=1)

        ttk.Label(
            frm,
            text="Seleccione uno o más equipos que ingresan a planta (Ctrl+clic / Mayús+clic):",
            font=("Arial", 11, "bold"), wraplength=580,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        frm_list = ttk.Frame(frm)
        frm_list.grid(row=1, column=0, sticky="nsew")
        frm_list.rowconfigure(0, weight=1)
        frm_list.columnconfigure(0, weight=1)
        lb = tk.Listbox(frm_list, selectmode=tk.EXTENDED, height=14, font=("Arial", 10))
        lb.grid(row=0, column=0, sticky="nsew")
        scr = ttk.Scrollbar(frm_list, orient="vertical", command=lb.yview)
        scr.grid(row=0, column=1, sticky="ns")
        lb.configure(yscrollcommand=scr.set)
        for i, (idx, etq) in enumerate(lista):
            lb.insert(tk.END, etq)
            if indices_preseleccionados and idx in indices_preseleccionados:
                lb.selection_set(i)

        def sel_todos():
            lb.selection_set(0, tk.END)

        def sel_ninguno():
            lb.selection_clear(0, tk.END)

        frm_lb_btn = ttk.Frame(frm_list)
        frm_lb_btn.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(frm_lb_btn, text="Seleccionar todos", command=sel_todos).pack(side="left", padx=2)
        ttk.Button(frm_lb_btn, text="Quitar selección", command=sel_ninguno).pack(side="left", padx=2)

        frm_datos = ttk.LabelFrame(frm, text=" Datos del ingreso ", padding=10)
        frm_datos.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(frm_datos, text="Fecha de ingreso a planta *", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w")
        de_ingreso = DateEntry(frm_datos, width=14, date_pattern="d/m/yyyy", font=("Arial", 11, "bold"))
        de_ingreso.grid(row=1, column=0, sticky="w", pady=4)
        de_ingreso.set_date(date.today())
        ttk.Label(
            frm_datos, text="Estado / condición al ingresar a planta *",
            font=("Arial", 10, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(8, 4))
        ttk.Label(
            frm_datos,
            text="Describa en qué estado vuelve el equipo o repuesto (ej. REPARADO, REVISADO OK, PARA BAJA).",
            font=("Arial", 8, "italic"), foreground="#555", wraplength=560,
        ).grid(row=3, column=0, sticky="w")
        txt_estado = tk.Text(frm_datos, height=3, font=("Arial", 10))
        txt_estado.grid(row=4, column=0, sticky="ew", pady=4)
        frm_datos.columnconfigure(0, weight=1)

        resultado = {"ok": False, "fecha": None, "estado": "", "indices": []}

        def confirmar():
            sel_idx = lb.curselection()
            if not sel_idx:
                messagebox.showwarning("Seguimiento", "Seleccione al menos un equipo.", parent=top)
                return
            estado_txt = txt_estado.get("1.0", tk.END).strip().upper()
            if not estado_txt:
                messagebox.showwarning(
                    "Seguimiento", "Indique el estado en que ingresa el equipo o repuesto.", parent=top,
                )
                return
            resultado["indices"] = [lista[i][0] for i in sel_idx]
            resultado["fecha"] = de_ingreso.get_date()
            resultado["estado"] = estado_txt
            resultado["ok"] = True
            top.destroy()

        btn_c = ttk.Frame(frm)
        btn_c.grid(row=3, column=0, pady=(12, 0))
        ttk.Button(btn_c, text="Confirmar ingreso", command=confirmar).pack(side="left", padx=4)
        ttk.Button(btn_c, text="Cancelar", command=top.destroy).pack(side="left", padx=4)
        top.wait_window()
        return resultado if resultado["ok"] else None

    def _seg_abrir_edicion(self, idx, ingresado=False):
        df = self._cargar_df_seguimiento_reparacion()
        if idx not in df.index:
            return messagebox.showerror("Seguimiento", "No se encontró el registro.", parent=self.root)
        row = df.loc[idx]
        top = tk.Toplevel(self.root)
        top.title("Editar equipo ingresado" if ingresado else "Editar equipo fuera de planta")
        top.geometry("540x520" if ingresado else "540x460")
        top.transient(self.root)
        top.grab_set()
        frm = ttk.Frame(top, padding=16)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text=self._etiqueta_equipo_seguimiento(row), font=("Arial", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10),
        )
        ttk.Label(
            frm,
            text=f"Código: {self._texto_ui(row.get('CODIGO'))}  |  Serie: {self._texto_ui(row.get('NRO_SERIE'))}  |  "
                 f"Remito: {self._normalizar_numero_documento_seguimiento(row.get('NUMERO_REMITO')) or '-'}",
            font=("Arial", 9), wraplength=490,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        r = 2
        ttk.Label(frm, text="Nº de pedido:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        var_ped = tk.StringVar(value=self._normalizar_numero_documento_seguimiento(row.get("NUMERO_PEDIDO")))
        ttk.Entry(frm, textvariable=var_ped).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        ttk.Label(frm, text="Nº de OC:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        var_oc = tk.StringVar(value=self._normalizar_numero_documento_seguimiento(row.get("NUMERO_OC")))
        ttk.Entry(frm, textvariable=var_oc).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        ttk.Label(frm, text="Sector:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        var_sec = tk.StringVar(value=self._texto_ui(row.get("SECTOR"), vacio=""))
        if var_sec.get() == "-":
            var_sec.set("")
        cmb_sec_ed = ttk.Combobox(frm, textvariable=var_sec, values=self.sectores_operario, state="normal")
        cmb_sec_ed.grid(row=r, column=1, sticky="ew", pady=4)
        self._configurar_combobox_predictivo(cmb_sec_ed, self.sectores_operario)
        r += 1

        ttk.Label(frm, text="Fecha de salida:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        fs_d = self._parse_fecha_ui_a_date(row.get("FECHA_SALIDA")) or date.today()
        de_salida = DateEntry(frm, width=14, date_pattern="d/m/yyyy", font=("Arial", 10, "bold"))
        de_salida.grid(row=r, column=1, sticky="w", pady=4)
        de_salida.set_date(fs_d)
        r += 1

        ttk.Label(frm, text="Proveedor:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
        var_prov = tk.StringVar(value=self._texto_ui(row.get("PROVEEDOR"), vacio=""))
        ttk.Entry(frm, textvariable=var_prov).grid(row=r, column=1, sticky="ew", pady=4)
        var_prov.trace_add("write", lambda *_a: self._set_upper_entry(var_prov))
        r += 1

        var_est_ing = None
        de_fr = None
        if ingresado:
            ttk.Label(frm, text="Fecha ingreso:").grid(row=r, column=0, sticky="e", padx=5, pady=4)
            de_fr = DateEntry(frm, width=14, date_pattern="d/m/yyyy", font=("Arial", 10, "bold"))
            de_fr.grid(row=r, column=1, sticky="w", pady=4)
            fr_d = self._parse_fecha_ui_a_date(row.get("FECHA_REGRESO"))
            if fr_d:
                de_fr.set_date(fr_d)
            r += 1
            ttk.Label(frm, text="Estado al ingreso:").grid(row=r, column=0, sticky="ne", padx=5, pady=4)
            var_est_ing = tk.StringVar(value=self._texto_ui(row.get("ESTADO_AL_INGRESO"), vacio=""))
            if var_est_ing.get() == "-":
                var_est_ing.set("")
            ttk.Entry(frm, textvariable=var_est_ing).grid(row=r, column=1, sticky="ew", pady=4)
            var_est_ing.trace_add("write", lambda *_a: self._set_upper_entry(var_est_ing))
            r += 1

        ttk.Label(frm, text="Fallas/Observaciones:").grid(row=r, column=0, sticky="ne", padx=5, pady=4)
        var_obs = tk.StringVar(value=self._texto_ui(row.get("OBSERVACIONES"), vacio=""))
        if var_obs.get() == "-":
            var_obs.set("")
        ttk.Entry(frm, textvariable=var_obs).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        def guardar_edicion():
            try:
                df.at[idx, "NUMERO_PEDIDO"] = self._normalizar_numero_documento_seguimiento(var_ped.get())
                df.at[idx, "NUMERO_OC"] = self._normalizar_numero_documento_seguimiento(var_oc.get())
                df.at[idx, "SECTOR"] = var_sec.get().strip().upper()
                df.at[idx, "FECHA_SALIDA"] = self._normalizar_celda_fecha_seguimiento(de_salida.get_date())
                df.at[idx, "PROVEEDOR"] = var_prov.get().strip().upper()
                df.at[idx, "OBSERVACIONES"] = var_obs.get().strip().upper()
                fr_calc = None
                if ingresado and de_fr is not None:
                    fr_calc = de_fr.get_date()
                    df.at[idx, "FECHA_REGRESO"] = self._normalizar_celda_fecha_seguimiento(fr_calc)
                    df.at[idx, "ESTADO_AL_INGRESO"] = var_est_ing.get().strip().upper() if var_est_ing else ""
                    df.at[idx, "ESTADO"] = "INGRESADO_A_PLANTA"
                fs = df.at[idx, "FECHA_SALIDA"]
                df.at[idx, "DIAS_FUERA"] = self._calcular_dias_fuera_planta(fs, fr_calc)
                self._guardar_df_seguimiento_reparacion(df)
                self._refrescar_vistas_seguimiento()
                top.destroy()
                messagebox.showinfo("Seguimiento", "Datos actualizados.", parent=self.root)
            except PermissionError:
                messagebox.showerror(
                    "Seguimiento", "Cierre el Excel de seguimiento si está abierto.", parent=top,
                )
            except Exception as ex:
                messagebox.showerror("Seguimiento", f"No se pudo guardar:\n{ex}", parent=top)

        def restablecer():
            if not messagebox.askyesno(
                "Restablecer",
                "¿Volver este equipo a «Fuera de planta»?\nSe borrarán fecha y estado de ingreso.",
                parent=top,
            ):
                return
            try:
                self._seg_restablecer_fuera_planta(df, idx)
                self._guardar_df_seguimiento_reparacion(df)
                self._refrescar_vistas_seguimiento()
                top.destroy()
                self.seg_preview_notebook.select(0)
                messagebox.showinfo("Seguimiento", "Equipo restablecido a fuera de planta.", parent=self.root)
            except PermissionError:
                messagebox.showerror("Seguimiento", "Cierre el Excel de seguimiento si está abierto.", parent=top)
            except Exception as ex:
                messagebox.showerror("Seguimiento", f"No se pudo guardar:\n{ex}", parent=top)

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=r, column=0, columnspan=2, pady=(14, 0))
        ttk.Button(btn_row, text="Guardar cambios", command=guardar_edicion).pack(side="left", padx=4)
        if ingresado:
            ttk.Button(btn_row, text="Restablecer a fuera de planta", command=restablecer).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Cancelar", command=top.destroy).pack(side="left", padx=4)

    def _seg_editar_seleccionado(self):
        indices = self._seg_indices_desde_tree(self.tree_seguimiento_fuera)
        if len(indices) != 1:
            return messagebox.showwarning(
                "Seguimiento",
                "Seleccione un solo equipo fuera de planta (doble clic o botón Editar datos).",
                parent=self.root,
            )
        df = self._cargar_df_seguimiento_reparacion()
        if not self._seguimiento_fila_pendiente(df.loc[indices[0]]):
            return messagebox.showwarning("Seguimiento", "El ítem ya no está fuera de planta.", parent=self.root)
        self._seg_abrir_edicion(indices[0], ingresado=False)

    def _seg_editar_ingresado_seleccionado(self):
        indices = self._seg_indices_desde_tree(self.tree_seguimiento_ingresado)
        if len(indices) != 1:
            return messagebox.showwarning(
                "Seguimiento",
                "Seleccione un solo equipo ingresado (doble clic o Editar datos).",
                parent=self.root,
            )
        self._seg_abrir_edicion(indices[0], ingresado=True)

    def _seg_doble_clic_tree_ing(self, event):
        iid = self.tree_seguimiento_ingresado.identify_row(event.y)
        if iid and str(iid).startswith("grp_"):
            self._seg_toggle_grupo_tree(event, self.tree_seguimiento_ingresado)
            return
        self._seg_editar_ingresado_seleccionado()

    def _seg_restablecer_seleccionado(self):
        indices = self._seg_indices_desde_tree(self.tree_seguimiento_ingresado)
        if not indices:
            return messagebox.showwarning(
                "Seguimiento",
                "Seleccione uno o más equipos en «Seguimientos ingresados a planta».",
                parent=self.root,
            )
        if not messagebox.askyesno(
            "Restablecer",
            f"¿Volver {len(indices)} equipo(s) a «Fuera de planta»?\nSe borrarán fecha y estado de ingreso.",
            parent=self.root,
        ):
            return
        try:
            df = self._cargar_df_seguimiento_reparacion()
            for idx in indices:
                if idx in df.index:
                    self._seg_restablecer_fuera_planta(df, idx)
            self._guardar_df_seguimiento_reparacion(df)
            self._refrescar_vistas_seguimiento()
            self.seg_preview_notebook.select(0)
            messagebox.showinfo("Seguimiento", f"Se restablecieron {len(indices)} equipo(s).", parent=self.root)
        except PermissionError:
            messagebox.showerror("Seguimiento", "Cierre el Excel de seguimiento si está abierto.", parent=self.root)
        except Exception as ex:
            messagebox.showerror("Seguimiento", str(ex), parent=self.root)

    def _seg_marcar_regreso(self):
        indices = self._seg_indices_desde_tree(self.tree_seguimiento_fuera)
        if not indices:
            return messagebox.showwarning(
                "Seguimiento",
                "Seleccione uno o más equipos en «Seguimientos fuera de planta» (Ctrl+clic para varios).",
                parent=self.root,
            )
        df = self._cargar_df_seguimiento_reparacion()
        n = len(indices)
        if not messagebox.askyesno(
            "Confirmar ingreso",
            f"¿Registrar el ingreso a planta de {n} equipo(s) seleccionado(s)?",
            parent=self.root,
        ):
            return
        res = self._seg_dialogo_ingreso_planta(df, indices_preseleccionados=indices)
        if not res:
            return
        try:
            self._seg_aplicar_ingreso_planta(df, res["indices"], res["fecha"], res["estado"])
            self._guardar_df_seguimiento_reparacion(df)
            self._refrescar_vistas_seguimiento()
            self.seg_preview_notebook.select(1)
            messagebox.showinfo(
                "Seguimiento",
                f"Ingreso registrado para {len(res['indices'])} equipo(s) el {self._formato_fecha_escrita(res['fecha'])}.",
                parent=self.root,
            )
        except PermissionError:
            messagebox.showerror("Seguimiento", "Cierre el Excel de seguimiento si está abierto.", parent=self.root)
        except Exception as ex:
            messagebox.showerror("Seguimiento", str(ex), parent=self.root)

    def _seg_reportar_excel(self):
        df = self._cargar_df_seguimiento_reparacion()
        if df.empty:
            df = self._normalizar_df_seguimiento_planta(pd.DataFrame(columns=self._columnas_seguimiento_planta()))
        self._guardar_df_seguimiento_reparacion(df)
        ruta = SALIDA_ACTIVOS_PATH if os.path.exists(SALIDA_ACTIVOS_PATH) else self._ruta_archivo_salida_activos()
        if os.path.exists(ruta):
            os.startfile(ruta)
        else:
            messagebox.showinfo("Salida de activos", "No hay datos para generar el reporte.")

    def _seg_enviar_reporte_destino_manual(self):
        dest = simpledialog.askstring("Mail", "Correo destino para reporte de salida de activos:", parent=self.root)
        if not dest:
            return
        try:
            ok, err = self._enviar_mail_seguimiento_reparacion(dest.strip())
            if ok:
                messagebox.showinfo("Seguimiento", "Reporte enviado.", parent=self.root)
            else:
                messagebox.showerror("Seguimiento", err or "No se pudo enviar.", parent=self.root)
        except Exception as ex:
            messagebox.showerror("Seguimiento", str(ex), parent=self.root)

    def setup_tab_salidas(self):
        content_frame = ttk.Frame(self.tab_salidas, padding="20")
        content_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", fill="y", expand=False, padx=(0, 10))

        frm_form = ttk.LabelFrame(left_frame, text=" Registro de Movimiento ", padding=15)
        frm_form.pack(fill="both", expand=True, pady=5)
        frm_form.columnconfigure(0, weight=1)

        fecha_frame = ttk.LabelFrame(frm_form, text=" Fecha de movimiento * ", padding=10)
        fecha_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(fecha_frame, text="⚠️ Verifique la fecha antes de registrar", font=("Arial", 10, "bold"), foreground="#b03a2e").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.date_entry = DateEntry(fecha_frame, width=14, date_pattern='d/m/yyyy', font=("Arial", 11, "bold"))
        self.date_entry.grid(row=1, column=0, sticky="w")
        self.date_entry.bind('<Return>', self.enfocar_siguiente)

        form_cols = ttk.Frame(frm_form)
        form_cols.grid(row=1, column=0, sticky="nsew")
        form_cols.columnconfigure(0, weight=1)
        form_cols.columnconfigure(1, weight=1)

        left_group = ttk.LabelFrame(form_cols, text=" Artículo ", padding=10)
        left_group.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_group.columnconfigure(1, weight=1)

        right_group = ttk.LabelFrame(form_cols, text=" Solicitud ", padding=10)
        right_group.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_group.columnconfigure(1, weight=1)

        self._label_con_asterisco_obligatorio(left_group, "Código:", 0)
        self.codigo_var = tk.StringVar()
        self.ent_codigo = ttk.Entry(left_group, textvariable=self.codigo_var, font=("Arial", 11, "bold"))
        self.ent_codigo.grid(row=0, column=1, sticky="ew", pady=4)
        self.ent_codigo.bind('<Return>', self.procesar_codigo_y_avanzar)

        frm_buscar = ttk.Frame(left_group)
        frm_buscar.grid(row=0, column=2, padx=5)
        ttk.Button(frm_buscar, text="🔍 Buscar", width=8, command=self.procesar_codigo_y_avanzar).pack(side="left", padx=1)
        ttk.Button(frm_buscar, text="Avanzado (F3)", command=self.abrir_buscador).pack(side="left", padx=1)
        self.root.bind('<F3>', lambda e: self.abrir_buscador())

        self.desc_var = tk.StringVar()
        ttk.Label(left_group, text="Descripción:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(left_group, textvariable=self.desc_var, state="readonly", takefocus=False).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)

        self.precio_var = tk.StringVar()
        ttk.Label(left_group, text="Precio Unit.:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        ttk.Entry(left_group, textvariable=self.precio_var, state="readonly", takefocus=False).grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)

        self.cant_var = tk.StringVar()
        self._label_con_asterisco_obligatorio(left_group, "Cantidad:", 3)
        self.ent_cant = ttk.Entry(left_group, textvariable=self.cant_var, font=("Arial", 11, "bold"))
        self.ent_cant.grid(row=3, column=1, sticky="ew", pady=4)
        self.ent_cant.bind('<Return>', self._on_enter_cantidad)

        self._label_con_asterisco_obligatorio(right_group, "Comprobante:", 0)
        self.cmb_tipo = ttk.Combobox(right_group, values=self.tipos_comprobante, state="normal")
        self.cmb_tipo.grid(row=0, column=1, sticky="ew", pady=4)
        self.cmb_tipo.bind('<Return>', self.enfocar_siguiente)
        self._configurar_combobox_predictivo(self.cmb_tipo, self.tipos_comprobante)
        self.cmb_tipo.bind("<<ComboboxSelected>>", lambda e: self._restaurar_lista_completa_combobox(self.cmb_tipo), add="+")

        self.orden_var = tk.StringVar()
        self._label_con_asterisco_obligatorio(right_group, "N° Orden:", 1)
        self.ent_orden = ttk.Entry(right_group, textvariable=self.orden_var)
        self.ent_orden.grid(row=1, column=1, sticky="ew", pady=4)
        self.ent_orden.bind('<Return>', self.enfocar_siguiente)

        self.maquina_var = tk.StringVar()
        ttk.Label(right_group, text="Máquina:").grid(row=2, column=0, sticky="e", padx=5, pady=4)
        self.ent_maquina = ttk.Entry(right_group, textvariable=self.maquina_var)
        self.ent_maquina.grid(row=2, column=1, sticky="ew", pady=4)
        self.ent_maquina.bind('<Return>', self.enfocar_siguiente)

        self._label_con_asterisco_obligatorio(right_group, "Sector:", 3)
        self.cmb_ope = ttk.Combobox(right_group, values=self.sectores_operario, state="normal")
        self.cmb_ope.grid(row=3, column=1, sticky="ew", pady=4)
        self.cmb_ope.bind("<<ComboboxSelected>>", self.on_sector_change)
        self.cmb_ope.bind("<<ComboboxSelected>>", lambda e: self._restaurar_lista_completa_combobox(self.cmb_ope), add="+")
        self.cmb_ope.bind("<KeyRelease>", self.on_sector_change, add="+")
        self.cmb_ope.bind('<Return>', lambda e: (self.on_sector_change(), self.enfocar_siguiente(e))[1])
        self._configurar_combobox_predictivo(self.cmb_ope, self.sectores_operario)

        self.ope_det_var = tk.StringVar()
        self._label_con_asterisco_obligatorio(right_group, "Operario:", 4)
        self.cmb_ope_det = ttk.Combobox(right_group, textvariable=self.ope_det_var, values=[], state="disabled")
        self.cmb_ope_det.grid(row=4, column=1, sticky="ew", pady=4)
        self.cmb_ope_det.bind('<Return>', lambda e: self.btn_save.invoke())
        self.cmb_ope_det.bind("<<ComboboxSelected>>", lambda e: self._restaurar_lista_completa_combobox(self.cmb_ope_det), add="+")

        self._montos_carga_orden = {}
        self._sim_items = []
        self._sim_visible = tk.BooleanVar(value=False)
        calc_outer = ttk.LabelFrame(left_frame, text=" Simulador de costo de salida ", padding=8)
        calc_outer.pack(fill="x", pady=(0, 6), before=frm_form)
        self._btn_toggle_sim = ttk.Button(
            calc_outer, text="▶ Simulador de costo de salida",
            command=self._toggle_simulador_costo,
        )
        self._btn_toggle_sim.pack(fill="x")
        self._sim_inner = ttk.LabelFrame(calc_outer, text=" Simulación (no descuenta stock) ", padding=8)
        frm_sim_add = ttk.Frame(self._sim_inner)
        frm_sim_add.pack(fill="x", pady=(0, 6))
        ttk.Label(frm_sim_add, text="Código:").pack(side="left")
        self.sim_buscar_var = tk.StringVar()
        ent_sim_cod = ttk.Entry(frm_sim_add, textvariable=self.sim_buscar_var, width=18)
        ent_sim_cod.pack(side="left", padx=4)
        ent_sim_cod.bind("<Return>", lambda e: self._sim_buscar_y_agregar())
        ttk.Button(frm_sim_add, text="Agregar actual", command=self._sim_agregar_desde_formulario).pack(side="left", padx=2)
        ttk.Button(frm_sim_add, text="Avanzado (F3)", command=lambda: self.abrir_buscador(callback=self._sim_callback_desde_avanzado)).pack(side="left", padx=2)
        ttk.Button(frm_sim_add, text="Ventana ampliada", command=self._abrir_simulador_ventana).pack(side="left", padx=2)
        cols_sim = ("Código", "Descripción", "Cant.", "P. unit.", "Monto")
        self.tree_sim = ttk.Treeview(self._sim_inner, columns=cols_sim, show="headings", height=5)
        for c, w in zip(cols_sim, (72, 160, 44, 78, 88)):
            self.tree_sim.heading(c, text=c)
            self.tree_sim.column(c, width=w, anchor="center" if c != "Descripción" else "w")
        self.tree_sim.pack(fill="x", pady=4)
        frm_sim_tot = ttk.Frame(self._sim_inner)
        frm_sim_tot.pack(fill="x")
        ttk.Label(frm_sim_tot, text="Total simulado:", font=("Arial", 10, "bold")).pack(side="left")
        self.sim_total_var = tk.StringVar(value="$ 0")
        ttk.Label(frm_sim_tot, textvariable=self.sim_total_var, font=("Arial", 12, "bold"), foreground="#1a5276").pack(side="left", padx=8)
        ttk.Button(frm_sim_tot, text="Vaciar", command=self._sim_vaciar).pack(side="right")

        self.btn_save = tk.Button(left_frame, text="REGISTRAR SALIDA", bg="#27ae60", fg="white", font=("Arial", 11, "bold"), command=lambda: self.procesar_movimiento(es_devolucion=False))
        self.btn_save.pack(fill="x", pady=(10, 5))
        self.btn_save.bind('<Return>', lambda e: self.btn_save.invoke())
        self._enforzar_mayusculas_campos_solicitud()

        self.btn_return = tk.Button(left_frame, text="♻️ REGISTRAR DEVOLUCIÓN", bg="#e67e22", fg="white", font=("Arial", 10, "bold"), command=lambda: self.procesar_movimiento(es_devolucion=True))
        self.btn_return.pack(fill="x", pady=(0, 5))

        # --- COLUMNA 2: VISTA PARCIAL DE LA ORDEN ---
        mid_frame = ttk.LabelFrame(content_frame, text=" Carga Actual ", padding=5)
        mid_frame.pack(side="left", fill="y", expand=False, padx=10)

        cols_orden = ("Código", "Descripción", "Cant.", "P. unit.", "Monto")
        self.tree_orden = ttk.Treeview(mid_frame, columns=cols_orden, show="headings", height=16, selectmode="extended")
        for c, w, anc in [
            ("Código", "Código", 68), ("Descripción", "Descripción", 150), ("Cant.", "Cant.", 44),
            ("P. unit.", "P. unit.", 76), ("Monto", "Monto", 84),
        ]:
            self.tree_orden.heading(c, text=w)
            self.tree_orden.column(c, width=anc, anchor="center" if c != "Descripción" else "w")
        self.tree_orden.pack(fill="both", expand=True)
        frm_tot_carga = ttk.Frame(mid_frame)
        frm_tot_carga.pack(fill="x", pady=(4, 0))
        ttk.Label(frm_tot_carga, text="Total salida:", font=("Arial", 10, "bold")).pack(side="left")
        self.lbl_total_carga_var = tk.StringVar(value="$ 0")
        ttk.Label(frm_tot_carga, textvariable=self.lbl_total_carga_var, font=("Arial", 12, "bold"), foreground="#c0392b").pack(side="left", padx=6)

        btn_f_ord = ttk.Frame(mid_frame)
        btn_f_ord.pack(fill="x", pady=5)
        tk.Button(btn_f_ord, text="✅ Finalizar", bg="#27ae60", fg="white", font=("Arial", 9, "bold"), command=self._finalizar_carga_actual).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(btn_f_ord, text="🧹 Eliminar ítem", bg="#7f8c8d", fg="white", font=("Arial", 9, "bold"), command=self._eliminar_items_carga_actual).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(btn_f_ord, text="🗑️ Restablecer", bg="#c0392b", fg="white", font=("Arial", 9, "bold"), command=self.restablecer_salidas).pack(side="right", fill="x", expand=True, padx=2)
        self.tree_orden.bind("<Delete>", lambda e: self._eliminar_items_carga_actual())

        # --- COLUMNA 3: ESTADO DEL ARTICULO Y LOGO ---
        right_frame = ttk.LabelFrame(content_frame, text=" Estado del Artículo ", padding=20)
        right_frame.pack(side="right", fill="both", expand=True, padx=10)

        self.stk_actual_var = tk.StringVar(value="-")
        self.stk_min_var = tk.StringVar(value="-")
        self.stk_ubic_var = tk.StringVar(value="-")

        ttk.Label(right_frame, text="STOCK ACTUAL", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        ttk.Label(right_frame, textvariable=self.stk_actual_var, font=("Arial", 28), foreground="#2980b9").pack()

        ttk.Label(right_frame, text="STOCK MÍNIMO", font=("Arial", 10, "bold")).pack(pady=(20, 0))
        ttk.Label(right_frame, textvariable=self.stk_min_var, font=("Arial", 24), foreground="#c0392b").pack()

        ttk.Label(right_frame, text="UBICACIÓN", font=("Arial", 10, "bold")).pack(pady=(20, 0))
        ttk.Label(right_frame, textvariable=self.stk_ubic_var, font=("Arial", 16, "italic")).pack()

        if os.path.exists(LOGO_PATH):
            try:
                self.logo_img = tk.PhotoImage(file=LOGO_PATH)
                lbl_logo = tk.Label(right_frame, image=self.logo_img)
                lbl_logo.pack(side="bottom", pady=20)
            except Exception: pass

        self._set_formulario_misma_orden_bloqueado(False)

    def _toggle_simulador_costo(self):
        if self._sim_visible.get():
            self._sim_inner.pack_forget()
            self._sim_visible.set(False)
            self._btn_toggle_sim.config(text="▶ Simulador de costo de salida")
        else:
            self._sim_inner.pack(fill="both", expand=True, pady=4)
            self._sim_visible.set(True)
            self._btn_toggle_sim.config(text="▼ Simulador de costo de salida")

    def _sim_refrescar_tree(self):
        if not hasattr(self, "tree_sim"):
            return
        self.tree_sim.delete(*self.tree_sim.get_children())
        total = 0.0
        for it in self._sim_items:
            self.tree_sim.insert("", "end", values=(
                it["cod"], it["desc"], it["cant"],
                self._formato_precio_unit_ui(it["precio"]),
                self._formato_pesos_ar(it["monto"]),
            ))
            total += it["monto"]
        self.sim_total_var.set(self._formato_pesos_ar(total))

    def _sim_agregar_item(self, cod, desc, cant, precio):
        try:
            cant_f = abs(float(str(cant).replace(",", ".")))
        except ValueError:
            return messagebox.showwarning("Simulador", "Cantidad inválida.", parent=self.root)
        if cant_f <= 0:
            return messagebox.showwarning("Simulador", "La cantidad debe ser mayor a cero.", parent=self.root)
        px = 0.0 if pd.isna(precio) else float(precio)
        monto = round(cant_f * px, 2)
        self._sim_items.append({
            "cod": str(cod).upper(),
            "desc": str(desc).upper(),
            "cant": cant_f,
            "precio": px,
            "monto": monto,
        })
        self._sim_refrescar_tree()

    def _sim_agregar_desde_formulario(self):
        cod = self.codigo_var.get().strip().upper()
        if not cod:
            return messagebox.showwarning("Simulador", "Ingrese un código primero.", parent=self.root)
        cant = self.cant_var.get().strip() or "1"
        precio = self._parse_precio_ui_a_float(self.precio_var.get())
        self._sim_agregar_item(cod, self.desc_var.get(), cant, precio)

    def _sim_callback_desde_avanzado(self, cod):
        self.sim_buscar_var.set(cod)
        self.codigo_var.set(cod)
        self.procesar_codigo_y_avanzar()
        self._sim_agregar_desde_formulario()

    def _sim_buscar_y_agregar(self):
        if not self.master_dict:
            return messagebox.showwarning("Simulador", "Cargue el maestro primero.", parent=self.root)
        q = self.sim_buscar_var.get().strip().upper()
        if not q:
            return self._sim_agregar_desde_formulario()
        if not self.search_cache:
            self.preparar_cache_buscador()
        exact = next((i for i in self.search_cache if i.get("c") == q), None)
        if exact is None:
            exact = next((i for i in self.search_cache if q in str(i.get("c", "")).upper()), None)
        if exact is None:
            return messagebox.showwarning("Simulador", "Código no encontrado. Use Avanzado (F3).", parent=self.root)
        self.sim_buscar_var.set(exact["c"])
        self.codigo_var.set(exact["c"])
        self.procesar_codigo_y_avanzar()
        self._sim_agregar_desde_formulario()

    def _sim_vaciar(self):
        self._sim_items = []
        self._sim_refrescar_tree()

    def _abrir_simulador_ventana(self):
        top = tk.Toplevel(self.root)
        top.title("Simulador de costo de salida")
        top.geometry("900x480")
        top.transient(self.root)
        ttk.Label(top, text="Agregue repuestos por código o búsqueda avanzada (no afecta stock).", font=("Arial", 10, "bold")).pack(pady=8)
        frm = ttk.Frame(top, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Código:").grid(row=0, column=0, sticky="e")
        sv = tk.StringVar()
        ttk.Entry(frm, textvariable=sv, width=24).grid(row=0, column=1, sticky="ew", padx=4)
        frm.columnconfigure(1, weight=1)

        def agregar_cod(cod):
            self.codigo_var.set(cod)
            self.procesar_codigo_y_avanzar()
            self._sim_agregar_desde_formulario()
            self._sim_refrescar_tree()

        ttk.Button(frm, text="Avanzado (F3)", command=lambda: self.abrir_buscador(callback=agregar_cod)).grid(row=0, column=2, padx=4)
        ttk.Button(frm, text="Agregar código", command=lambda: (self.sim_buscar_var.set(sv.get()), self._sim_buscar_y_agregar())).grid(row=0, column=3, padx=4)
        tree_w = ttk.Treeview(frm, columns=("Código", "Descripción", "Cant.", "P. unit.", "Monto"), show="headings", height=14)
        for c in tree_w["columns"]:
            tree_w.heading(c, text=c)
        tree_w.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=10)
        frm.rowconfigure(1, weight=1)

        def refrescar_win():
            tree_w.delete(*tree_w.get_children())
            tot = 0.0
            for it in self._sim_items:
                tree_w.insert("", "end", values=(
                    it["cod"], it["desc"], it["cant"],
                    self._formato_precio_unit_ui(it["precio"]),
                    self._formato_pesos_ar(it["monto"]),
                ))
                tot += it["monto"]
            lbl_tot.config(text=self._formato_pesos_ar(tot))

        lbl_tot = ttk.Label(frm, text="$ 0", font=("Arial", 14, "bold"), foreground="#1a5276")
        lbl_tot.grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Button(frm, text="Vaciar lista", command=lambda: (self._sim_vaciar(), refrescar_win())).grid(row=2, column=3, sticky="e")
        refrescar_win()
        top.bind("<Destroy>", lambda e: self._sim_refrescar_tree())

    def _actualizar_total_carga_orden(self):
        if not hasattr(self, "lbl_total_carga_var"):
            return
        total = sum(self._montos_carga_orden.values()) if hasattr(self, "_montos_carga_orden") else 0.0
        self.lbl_total_carga_var.set(self._formato_pesos_ar(total))

    def _eliminar_items_carga_actual(self):
        if not hasattr(self, "tree_orden"):
            return
        sels = self.tree_orden.selection()
        if not sels:
            return
        for iid in sels:
            self.tree_orden.delete(iid)
            if hasattr(self, "_montos_carga_orden") and iid in self._montos_carga_orden:
                self._montos_carga_orden.pop(iid, None)
            if hasattr(self, "_salidas_pendientes") and iid in self._salidas_pendientes:
                self._salidas_pendientes.pop(iid, None)
        self._actualizar_total_carga_orden()

    def _buscar_stock_item_master(self, cod):
        cod = str(cod or "").strip().upper()
        for s, df in self.master_dict.items():
            if 'codigo' not in df.columns:
                continue
            idx_m = df.index[df['codigo'] == cod].tolist()
            if not idx_m:
                continue
            col_s = next((c for c in df.columns if 'stock' in c or 'act' in c or 'cant' in c), None)
            if not col_s:
                continue
            return s, df, idx_m[0], col_s
        return None, None, None, None

    def _stock_proyectado_codigo(self, cod):
        s, df, idx, col_s = self._buscar_stock_item_master(cod)
        if df is None:
            return None
        stk_act = pd.to_numeric(df.at[idx, col_s], errors='coerce')
        base = 0.0 if pd.isna(stk_act) else float(stk_act)
        for p in self._salidas_pendientes.values():
            fila = p.get("fila", {})
            if str(fila.get("CODIGO", "")).strip().upper() == str(cod).strip().upper():
                base -= float(fila.get("CANTIDAD", 0) or 0)
        return base

    def _guardar_movimientos_batch(self, pendientes):
        with self.save_lock:
            self.guardar_sistemas_simple()
            por_archivo = {}
            for p in pendientes:
                fila = p["fila"]
                fecha_dt = p["fecha_dt"]
                archivo_diario = os.path.join(BASE_DIR, f"salidas_{fecha_dt.strftime('%d-%m-%Y')}.xlsx")
                por_archivo.setdefault(HISTORIAL_PATH, []).append(fila)
                por_archivo.setdefault(archivo_diario, []).append(fila)
            for path, filas in por_archivo.items():
                if os.path.exists(path):
                    df_p = pd.read_excel(path)
                else:
                    df_p = pd.DataFrame()
                if 'FECHA' in df_p.columns:
                    df_p['FECHA'] = df_p['FECHA'].apply(self._fecha_sin_hora_str)
                df_p = pd.concat([df_p, pd.DataFrame(filas)], ignore_index=True)
                if 'FECHA' in df_p.columns:
                    df_p['FECHA'] = df_p['FECHA'].apply(self._fecha_sin_hora_str)
                self._escribir_excel_formateado(path, df_p, sheet_name="Movimientos", highlight_col="CANTIDAD")

    def _finalizar_carga_actual(self):
        if not self._salidas_pendientes:
            return messagebox.showwarning("Carga actual", "No hay ítems precargados para finalizar.", parent=self.root)
        if not messagebox.askyesno("Confirmar", f"¿Confirmar {len(self._salidas_pendientes)} ítem(s) y grabar en Excel?", parent=self.root):
            return
        try:
            pendientes = list(self._salidas_pendientes.values())
            sync_por_codigo = {}
            for p in pendientes:
                fila = p["fila"]
                cod = fila.get("CODIGO")
                s, df, idx, col_s = self._buscar_stock_item_master(cod)
                if df is None:
                    return messagebox.showerror("Error", f"No se encontró el código {cod} en el maestro.")
                stk_act = pd.to_numeric(df.at[idx, col_s], errors='coerce')
                actual = 0.0 if pd.isna(stk_act) else float(stk_act)
                nuevo_stock = actual - float(fila.get("CANTIDAD", 0) or 0)
                self._set_cell_numeric_safe(df, idx, col_s, nuevo_stock)
                sync_por_codigo[cod] = (nuevo_stock, fila.get("DESCRIPCION", ""), fila.get("UBICACION", ""), s)

            self._guardar_movimientos_batch(pendientes)

            if firebase_conectado:
                for cod, info in sync_por_codigo.items():
                    threading.Thread(
                        target=self.sincronizar_item_a_firebase,
                        args=(cod, info[0], info[1], info[2], info[3]),
                        daemon=True,
                    ).start()

            self.actualizar_contadores_reposicion()
            self.limpiar_total()
            messagebox.showinfo("Éxito", "Carga finalizada y guardada en Excel.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo finalizar la carga:\n{e}", parent=self.root)

    def restablecer_salidas(self):
        if messagebox.askyesno("Advertencia", "¿Borrar datos no guardados?"):
            self.limpiar_total()

    def enfocar_siguiente(self, event):
        event.widget.tk_focusNext().focus()
        return "break"

    def _on_enter_cantidad(self, event):
        # Cuando la orden ya está bloqueada (2º ítem en adelante con la misma
        # orden), los campos superiores están deshabilitados: el Enter en
        # Cantidad debe registrar la salida directamente para agilizar la carga.
        if getattr(self, "_formulario_orden_bloqueada", False):
            self.btn_save.invoke()
            return "break"
        return self.enfocar_siguiente(event)

    def create_label(self, parent, text, row):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="e", padx=5)

    def create_readonly(self, parent, text, var, row):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="e", padx=5)
        ttk.Entry(parent, textvariable=var, state="readonly", takefocus=False).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)

    def _configurar_combobox_predictivo(self, combo, valores, valores_mayusculas=True):
        vals = [str(v).strip() for v in (valores or []) if str(v).strip()]
        if valores_mayusculas:
            vals = [v.upper() for v in vals]
        combo._all_values = vals
        combo['values'] = vals

        if not getattr(combo, "_predictivo_bound", False):
            combo.bind("<KeyRelease>", lambda e, cb=combo: self._filtrar_combobox_predictivo(cb, e), add="+")
            combo._predictivo_bound = True

    def _restaurar_lista_completa_combobox(self, combo):
        vals = getattr(combo, '_all_values', None)
        if vals is not None:
            combo['values'] = list(vals)

    def _filtrar_combobox_predictivo(self, combo, event=None):
        keys_skip = {
            'Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape',
            'Control_L', 'Control_R', 'Shift_L', 'Shift_R', 'Alt_L', 'Alt_R'
        }
        if event is not None and event.keysym in keys_skip:
            return
        base = list(getattr(combo, "_all_values", []))
        if not base:
            return
        txt = combo.get().strip().lower()
        if not txt:
            combo['values'] = base
            return
        filtrados = [v for v in base if txt in v.lower()]
        combo['values'] = filtrados if filtrados else base

    def _set_formulario_misma_orden_bloqueado(self, bloqueado):
        """Tras «misma orden», sólo código y cantidad editables (y buscar)."""
        self._formulario_orden_bloqueada = bool(bloqueado)
        st = 'disabled' if bloqueado else 'normal'
        st_combo = 'disabled' if bloqueado else 'normal'
        try:
            self.date_entry.configure(state=st)
        except (tk.TclError, AttributeError):
            pass
        self.cmb_tipo.configure(state=st_combo)
        self.ent_orden.configure(state=st)
        self.ent_maquina.configure(state=st)
        self.cmb_ope.configure(state=st_combo)
        if bloqueado:
            self.cmb_ope_det.configure(state='disabled')
        else:
            self.on_sector_change()
        self.ent_codigo.configure(state='normal')
        self.ent_cant.configure(state='normal')

    def _normalizar_operario(self, txt):
        return str(txt).strip().lower()

    def _resolver_sector_texto(self, txt):
        n = self._norm_header_imp(str(txt)).strip().lower()
        if not n:
            return ""
        if n.startswith("prod"):
            return "produccion"
        if n.startswith("proy"):
            return "proyectos"
        if n.startswith("mant"):
            return "mantenimiento"
        if n.startswith("edil"):
            return "edilicio"
        if n in ("produccion", "proyectos", "mantenimiento", "edilicio"):
            return n
        if self.sector_operarios_map and n in self.sector_operarios_map:
            return n
        return n

    def on_sector_change(self, event=None):
        sector = self._resolver_sector_texto(self.cmb_ope.get())
        operarios_sector = self.sector_operarios_map.get(sector, [])
        if sector and operarios_sector:
            self._configurar_combobox_predictivo(self.cmb_ope_det, operarios_sector)
            self.cmb_ope_det.set("")
            self.cmb_ope_det.configure(state="normal")
            self.cmb_ope_det.focus_set()
        elif sector == "proyectos":
            self._configurar_combobox_predictivo(self.cmb_ope_det, self.operarios_proyectos)
            self.cmb_ope_det.set("")
            self.cmb_ope_det.configure(state="normal")
            self.cmb_ope_det.focus_set()
        elif sector == "mantenimiento":
            excluidos = {self._normalizar_operario(x) for x in (["produccion", "proyectos", "mantenimiento", "edilicio"] + self.operarios_proyectos)}
            restantes = [o for o in self.lista_operarios if self._normalizar_operario(o) not in excluidos]
            self._configurar_combobox_predictivo(self.cmb_ope_det, restantes)
            self.cmb_ope_det.set("")
            self.cmb_ope_det.configure(state="normal")
            self.cmb_ope_det.focus_set()
        elif sector == "edilicio":
            self._configurar_combobox_predictivo(self.cmb_ope_det, operarios_sector if operarios_sector else self.lista_operarios)
            self.cmb_ope_det.set("")
            self.cmb_ope_det.configure(state="normal")
            self.cmb_ope_det.focus_set()
        elif sector == "produccion":
            self._configurar_combobox_predictivo(self.cmb_ope_det, operarios_sector if operarios_sector else self.lista_operarios)
            self.cmb_ope_det.set("")
            self.cmb_ope_det.configure(state="normal")
            self.cmb_ope_det.focus_set()
        else:
            self.cmb_ope_det.set("")
            self.cmb_ope_det['values'] = []
            self.cmb_ope_det.configure(state="disabled")

    def obtener_sector_operario(self):
        sector = self._resolver_sector_texto(self.cmb_ope.get())
        if not sector:
            return None, None

        if sector == "produccion":
            detalle_prod = str(self.cmb_ope_det.get()).strip()
            return "PRODUCCION", (detalle_prod.upper() if detalle_prod else "PRODUCCION")

        detalle = str(self.cmb_ope_det.get()).strip()
        if not detalle:
            return None, None
        if sector == "proyectos":
            return "PROYECTOS", detalle.upper()
        if sector == "edilicio":
            return "EDILICIO", detalle.upper()
        return sector.upper(), detalle.upper()

    def auto_load_all(self):
        ruta = None
        if os.path.exists(BASE_DATOS_DEFAULT):
            ruta = BASE_DATOS_DEFAULT
        elif os.path.exists(MASTER_LEGACY):
            ruta = MASTER_LEGACY
        if ruta:
            self.process_master_load(ruta)
            estado_nube = " | ☁️ Nube OK" if firebase_conectado else " | 🔴 Sin Nube"
            self.lbl_status.config(text=f"Base de datos cargada OK{estado_nube}", foreground="green")
            self.chequear_y_enviar_reporte_diario()

    def load_master(self):
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if p:
            self.process_master_load(p)

    def process_master_load(self, path):
        try:
            xls = pd.ExcelFile(path)
            self.master_dict = {}
            self.categoria_map = {}
            bloques_df = []
            for sheet in xls.sheet_names:
                sheet_lower = sheet.lower().strip()
                if sheet_lower == 'config':
                    self.config_df = pd.read_excel(xls, sheet_name=sheet)
                    if 'operarios' in self.config_df.columns:
                        self.lista_operarios = [str(x).strip().upper() for x in self.config_df['operarios'].dropna().astype(str).tolist()]
                        if hasattr(self, 'cmb_ope'):
                            self._configurar_combobox_predictivo(self.cmb_ope, self.sectores_operario)
                            self.on_sector_change()
                    if 'comprobantes' in self.config_df.columns:
                        self.tipos_comprobante = self.config_df['comprobantes'].dropna().astype(str).tolist()
                        self._configurar_combobox_predictivo(self.cmb_tipo, self.tipos_comprobante)
                    self._cargar_relaciones_sector_operario_desde_config()
                    if self.sector_operarios_map:
                        self.sectores_operario = sorted({str(s).strip().upper() for s in self.sector_operarios_map.keys()})
                        self._asegurar_sectores_base()
                        if hasattr(self, 'cmb_ope'):
                            self._configurar_combobox_predictivo(self.cmb_ope, self.sectores_operario)
                            if hasattr(self, 'cmb_seg_sector'):
                                self._configurar_combobox_predictivo(self.cmb_seg_sector, self.sectores_operario)
                elif sheet_lower == 'correos':
                    self.correos_df = pd.read_excel(xls, sheet_name=sheet)
                else:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    df.columns = [str(c).lower().strip() for c in df.columns]
                    if 'codigo' not in df.columns:
                        continue
                    df['codigo'] = df['codigo'].astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)
                    for cod in df['codigo'].dropna():
                        self.categoria_map[str(cod).upper()] = sheet
                    if self._col_importancia(df) is None:
                        df['importancia'] = self._importancia_desde_nombre_hoja(sheet)
                    bloques_df.append(df)

            if bloques_df:
                merged = pd.concat(bloques_df, ignore_index=True, sort=False)
                merged = merged.drop_duplicates(subset=['codigo'], keep='last')
                merged = self._limpiar_columnas_precio_duplicadas_df(merged)
                if self._col_importancia(merged) is None:
                    merged['importancia'] = 'BASE'
                else:
                    col_imp = self._col_importancia(merged)
                    merged[col_imp] = merged[col_imp].apply(self._normalizar_criticidad_maestro)
                self.master_dict[HOJA_ARTICULOS] = merged

            self.master_file_path = path
            self.lbl_status.config(text="Base unificada cargada", foreground="green")
            self.actualizar_contadores_reposicion()
        except Exception as e:
            messagebox.showerror("Error Base de datos", str(e))

    def procesar_codigo_y_avanzar(self, event=None):
        cod = self.codigo_var.get().strip().upper()
        if not self.master_dict or not cod: return "break"
        ubic_map = self._construir_mapa_ubicaciones_master()
        ubic_preferida = ubic_map.get(cod)
        encontrado = False
        for sheet_name, df in self.master_dict.items():
            if 'codigo' not in df.columns: continue
            match = df[df['codigo'] == cod]
            if not match.empty:
                row = match.iloc[0]
                if ubic_preferida:
                    for _, cand in match.iterrows():
                        if self._obtener_ubicacion_desde_row(cand, df.columns) == ubic_preferida:
                            row = cand
                            break
                desc = next((str(row.get(c, '')).upper() for c in ['descripcion', 'descripción', 'detalle', 'articulo'] if c in df.columns), "")
                self.desc_var.set(desc)
                col_p = self._col_precio_unitario_df(df)
                precio = pd.to_numeric(row.get(col_p, 0), errors='coerce') if col_p else 0
                px = 0.0 if pd.isna(precio) else float(precio)
                self.precio_var.set(self._formato_precio_unit_ui(px))
                ubic = self._obtener_ubicacion_desde_row(row, df.columns)
                self.stk_ubic_var.set(ubic)
                stk = next((pd.to_numeric(row.get(c, 0), errors='coerce') for c in ['stock', 'stock actual', 'stock_actual', 'cantidad'] if c in df.columns), 0)
                self.stk_actual_var.set(0 if pd.isna(stk) else stk)
                col_m = next((c for c in df.columns if 'min' in self._norm_header_imp(str(c))), None)
                if col_m:
                    mn = pd.to_numeric(row.get(col_m, 0), errors='coerce')
                    self.stk_min_var.set(0 if pd.isna(mn) else mn)
                else:
                    self.stk_min_var.set("-")
                encontrado = True; break
        if not encontrado: return messagebox.showwarning("Error", "Código no existe."); return "break"
        self.ent_cant.focus_set(); return "break"

    def chequear_y_enviar_reporte_diario(self):
        # Mantiene compatibilidad con llamados existentes: dispara la verificación del scheduler.
        self._verificar_envio_programado_730()

    def iniciar_programador_730(self):
        if self.scheduler_iniciado:
            return
        self.scheduler_iniciado = True
        self._verificar_envio_programado_730()

    def _leer_fecha_envio(self, path):
        if not os.path.exists(path):
            return ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return ""

    def _es_hora_objetivo(self):
        ahora = datetime.now()
        return (ahora.hour > 7) or (ahora.hour == 7 and ahora.minute >= 30)

    def _es_hora_objetivo_mensual(self):
        ahora = datetime.now()
        return ahora.day >= 2 and ((ahora.hour > 7) or (ahora.hour == 7 and ahora.minute >= 30))

    def _verificar_envio_programado_730(self):
        try:
            hoy = datetime.today().strftime('%Y-%m-%d')
            repo_enviado_hoy = self._leer_fecha_envio(LAST_MAIL_FILE) == hoy
            gastos_enviado_hoy = self._leer_fecha_envio(LAST_MAIL_GASTOS_FILE) == hoy
            seg_enviado_hoy = self._leer_fecha_envio(LAST_MAIL_SEGUIMIENTO_FILE) == hoy

            if (
                not self.correos_df.empty
                and self._correo_destinatario_primario()
                and self._es_hora_objetivo()
                and (not repo_enviado_hoy or not gastos_enviado_hoy or not seg_enviado_hoy)
            ):
                if not self.envio_auto_en_progreso:
                    self.envio_auto_en_progreso = True
                    threading.Thread(target=self._enviar_reportes_automaticos_730, daemon=True).start()
        finally:
            # Revisa cada minuto para no depender de que el usuario reinicie la app.
            self.root.after(60_000, self._verificar_envio_programado_730)

    def _buscar_archivo_salidas_ultimo_dia(self):
        fecha_ref = (datetime.today().date() - timedelta(days=1))
        archivo = os.path.join(BASE_DIR, f"salidas_{fecha_ref.strftime('%d-%m-%Y')}.xlsx")
        if os.path.exists(archivo):
            return archivo, fecha_ref
        return None

    def _clasificar_sector(self, operario):
        t = str(operario).strip().lower()
        if t == "produccion":
            return "PRODUCCION"
        if t == "edilicio" or t.startswith("edil"):
            return "EDILICIO"
        for sec, ops in self.sector_operarios_map.items():
            if t == sec or t in [self._normalizar_operario(x) for x in ops]:
                return sec.upper()
        if t in ("proyectos", "maccaroni", "valenzuela"):
            return "PROYECTOS"
        return "MANTENIMIENTO"

    def _generar_reporte_gastos_sector(self, fecha_reporte=None):
        """
        Genera Excel y cuerpos de mail (texto + HTML) para gastos del día `fecha_reporte`.
        Si fecha_reporte es None, usa el día anterior (reporte automático).
        """
        if fecha_reporte is None:
            fecha_ref = datetime.today().date() - timedelta(days=1)
        else:
            fecha_ref = fecha_reporte if isinstance(fecha_reporte, date) else fecha_reporte.date()

        df, col_operario, col_monto, err_load = self._cargar_movimientos_fecha_gastos(fecha_ref)
        if df is None or df.empty:
            return None, fecha_ref, "", "", err_load or "Sin movimientos para la fecha indicada."

        presentes_mes = self._coleccionar_sectores_presentes_en_mes(fecha_ref)
        presentes_dia = set(str(s).strip().upper() for s in df["SECTOR"].dropna().unique())
        presentes = presentes_mes | presentes_dia
        orden_informe = self._orden_sectores_para_informe(presentes)

        totales_dia_sector, dias_mes = self._totales_mes_por_dia_y_sector(fecha_ref, orden_informe)
        fecha_key = self._formato_fecha_escrita(fecha_ref)

        acum_mes_sector = {code: 0.0 for code, _ in orden_informe}
        for fd in dias_mes:
            k = self._formato_fecha_escrita(fd)
            tds = totales_dia_sector.get(k, {})
            for code, _ in orden_informe:
                acum_mes_sector[code] += tds.get(code, 0.0)

        resumen_html = []
        cuadros_html = []
        lineas_txt = [
            f"Reporte de gastos por sector — día {self._formato_fecha_escrita(fecha_ref)} (movimientos retirados ese día).",
            "",
        ]
        cuadros_txt = []

        for num, (code, etiqueta) in enumerate(orden_informe, start=1):
            intro_txt = (
                f"Reporte correspondiente a retiros registrados el {self._formato_fecha_escrita(fecha_ref)} "
                f"(sector {etiqueta})."
            )
            est = self._estilo_sector_html(code)
            intro_html = (
                f'<p style="font-family:Arial,sans-serif;font-size:13px;margin:12px 0 6px 0;'
                f'color:{est["title"]};padding:8px;background:{est["bg"]};border-left:4px solid {est["border"]};">'
                f'Reporte correspondiente a retiros registrados el <b>{html.escape(self._formato_fecha_escrita(fecha_ref))}</b> '
                f'— sector <b>{html.escape(etiqueta)}</b>.</p>'
            )
            lineas_txt.extend(["", intro_txt, ""])
            resumen_html.append(intro_html)

            g_dia = totales_dia_sector.get(fecha_key, {}).get(code, 0.0)
            acum = acum_mes_sector.get(code, 0.0)
            resumen_html.append(self._bloque_resumen_sector_html(num, etiqueta, code, g_dia, acum))
            lineas_txt.extend([
                f"{num}. {etiqueta}:",
                f"   Gasto del día {self._formato_pesos_ar(g_dia)}",
                f"   Total acumulado del mes: {self._formato_pesos_ar(acum)}",
                "",
            ])

            df_s = df[df["SECTOR"] == code].copy()
            detalle_cols = [c for c in [
                "FECHA", "CODIGO", "DESCRIPCION", "CANTIDAD", "PRECIO_UNITARIO",
                "MONTO_TOTAL_SALIDA", "TIPO_COMPROBANTE", "NUMERO_ORDEN", "MAQUINA_SITIO", "OPERARIO"
            ] if c in df_s.columns]
            if detalle_cols and not df_s.empty:
                df_s = df_s.sort_values(by=[col_operario]).copy()
                cab = [str(c).replace("_", " ") for c in detalle_cols]
                filas_h = []
                for _, row in df_s.iterrows():
                    fila = []
                    for c in detalle_cols:
                        v = row.get(c, "")
                        if c == "PRECIO_UNITARIO":
                            fila.append(self._formato_precio_unit_ui(v))
                        elif c == "MONTO_TOTAL_SALIDA":
                            fila.append(self._formato_pesos_ar(v))
                        else:
                            fila.append(v if pd.notna(v) else "")
                    filas_h.append(fila)
                cuadros_html.append(self._tabla_html_simple(f"Detalle de retiros — {etiqueta}", cab, filas_h, code))
                cuadros_txt.append(f"--- Detalle {etiqueta} ({len(df_s)} líneas) ---")
                for _, row in df_s.iterrows():
                    partes = [f"{c}={row.get(c, '')}" for c in detalle_cols]
                    cuadros_txt.append(" | ".join(str(p) for p in partes))
                cuadros_txt.append("")

            if code == "MANTENIMIENTO":
                gastos_linea = self._gastos_por_linea_mantenimiento_mes(fecha_ref)
                if gastos_linea:
                    filas_linea = [(ln, self._formato_pesos_ar(m)) for ln, m in gastos_linea]
                    cuadros_html.append(self._tabla_html_simple(
                        "Gastos por línea — Mantenimiento (acumulado del mes)",
                        ["Línea", "Total gastado"],
                        filas_linea,
                        "MANTENIMIENTO",
                    ))
                    cuadros_txt.append("--- Gastos por línea (Mantenimiento, mes) ---")
                    for ln, m in gastos_linea:
                        cuadros_txt.append(f"  {ln}: {self._formato_pesos_ar(m)}")
                    cuadros_txt.append("")

            acum_run = 0.0
            filas_mini = []
            for fd in dias_mes:
                k = self._formato_fecha_escrita(fd)
                g = totales_dia_sector.get(k, {}).get(code, 0.0)
                acum_run += g
                filas_mini.append((k, self._formato_pesos_ar(g), self._formato_pesos_ar(acum_run)))
            cuadros_html.append(self._tabla_html_simple(
                f"Resumen día a día — {etiqueta}",
                ["Fecha", "Gasto del día (sector)", "Acumulado mes (sector)"],
                filas_mini,
                code,
            ))
            cuadros_txt.append(f"--- Día a día {etiqueta} ---")
            for k, a, b in filas_mini:
                cuadros_txt.append(f"  {k}  |  {a}  |  {b}")
            cuadros_txt.append("")

        codes_list = [c for c, _ in orden_informe]
        etiquetas_tot = [et for _, et in orden_informe]
        filas_tot = []
        sumas = {c: 0.0 for c in codes_list}
        for fd in dias_mes:
            k = self._formato_fecha_escrita(fd)
            tds = totales_dia_sector.get(k, {})
            vals_fmt = []
            td = 0.0
            for c in codes_list:
                v = float(tds.get(c, 0.0))
                td += v
                sumas[c] += v
                vals_fmt.append(self._formato_pesos_ar(v))
            filas_tot.append((k, *vals_fmt, self._formato_pesos_ar(td)))
        fila_total_vals = [self._formato_pesos_ar(sumas[c]) for c in codes_list]
        filas_tot.append(("Total general", *fila_total_vals, self._formato_pesos_ar(sum(sumas.values()))))
        hdr_tot = ["Fecha"] + etiquetas_tot + ["Total día"]
        cuadros_html.append(self._tabla_html_simple(
            "Total general por día (todos los sectores)",
            hdr_tot,
            filas_tot,
        ))
        cuadros_txt.extend(["--- Total general por día ---"])
        for fila in filas_tot:
            cuadros_txt.append("  " + " | ".join(str(x) for x in fila))
        lineas_txt.extend(["", "Cuadros de respaldo:", ""])
        lineas_txt.extend(cuadros_txt)
        cuerpo_html = (
            '<div style="font-family:Arial,sans-serif;color:#222;">'
            + "".join(resumen_html)
            + '<p style="font-size:14px;margin-top:14px;"><b>Cuadros de respaldo:</b></p>'
            + "".join(cuadros_html)
            + '<p style="font-size:11px;color:#555;">Totales alineados con el archivo diario de salidas y el mes en curso.</p>'
            + '</div>'
        )
        cuerpo_txt = "\n".join(lineas_txt)

        registros_mes_global = []
        for fd in dias_mes:
            k = self._formato_fecha_escrita(fd)
            tds = totales_dia_sector.get(k, {})
            sm = sum(tds.get(code, 0.0) for code, _ in orden_informe)
            registros_mes_global.append({"FECHA": k, "GASTO_DIA_TOTAL": sm})
        df_mes = pd.DataFrame(registros_mes_global)
        if not df_mes.empty:
            df_mes["ACUMULADO_MES"] = df_mes["GASTO_DIA_TOTAL"].cumsum()

        resumen_rows = []
        for code, etiqueta in orden_informe:
            g_dia = totales_dia_sector.get(fecha_key, {}).get(code, 0.0)
            acum = acum_mes_sector.get(code, 0.0)
            resumen_rows.append({
                "SECTOR": etiqueta,
                "GASTO_DIA": g_dia,
                "ACUMULADO_MES": acum,
            })
        resumen = pd.DataFrame(resumen_rows)
        total_dia = float(df[col_monto].sum())
        acum_total_mes = 0.0
        if not df_mes.empty:
            acum_total_mes = float(df_mes["ACUMULADO_MES"].iloc[-1])
        resumen.loc[len(resumen)] = ["TOTAL DÍA (todos)", total_dia, acum_total_mes]

        fecha_arch = fecha_ref.strftime("%Y-%m-%d")
        out_path = os.path.join(BASE_DIR, f"Reporte_Gastos_Sector_{fecha_arch}.xlsx")
        cols_df_tot = ["FECHA"] + etiquetas_tot + ["TOTAL_DIA"]
        with pd.ExcelWriter(out_path, engine='xlsxwriter') as writer:
            resumen.to_excel(writer, index=False, sheet_name="RESUMEN")
            wb = writer.book
            ws_res = writer.sheets["RESUMEN"]
            hfmt = wb.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1, 'align': 'center'})
            bfmt = wb.add_format({'border': 1})
            mfmt = wb.add_format({'bold': True, 'font_color': '#C00000', 'border': 1})
            for col_num, col_name in enumerate(resumen.columns):
                ws_res.write(0, col_num, str(col_name), hfmt)
                ws_res.set_column(col_num, col_num, 22, bfmt)
            for r in range(len(resumen)):
                es_tot = 'TOTAL' in str(resumen.iloc[r, 0]).upper()
                ws_res.write(r + 1, 1, resumen.iloc[r, 1], mfmt if es_tot else bfmt)
                if len(resumen.columns) > 2:
                    ws_res.write(r + 1, 2, resumen.iloc[r, 2], mfmt if es_tot else bfmt)
            ws_res.autofilter(0, 0, len(resumen), len(resumen.columns) - 1)
            ws_res.freeze_panes(1, 0)
            self._aplicar_formato_monto_ws(ws_res, wb, resumen)

            if not df_mes.empty:
                df_mes.to_excel(writer, index=False, sheet_name="MES_DIA_A_DIA")
                ws_m = writer.sheets["MES_DIA_A_DIA"]
                for col_num, col_name in enumerate(df_mes.columns):
                    ws_m.write(0, col_num, str(col_name), hfmt)
                    ws_m.set_column(col_num, col_num, 18, bfmt)
                ws_m.autofilter(0, 0, len(df_mes), len(df_mes.columns) - 1)
                ws_m.freeze_panes(1, 0)

            df_tot = pd.DataFrame(filas_tot, columns=cols_df_tot)
            df_tot.to_excel(writer, index=False, sheet_name="TOTAL_GENERAL_MES")

            detalle_cols = [c for c in [
                "FECHA", "CODIGO", "DESCRIPCION", "CANTIDAD", "PRECIO_UNITARIO",
                "MONTO_TOTAL_SALIDA", "TIPO_COMPROBANTE", "NUMERO_ORDEN", "MAQUINA_SITIO", "OPERARIO"
            ] if c in df.columns]
            for code, _ in orden_informe:
                df_s = df[df["SECTOR"] == code].copy()
                if df_s.empty:
                    continue
                df_s = df_s.sort_values(by=[col_operario]).copy()
                df_s = df_s[detalle_cols]
                sheet = code[:31]
                df_s.to_excel(writer, index=False, sheet_name=sheet)
                ws = writer.sheets[sheet]
                for col_num, col_name in enumerate(df_s.columns):
                    ws.write(0, col_num, str(col_name), hfmt)
                    ws.set_column(col_num, col_num, min(max(14, len(str(col_name)) + 3), 45), bfmt)
                ws.autofilter(0, 0, len(df_s), len(df_s.columns) - 1)
                ws.freeze_panes(1, 0)
                self._aplicar_formato_monto_ws(ws, wb, df_s)
        adjunto_diario = self._ruta_archivo_salidas_dia(fecha_ref)
        if not os.path.exists(adjunto_diario):
            adjunto_diario = out_path
        return adjunto_diario, fecha_ref, cuerpo_txt, cuerpo_html, ""

    def _gastos_dia_por_linea_mantenimiento_mes(self, fecha_ref, dias_mes):
        """Por cada día del mes: total de mantenimiento desglosado por línea/pañol."""
        dia_linea = {}
        for fd in dias_mes:
            k = self._formato_fecha_escrita(fd)
            dia_linea[k] = {}
            df_d, _, _, _ = self._cargar_movimientos_fecha_gastos(fd)
            if df_d is None or df_d.empty or "TIPO_COMPROBANTE" not in df_d.columns:
                continue
            dm = df_d[df_d["SECTOR"].astype(str).str.upper() == "MANTENIMIENTO"].copy()
            if dm.empty:
                continue
            dm["MONTO_TOTAL_SALIDA"] = pd.to_numeric(dm.get("MONTO_TOTAL_SALIDA", 0), errors="coerce").fillna(0.0)
            dm["_LINEA"] = dm["TIPO_COMPROBANTE"].apply(self._normalizar_linea_gasto)
            g = dm.groupby("_LINEA")["MONTO_TOTAL_SALIDA"].sum()
            for ln in g.index:
                dia_linea[k][str(ln)] = float(g[ln])
        return dia_linea

    def _generar_reporte_mensual_gastos(self, fecha_mes):
        year, month = fecha_mes.year, fecha_mes.month
        # Cubrir el mes completo sin importar qué día se reciba (los helpers cortan
        # en d <= fecha). En el mes en curso no se va más allá de hoy.
        if month == 12:
            ultimo_dia_mes = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            ultimo_dia_mes = date(year, month + 1, 1) - timedelta(days=1)
        hoy = date.today()
        if year == hoy.year and month == hoy.month:
            fecha_cobertura = min(ultimo_dia_mes, hoy)
        else:
            fecha_cobertura = ultimo_dia_mes

        presentes = self._coleccionar_sectores_presentes_en_mes(fecha_cobertura)
        if not presentes:
            return None, "", "", "Sin movimientos para el mes elegido."
        orden_informe = self._orden_sectores_para_informe(presentes)
        codes = [c for c, _ in orden_informe]
        etiquetas = [et for _, et in orden_informe]
        etiqueta_de = {c: et for c, et in orden_informe}

        totales_dia_sector, dias_mes = self._totales_mes_por_dia_y_sector(fecha_cobertura, orden_informe)

        # Totales del mes por sector y total general.
        total_sector = {c: 0.0 for c in codes}
        for fd in dias_mes:
            k = self._formato_fecha_escrita(fd)
            tds = totales_dia_sector.get(k, {})
            for c in codes:
                total_sector[c] += float(tds.get(c, 0.0))
        total_mes = sum(total_sector.values())

        # Desglose de Mantenimiento por línea/pañol (mes).
        gastos_linea = self._gastos_por_linea_mantenimiento_mes(fecha_cobertura)
        lineas_presentes = [ln for ln, _ in gastos_linea]
        gl_map = {ln: m for ln, m in gastos_linea}
        total_mant = sum(gl_map.values())
        dia_linea = self._gastos_dia_por_linea_mantenimiento_mes(fecha_cobertura, dias_mes)

        # ---------------- Cuerpo de texto plano ----------------
        txt = [f"Reporte mensual de gastos — {month:02d}/{year}.", ""]
        txt.append(f"TOTAL GASTADO EN EL MES: {self._formato_pesos_ar(total_mes)}")
        txt.append("")
        txt.append("Gasto por sector:")
        for c in codes:
            txt.append(f"  {etiqueta_de[c]}: {self._formato_pesos_ar(total_sector[c])}")
        txt.append("")
        if gastos_linea:
            txt.append("Desglose de Mantenimiento por línea / pañol:")
            for ln in lineas_presentes:
                txt.append(f"  {ln}: {self._formato_pesos_ar(gl_map[ln])}")
            txt.append(f"  TOTAL MANTENIMIENTO: {self._formato_pesos_ar(total_mant)}")
            txt.append("")

        # ---------------- Cuerpo HTML ----------------
        html_bloques = []
        html_bloques.append(
            f'<p style="font-family:Arial,sans-serif;font-size:16px;color:#111;margin:6px 0 12px 0;">'
            f'<b>Total gastado en el mes {month:02d}/{year}: {self._formato_pesos_ar(total_mes)}</b></p>'
        )
        for i, c in enumerate(codes, start=1):
            est = self._estilo_sector_html(c)
            html_bloques.append(
                f'<div style="font-family:Arial,sans-serif;margin:8px 0;padding:10px 14px;'
                f'background:{est["bg"]};border-left:5px solid {est["border"]};border-radius:4px;">'
                f'<p style="margin:0;font-size:15px;color:{est["title"]};"><b>{i}. {html.escape(etiqueta_de[c])}</b></p>'
                f'<p style="margin:4px 0 0 0;font-size:13px;color:#333;">'
                f'Gasto total del mes: <b>{self._formato_pesos_ar(total_sector[c])}</b></p></div>'
            )

        # Tabla: gasto por sector.
        filas_sec = [(etiqueta_de[c], self._formato_pesos_ar(total_sector[c])) for c in codes]
        filas_sec.append(("TOTAL", self._formato_pesos_ar(total_mes)))
        tabla_sec_html = self._tabla_html_simple(
            "Gasto por sector (mes)", ["Sector", "Total mes"], filas_sec,
        )

        # Tabla: desglose mantenimiento por línea/pañol.
        tabla_lin_html = ""
        if gastos_linea:
            filas_ln = [(ln, self._formato_pesos_ar(gl_map[ln])) for ln in lineas_presentes]
            filas_ln.append(("TOTAL MANTENIMIENTO", self._formato_pesos_ar(total_mant)))
            tabla_lin_html = self._tabla_html_simple(
                "Desglose de Mantenimiento por línea y pañol (mes)",
                ["Línea / Pañol", "Total mes"], filas_ln, "MANTENIMIENTO",
            )

        # Tabla: gasto por día y sector (sólo días con movimiento, en orden de fecha).
        filas_ds = []
        for fd in dias_mes:
            k = self._formato_fecha_escrita(fd)
            tds = totales_dia_sector.get(k, {})
            tot = sum(float(tds.get(c, 0.0)) for c in codes)
            if tot == 0:
                continue
            vals = [self._formato_pesos_ar(float(tds.get(c, 0.0))) for c in codes]
            filas_ds.append((k, *vals, self._formato_pesos_ar(tot)))
        filas_ds.append((
            "TOTAL MES",
            *[self._formato_pesos_ar(total_sector[c]) for c in codes],
            self._formato_pesos_ar(total_mes),
        ))
        tabla_ds_html = self._tabla_html_simple(
            "Gasto por día y sector (mes)", ["Fecha"] + etiquetas + ["Total día"], filas_ds,
        )

        # Tabla: mantenimiento por día y línea/pañol.
        tabla_dl_html = ""
        if lineas_presentes:
            filas_dl = []
            for fd in dias_mes:
                k = self._formato_fecha_escrita(fd)
                dl = dia_linea.get(k, {})
                tot = sum(dl.values())
                if tot == 0:
                    continue
                vals = [self._formato_pesos_ar(dl.get(ln, 0.0)) for ln in lineas_presentes]
                filas_dl.append((k, *vals, self._formato_pesos_ar(tot)))
            filas_dl.append((
                "TOTAL MES",
                *[self._formato_pesos_ar(gl_map[ln]) for ln in lineas_presentes],
                self._formato_pesos_ar(total_mant),
            ))
            tabla_dl_html = self._tabla_html_simple(
                "Mantenimiento: gasto por día y línea/pañol (mes)",
                ["Fecha"] + lineas_presentes + ["Total día"], filas_dl, "MANTENIMIENTO",
            )

        body_txt = "\n".join(txt)
        body_html = (
            '<div style="font-family:Arial,sans-serif;color:#222;">'
            + f'<p style="font-size:14px;">Reporte mensual correspondiente a <b>{month:02d}/{year}</b>. '
            + 'Los gráficos comparativos están en el Excel adjunto.</p>'
            + "".join(html_bloques)
            + tabla_sec_html
            + tabla_lin_html
            + tabla_ds_html
            + tabla_dl_html
            + '<p style="font-size:11px;color:#555;">El gasto de Mantenimiento se desglosa por línea (L1…L7) y pañol; '
            + 'el resto de los sectores no se desglosa.</p>'
            + "</div>"
        )

        # ---------------- Excel con gráficos ----------------
        out_path = os.path.join(BASE_DIR, f"Reporte_Gastos_Mensual_{year}_{month:02d}.xlsx")
        with pd.ExcelWriter(out_path, engine='xlsxwriter') as writer:
            wb = writer.book
            hfmt = wb.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1, 'align': 'center'})
            bfmt = wb.add_format({'border': 1})
            money_fmt = wb.add_format({'num_format': '$ #,##0.00', 'border': 1})
            tot_fmt = wb.add_format({'num_format': '$ #,##0.00', 'border': 1, 'bold': True, 'font_color': '#C00000'})

            # Hoja RESUMEN_SECTOR + gráfico de torta.
            ws_sec = wb.add_worksheet("RESUMEN_SECTOR")
            ws_sec.write(0, 0, "SECTOR", hfmt)
            ws_sec.write(0, 1, "TOTAL_MES", hfmt)
            for r, c in enumerate(codes):
                ws_sec.write(r + 1, 0, etiqueta_de[c], bfmt)
                ws_sec.write_number(r + 1, 1, round(float(total_sector[c]), 2), money_fmt)
            fila_tot = len(codes) + 1
            ws_sec.write(fila_tot, 0, "TOTAL", hfmt)
            ws_sec.write_number(fila_tot, 1, round(float(total_mes), 2), tot_fmt)
            ws_sec.set_column(0, 0, 22, bfmt)
            ws_sec.set_column(1, 1, 18, money_fmt)
            if len(codes) >= 1 and total_mes > 0:
                ch_sec = wb.add_chart({'type': 'pie'})
                ch_sec.add_series({
                    'name': f'Gasto por sector {month:02d}/{year}',
                    'categories': ['RESUMEN_SECTOR', 1, 0, len(codes), 0],
                    'values': ['RESUMEN_SECTOR', 1, 1, len(codes), 1],
                    'data_labels': {'percentage': True, 'category': True},
                })
                ch_sec.set_title({'name': f'Gasto por sector — {month:02d}/{year}'})
                ch_sec.set_size({'width': 520, 'height': 360})
                ws_sec.insert_chart('D2', ch_sec)

            # Hoja POR_LINEA_MANT + gráfico de columnas.
            if lineas_presentes:
                ws_ln = wb.add_worksheet("POR_LINEA_MANT")
                ws_ln.write(0, 0, "LINEA_PAÑOL", hfmt)
                ws_ln.write(0, 1, "TOTAL_MES", hfmt)
                for r, ln in enumerate(lineas_presentes):
                    ws_ln.write(r + 1, 0, ln, bfmt)
                    ws_ln.write_number(r + 1, 1, round(float(gl_map[ln]), 2), money_fmt)
                fila_tl = len(lineas_presentes) + 1
                ws_ln.write(fila_tl, 0, "TOTAL MANT.", hfmt)
                ws_ln.write_number(fila_tl, 1, round(float(total_mant), 2), tot_fmt)
                ws_ln.set_column(0, 0, 18, bfmt)
                ws_ln.set_column(1, 1, 18, money_fmt)
                if total_mant > 0:
                    ch_ln = wb.add_chart({'type': 'column'})
                    ch_ln.add_series({
                        'name': 'Gasto por línea (Mantenimiento)',
                        'categories': ['POR_LINEA_MANT', 1, 0, len(lineas_presentes), 0],
                        'values': ['POR_LINEA_MANT', 1, 1, len(lineas_presentes), 1],
                        'data_labels': {'value': False},
                    })
                    ch_ln.set_title({'name': f'Mantenimiento por línea/pañol — {month:02d}/{year}'})
                    ch_ln.set_legend({'none': True})
                    ch_ln.set_size({'width': 560, 'height': 360})
                    ws_ln.insert_chart('D2', ch_ln)

            # Hoja DIA_x_SECTOR (todas las fechas en orden).
            ws_ds = wb.add_worksheet("DIA_x_SECTOR")
            cab_ds = ["FECHA"] + etiquetas + ["TOTAL_DIA"]
            for cnum, cname in enumerate(cab_ds):
                ws_ds.write(0, cnum, cname, hfmt)
            rnum = 1
            for fd in dias_mes:
                k = self._formato_fecha_escrita(fd)
                tds = totales_dia_sector.get(k, {})
                tot = sum(float(tds.get(c, 0.0)) for c in codes)
                if tot == 0:
                    continue
                ws_ds.write(rnum, 0, k, bfmt)
                for cidx, c in enumerate(codes, start=1):
                    ws_ds.write_number(rnum, cidx, round(float(tds.get(c, 0.0)), 2), money_fmt)
                ws_ds.write_number(rnum, len(codes) + 1, round(tot, 2), money_fmt)
                rnum += 1
            ws_ds.write(rnum, 0, "TOTAL MES", hfmt)
            for cidx, c in enumerate(codes, start=1):
                ws_ds.write_number(rnum, cidx, round(float(total_sector[c]), 2), tot_fmt)
            ws_ds.write_number(rnum, len(codes) + 1, round(float(total_mes), 2), tot_fmt)
            ws_ds.set_column(0, 0, 14, bfmt)
            ws_ds.set_column(1, len(cab_ds) - 1, 16, money_fmt)
            ws_ds.freeze_panes(1, 1)

            # Hoja DIA_x_LINEA_MANT.
            if lineas_presentes:
                ws_dl = wb.add_worksheet("DIA_x_LINEA_MANT")
                cab_dl = ["FECHA"] + lineas_presentes + ["TOTAL_DIA"]
                for cnum, cname in enumerate(cab_dl):
                    ws_dl.write(0, cnum, cname, hfmt)
                rnum = 1
                for fd in dias_mes:
                    k = self._formato_fecha_escrita(fd)
                    dl = dia_linea.get(k, {})
                    tot = sum(dl.values())
                    if tot == 0:
                        continue
                    ws_dl.write(rnum, 0, k, bfmt)
                    for cidx, ln in enumerate(lineas_presentes, start=1):
                        ws_dl.write_number(rnum, cidx, round(float(dl.get(ln, 0.0)), 2), money_fmt)
                    ws_dl.write_number(rnum, len(lineas_presentes) + 1, round(tot, 2), money_fmt)
                    rnum += 1
                ws_dl.write(rnum, 0, "TOTAL MES", hfmt)
                for cidx, ln in enumerate(lineas_presentes, start=1):
                    ws_dl.write_number(rnum, cidx, round(float(gl_map[ln]), 2), tot_fmt)
                ws_dl.write_number(rnum, len(lineas_presentes) + 1, round(float(total_mant), 2), tot_fmt)
                ws_dl.set_column(0, 0, 14, bfmt)
                ws_dl.set_column(1, len(cab_dl) - 1, 14, money_fmt)
                ws_dl.freeze_panes(1, 1)

        return out_path, body_txt, body_html, ""

    def _enviar_mail_gastos_adjunto(self, asunto, cuerpo_txt, cuerpo_html, destino, archivo):
        """Envía gastos con cuerpo multipart (texto plano + HTML) y Excel adjunto."""
        conf = self.correos_df.iloc[0]
        msg = MIMEMultipart()
        msg['From'] = str(conf['remitente'])
        msg['To'] = str(destino)
        msg['Subject'] = asunto
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(cuerpo_txt, 'plain', 'utf-8'))
        alt.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))
        msg.attach(alt)

        with open(archivo, "rb") as adj:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(adj.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(archivo)}")
            msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(str(conf['remitente']).strip(), str(conf['password']).strip())
        server.send_message(msg)
        server.quit()

    def _enviar_mail_con_adjunto(self, asunto, cuerpo, destino, archivo):
        conf = self.correos_df.iloc[0]
        msg = MIMEMultipart()
        msg['From'] = str(conf['remitente'])
        msg['To'] = str(destino)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))

        with open(archivo, "rb") as adj:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(adj.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(archivo)}")
            msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(str(conf['remitente']).strip(), str(conf['password']).strip())
        server.send_message(msg)
        server.quit()

    def _enviar_mail_texto_plano(self, asunto, cuerpo, destino):
        conf = self.correos_df.iloc[0]
        msg = MIMEMultipart()
        msg['From'] = str(conf['remitente'])
        msg['To'] = str(destino)
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(str(conf['remitente']).strip(), str(conf['password']).strip())
        server.send_message(msg)
        server.quit()

    def _enviar_reportes_automaticos_730(self):
        hoy = datetime.today().strftime('%Y-%m-%d')
        try:
            hay_tipo = self._col_correos_tipo() is not None
            destino = self._destinos_str('general')
            destino_activos = self._destinos_str('activos')
            if not hay_tipo:
                prim = self._correo_destinatario_primario()
                destino = destino or prim
                destino_activos = destino_activos or prim
            if not destino and not destino_activos:
                self._log_mail_automatico("SKIP: sin destinatarios en hoja correos.")
                return

            if self._leer_fecha_envio(LAST_MAIL_FILE) != hoy:
                if destino:
                    self._generar_y_enviar_reporte_total(hoy, destino)
                else:
                    self._log_mail_automatico("Reposición: sin destinatarios 'pañol', se omite.")
                    with open(LAST_MAIL_FILE, 'w', encoding='utf-8') as f:
                        f.write(hoy)

            if self._leer_fecha_envio(LAST_MAIL_GASTOS_FILE) != hoy:
                if not destino:
                    self._log_mail_automatico("Gastos: sin destinatarios 'pañol', se omite.")
                    with open(LAST_MAIL_GASTOS_FILE, 'w', encoding='utf-8') as f:
                        f.write(hoy)
                else:
                    archivo_gastos, fecha_ref, cuerpo_txt, cuerpo_html, err = self._generar_reporte_gastos_sector()
                    if archivo_gastos:
                        asunto = f"Reporte Diario de Gasto por Sector ({fecha_ref.strftime('%Y-%m-%d')})"
                        pie = (
                            "\n\nClasificación aplicada: PRODUCCION, PROYECTOS y MANTENIMIENTO "
                            "(según columna OPERARIO: PRODUCCION directo, PROYECTOS para Maccaroni/Valenzuela,"
                            " y resto como MANTENIMIENTO)."
                        )
                        intro_txt = "Adjunto reporte diario por sector.\n\n"
                        intro_html = '<p style="font-size:12px;">Adjunto reporte diario por sector.</p>'
                        self._enviar_mail_gastos_adjunto(
                            asunto,
                            intro_txt + cuerpo_txt + pie,
                            intro_html + cuerpo_html,
                            destino,
                            archivo_gastos,
                        )
                        with open(LAST_MAIL_GASTOS_FILE, 'w', encoding='utf-8') as f:
                            f.write(hoy)
                    else:
                        self._log_mail_automatico(f"Gastos no enviados: {err}")
                        with open(LAST_MAIL_GASTOS_FILE, 'w', encoding='utf-8') as f:
                            f.write(hoy)
            if self._es_hora_objetivo_mensual():
                mark_mensual = os.path.join(BASE_DIR, ".ultimo_mail_gastos_mensual.txt")
                marca = datetime.today().strftime("%Y-%m")
                if self._leer_fecha_envio(mark_mensual) != marca and destino:
                    fecha_ref_m = datetime.today().date().replace(day=1) - timedelta(days=1)
                    archivo_m, txt_m, html_m, err_m = self._generar_reporte_mensual_gastos(fecha_ref_m)
                    if archivo_m:
                        asunto_m = f"Reporte Mensual de Gasto por Sector ({fecha_ref_m.strftime('%Y-%m')})"
                        self._enviar_mail_gastos_adjunto(asunto_m, txt_m, html_m, destino, archivo_m)
                    else:
                        self._log_mail_automatico(f"Mensual no enviado: {err_m}")
                    with open(mark_mensual, 'w', encoding='utf-8') as f:
                        f.write(marca)

            if self._leer_fecha_envio(LAST_MAIL_SEGUIMIENTO_FILE) != hoy and destino_activos:
                try:
                    ok_seg, err_seg = self._enviar_mail_seguimiento_reparacion(destino_activos)
                    if not ok_seg:
                        self._log_mail_automatico(f"Seguimiento reparación: {err_seg}")
                except Exception as ex_seg:
                    self._log_mail_automatico(f"Seguimiento reparación error: {ex_seg}")
                with open(LAST_MAIL_SEGUIMIENTO_FILE, 'w', encoding='utf-8') as f:
                    f.write(hoy)
        except Exception as e:
            self._log_mail_automatico(f"Error envío 07:30: {e}\n{traceback.format_exc()}")
        finally:
            self.envio_auto_en_progreso = False

    def _generar_y_enviar_reporte_total(self, fecha_str, destino_override=None):
        destino = (destino_override or "").strip() or self._correo_destinatario_primario()
        if not destino:
            self._log_mail_automatico("Reposición: sin destinatario, no se envía.")
            return
        try:
            df = self._df_articulos_principal()
            if df is None or df.empty:
                self._enviar_mail_texto_plano(
                    f"Reporte Diario de Reposición ({fecha_str})",
                    "No hay datos en la hoja ARTICULOS (base vacía o no cargada).",
                    destino,
                )
                with open(LAST_MAIL_FILE, 'w', encoding='utf-8') as f:
                    f.write(fecha_str)
                self._log_mail_automatico("Reposición: base vacía, correo texto enviado.")
                return

            col_minimo = self._col_stock_minimo_maestro(df)
            col_actual = self._col_stock_actual_maestro(df)
            if not col_actual or not col_minimo:
                self._enviar_mail_texto_plano(
                    f"Reporte Diario de Reposición ({fecha_str})",
                    (
                        "No se detectaron columnas de stock actual y/o stock mínimo en ARTICULOS.\n"
                        "Revise nombres (ej.: stock, cantidad, stock_minimo, minimo). Detalle en mail_automatico.log."
                    ),
                    destino,
                )
                self._log_mail_automatico(f"Reposición: columnas no detectadas actual={col_actual} min={col_minimo} cols={list(df.columns)}")
                with open(LAST_MAIL_FILE, 'w', encoding='utf-8') as f:
                    f.write(fecha_str)
                return

            col_articulo = next((c for c in df.columns if 'art' in str(c).lower() or 'desc' in str(c).lower() or 'det' in str(c).lower()), None)
            col_imp = self._col_importancia(df)

            df_repo = df[pd.to_numeric(df[col_actual], errors='coerce') <= pd.to_numeric(df[col_minimo], errors='coerce')].copy()
            df_repo['A_REPONER'] = pd.to_numeric(df_repo[col_minimo], errors='coerce') - pd.to_numeric(df_repo[col_actual], errors='coerce')
            df_repo = df_repo[df_repo['A_REPONER'] > 0].copy()

            if df_repo.empty:
                self._enviar_mail_texto_plano(
                    f"Reporte Diario de Reposición ({fecha_str})",
                    "No hay artículos con faltante de reposición (stock por encima del mínimo o sin déficit positivo).",
                    destino,
                )
                with open(LAST_MAIL_FILE, 'w', encoding='utf-8') as f:
                    f.write(fecha_str)
                self._log_mail_automatico("Reposición: lista vacía, correo aviso enviado.")
                return

            if col_imp and col_imp in df_repo.columns:
                df_repo['PRIORIDAD'] = df_repo[col_imp].astype(str).str.upper()
            else:
                df_repo['PRIORIDAD'] = 'BASE'
            df_repo['CATEGORIA'] = df_repo['codigo'].apply(lambda c: self.categoria_map.get(str(c).upper(), 'GENERAL'))

            cols_to_keep = ['codigo', col_articulo, col_actual, col_minimo, 'A_REPONER', 'PRIORIDAD', 'CATEGORIA']
            cols_to_keep = [c for c in cols_to_keep if c is not None]
            df_repo = df_repo[[c for c in cols_to_keep if c in df_repo.columns]]
            ren = ['CODIGO', 'ARTICULO', 'STOCK ACTUAL', 'STOCK MINIMO', 'A REPONER', 'IMPORTANCIA', 'CATEGORIA']
            df_repo.columns = ren[:len(df_repo.columns)]
            df_total = df_repo

            filename = os.path.join(BASE_DIR, f"Reporte_Compras_{fecha_str}.xlsx")
            writer = pd.ExcelWriter(filename, engine='xlsxwriter')

            header_fmt = writer.book.add_format({'bold': True, 'bg_color': '#2C3E50', 'font_color': 'white', 'border': 1, 'align': 'center'})
            base_fmt = writer.book.add_format({'border': 1, 'align': 'center'})
            alert_fmt = writer.book.add_format({'bold': True, 'font_color': '#c0392b', 'border': 1, 'align': 'center'})

            for cat in df_total['CATEGORIA'].unique():
                df_cat = df_total[df_total['CATEGORIA'] == cat].drop(columns=['CATEGORIA'])
                sheet_name = str(cat)[:31]
                df_cat.to_excel(writer, index=False, sheet_name=sheet_name)
                ws = writer.sheets[sheet_name]
                for col_num, value in enumerate(df_cat.columns.values):
                    ws.write(0, col_num, str(value), header_fmt)
                ncols = len(df_cat.columns)
                ws.set_column(0, 0, 15, base_fmt)
                ws.set_column(1, 1, 45, base_fmt)
                if ncols > 2:
                    ws.set_column(2, min(3, ncols - 1), 18, base_fmt)
                if ncols > 4:
                    ws.set_column(4, 4, 18, alert_fmt)
                if ncols > 5:
                    ws.set_column(5, ncols - 1, 18, base_fmt)
                ws.autofilter(0, 0, len(df_cat), ncols - 1)
                ws.freeze_panes(1, 0)
                tot_col = ncols
                ws.write(0, tot_col, "TOTAL ARTÍCULOS:", header_fmt)
                ws.write(1, tot_col, len(df_cat), base_fmt)
                for r in range(len(df_cat)):
                    for c in range(len(df_cat.columns)):
                        if df_cat.columns[c] == 'A REPONER':
                            ws.write(r + 1, c, df_cat.iloc[r, c], alert_fmt)
                        else:
                            ws.write(r + 1, c, df_cat.iloc[r, c], base_fmt)
            writer.close()

            # Tabla de críticos para el cuerpo del mail (visualización rápida).
            filas_crit = []
            if 'IMPORTANCIA' in df_total.columns:
                df_crit = df_total[
                    df_total['IMPORTANCIA'].astype(str).apply(lambda v: 'crit' in self._norm_header_imp(v))
                ].copy()
                if 'A REPONER' in df_crit.columns:
                    df_crit = df_crit.sort_values('A REPONER', ascending=False)
                for _, rc in df_crit.iterrows():
                    filas_crit.append((
                        '#FFC7CE',
                        (
                            self._texto_ui(rc.get('CODIGO')),
                            self._texto_ui(rc.get('ARTICULO')),
                            self._texto_ui(rc.get('STOCK ACTUAL')),
                            self._texto_ui(rc.get('STOCK MINIMO')),
                            self._texto_ui(rc.get('A REPONER')),
                        ),
                    ))

            cuerpo_txt = f"Adjunto reporte consolidado automático. Total de ítems a reponer: {len(df_total)}."
            if filas_crit:
                cuerpo_txt += f"\nArtículos CRÍTICOS a reponer: {len(filas_crit)} (ver detalle en el cuerpo del mail)."
            intro_html = (
                f'<p style="font-family:Arial,sans-serif;font-size:13px;color:#2C3E50;">'
                f'Reporte consolidado automático. Total de ítems a reponer: <b>{len(df_total)}</b>.<br/>'
                f'El detalle completo por categoría está en el Excel adjunto.</p>'
            )
            if filas_crit:
                tabla_crit_html = self._tabla_html_coloreada(
                    f"Artículos CRÍTICOS a reponer ({len(filas_crit)})",
                    ["Código", "Artículo", "Stock actual", "Stock mínimo", "A reponer"],
                    filas_crit,
                    leyenda_dias=False,
                )
            else:
                tabla_crit_html = (
                    '<p style="font-family:Arial,sans-serif;font-size:13px;color:#1e8449;">'
                    'No hay artículos críticos pendientes de reposición.</p>'
                )
            cuerpo_html = intro_html + tabla_crit_html

            conf = self.correos_df.iloc[0]
            msg = MIMEMultipart()
            msg['From'] = str(conf['remitente'])
            msg['To'] = destino
            msg['Subject'] = f"Reporte Diario de Reposición ({fecha_str})"
            alt = MIMEMultipart('alternative')
            alt.attach(MIMEText(cuerpo_txt, 'plain', 'utf-8'))
            alt.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))
            msg.attach(alt)

            with open(filename, "rb") as adj:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(adj.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(filename)}")
                msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(str(conf['remitente']).strip(), str(conf['password']).strip())
            server.send_message(msg)
            server.quit()

            with open(LAST_MAIL_FILE, 'w', encoding='utf-8') as f:
                f.write(fecha_str)
            self._log_mail_automatico(f"Reposición OK: {len(df_total)} ítems, adjunto {filename}")
        except Exception as e:
            self._log_mail_automatico(f"Error reporte reposición: {e}\n{traceback.format_exc()}")

    def enviar_mail_manual(self, cat_or_base):
        if self.correos_df.empty: return messagebox.showwarning("Aviso", "No hay configuraciones de correo.")
        archivo = self.exportar_reposicion(cat_or_base, abrir_al_terminar=False)
        if not archivo: return 
        dest = simpledialog.askstring("Mail", f"Correo destino para '{cat_or_base}':", parent=self.root)
        if not dest: return 
        
        def enviar():
            try:
                conf = self.correos_df.iloc[0]; msg = MIMEMultipart(); msg['From'] = str(conf['remitente']); msg['To'] = dest; msg['Subject'] = f"Lista: {cat_or_base.upper()}"
                msg.attach(MIMEText(f"Se adjunta lista solicitada.", 'plain'))
                with open(archivo, "rb") as adj: part = MIMEBase("application", "octet-stream"); part.set_payload(adj.read()); encoders.encode_base64(part); part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(archivo)}"); msg.attach(part)
                server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(str(conf['remitente']).strip(), str(conf['password']).strip()); server.send_message(msg); server.quit()
                self.root.after(0, lambda: messagebox.showinfo("Éxito", "Enviado."))
            except Exception as e: self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        threading.Thread(target=enviar).start()

    def guardar_sistemas_simple(self):
        with self.save_lock:
            try:
                with pd.ExcelWriter(self.master_file_path, engine='xlsxwriter') as writer:
                    for s, df in self.master_dict.items():
                        df_save = df
                        if s == HOJA_ARTICULOS:
                            df_save = self._limpiar_columnas_precio_duplicadas_df(df)
                            col_imp = self._col_importancia(df_save)
                            if col_imp:
                                df_save[col_imp] = df_save[col_imp].apply(self._normalizar_criticidad_maestro)
                        self._apply_uppercase_to_df(df_save).to_excel(writer, index=False, sheet_name=s)
                    if not self.config_df.empty:
                        self.config_df.to_excel(writer, index=False, sheet_name='config')
                    if not self.correos_df.empty:
                        self.correos_df.to_excel(writer, index=False, sheet_name='correos')
            except Exception as e:
                print(f"Error guardando maestro: {e}")

    def guardar_archivos_background(self, nueva_fila, fecha_dt):
        with self.save_lock: 
            try:
                # Actualiza master primero
                self.guardar_sistemas_simple()
                
                # Guarda la salida en master_salidas y el archivo diario de forma SEGURA (sin xlsxwriter)
                archivo_diario = os.path.join(BASE_DIR, f"salidas_{fecha_dt.strftime('%d-%m-%Y')}.xlsx")
                for p in [HISTORIAL_PATH, archivo_diario]:
                    if os.path.exists(p):
                        df_p = pd.read_excel(p)
                    else:
                        df_p = pd.DataFrame()
                    if 'FECHA' in df_p.columns:
                        df_p['FECHA'] = df_p['FECHA'].apply(self._fecha_sin_hora_str)
                        
                    df_p = pd.concat([df_p, pd.DataFrame([nueva_fila])], ignore_index=True)
                    if 'FECHA' in df_p.columns:
                        df_p['FECHA'] = df_p['FECHA'].apply(self._fecha_sin_hora_str)
                    self._escribir_excel_formateado(p, df_p, sheet_name="Movimientos", highlight_col="CANTIDAD")
            except Exception as e: 
                print(f"Error guardando historial: {e}")

    def procesar_movimiento(self, es_devolucion=False):
        try:
            cod = self.codigo_var.get().strip().upper()
            try:
                cant_input = float(self.cant_var.get().replace(',', '.'))
                cant = -abs(cant_input) if es_devolucion else abs(cant_input)
            except: return messagebox.showerror("Error", "Cantidad inválida")
            
            sector, operario_final = self.obtener_sector_operario()
            if not sector:
                return messagebox.showwarning("Faltan datos", "Complete Orden, Comprobante y selección de Sector/Operario.")
            if not (self.cmb_tipo.get() and self.orden_var.get()):
                return messagebox.showwarning("Faltan datos", "Complete Orden y Comprobante.")
            
            stock_proyectado = self._stock_proyectado_codigo(cod)
            if stock_proyectado is None:
                return messagebox.showerror("Error", "No se encontró el código en el Master.")
            nuevo_stock = stock_proyectado - cant
            if nuevo_stock < 0 and not es_devolucion:
                if not messagebox.askyesno("Atención", f"Stock proyectado quedaría en negativo ({nuevo_stock:.2f}). ¿Desea continuar?"):
                    return
            
            fecha_dt = self.date_entry.get_date()
            precio = self._parse_precio_ui_a_float(self.precio_var.get())
            orden_val = self._normalizar_orden_para_excel(self.orden_var.get())
            monto_linea = round(abs(cant) * precio, 2)
            nueva_fila = {
                "FECHA": self._fecha_sin_hora_str(fecha_dt),
                "MES": self._nombre_mes_escrito(fecha_dt.month),
                "AÑO": int(fecha_dt.year),
                "CODIGO": cod,
                "DESCRIPCION": ("(DEVOLUCIÓN) " if es_devolucion else "") + self.desc_var.get(),
                "UBICACION": self.stk_ubic_var.get(),
                "CANTIDAD": cant,
                "TIPO_COMPROBANTE": self.cmb_tipo.get(),
                "NUMERO_ORDEN": orden_val if orden_val is not None else "",
                "MAQUINA_SITIO": self.maquina_var.get(),
                "PRECIO_UNITARIO": precio,
                "MONTO_TOTAL_SALIDA": monto_linea if not es_devolucion else -monto_linea,
                "OPERARIO": operario_final,
                "SECTOR": sector,
            }
            for k in list(nueva_fila.keys()):
                if k in ("MES", "AÑO", "NUMERO_ORDEN", "PRECIO_UNITARIO", "MONTO_TOTAL_SALIDA", "CANTIDAD"):
                    continue
                if isinstance(nueva_fila[k], str):
                    nueva_fila[k] = nueva_fila[k].upper()
            iid = self.tree_orden.insert("", "end", values=(
                cod,
                nueva_fila["DESCRIPCION"],
                cant,
                self._formato_precio_unit_ui(precio),
                self._formato_pesos_ar(monto_linea),
            ))
            self._montos_carga_orden[iid] = monto_linea
            self._salidas_pendientes[iid] = {"fila": nueva_fila, "fecha_dt": fecha_dt}
            self._actualizar_total_carga_orden()
            self.actualizar_contadores_reposicion()

            self.limpiar_parcial()
            self._set_formulario_misma_orden_bloqueado(True)
            self.ent_codigo.focus_set()
        except Exception as e: messagebox.showerror("Error", f"Fallo al registrar: {e}")

    def _payload_articulo_firebase(self, item):
        return {
            'codigo': item['c'],
            'desc': item['d'],
            'stock': item['s'],
            'ubicacion': item['u'],
            'categoria': self.categoria_map.get(item['c'], 'GENERAL'),
        }

    def _snapshot_articulos_firebase(self):
        """Lee el estado actual en la nube (solo al pulsar sincronizar)."""
        snap = {}
        for doc in db.collection('articulos').stream():
            d = doc.to_dict() or {}
            snap[doc.id] = {
                'codigo': str(d.get('codigo', doc.id)),
                'desc': str(d.get('desc', '')),
                'stock': str(d.get('stock', '')),
                'ubicacion': str(d.get('ubicacion', '')),
                'categoria': str(d.get('categoria', 'GENERAL')),
            }
        return snap

    def _bump_catalogo_version_firebase(self):
        import time
        ref = db.collection('config').document('catalogo')
        ref.set({'version': int(time.time()), 'updatedAt': firestore.SERVER_TIMESTAMP}, merge=True)

    def sincronizar_item_a_firebase(self, codigo, nuevo_stock, desc, ubicacion, categoria):
        if not firebase_conectado: return
        try:
            db.collection('articulos').document(codigo).set(
                {'codigo': codigo, 'stock': nuevo_stock, 'desc': desc, 'ubicacion': ubicacion, 'categoria': categoria},
                merge=True,
            )
            self._bump_catalogo_version_firebase()
        except Exception as e:
            print(f"Error Firebase: {e}")

    def sincronizar_todo_a_firebase(self):
        if not firebase_conectado: return messagebox.showerror("Error", "No hay conexión a Firebase.")
        if not self.search_cache: self.preparar_cache_buscador()
        if not messagebox.askyesno(
            "Migración",
            "¿Sincronizar solo los artículos que cambiaron respecto a la nube?\n"
            "(Evita reescribir miles de documentos iguales.)",
        ):
            return

        def tarea():
            try:
                self.root.after(0, lambda: self.lbl_status.config(text="⏳ Comparando con la nube...", foreground="orange"))
                remoto = self._snapshot_articulos_firebase()
                escritos = 0
                omitidos = 0
                for item in self.search_cache:
                    payload = self._payload_articulo_firebase(item)
                    prev = remoto.get(item['c'])
                    if prev == payload:
                        omitidos += 1
                        continue
                    db.collection('articulos').document(item['c']).set(payload, merge=True)
                    escritos += 1
                if escritos > 0:
                    self._bump_catalogo_version_firebase()
                msg = f"Nube OK — {escritos} actualizados, {omitidos} sin cambios"
                self.root.after(0, lambda: self.lbl_status.config(text=msg, foreground="green"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def abrir_editor(self):
        if not self.master_dict:
            return messagebox.showwarning("Aviso", "Primero cargue la base de datos.")
        top = tk.Toplevel(self.root)
        top.title("Editar artículo")
        top.geometry("520x360")
        top.grab_set()
        frm = ttk.Frame(top, padding=20)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        self._label_con_asterisco_obligatorio(frm, "Código:", 0)
        c_ed = tk.StringVar()
        ent = ttk.Entry(frm, textvariable=c_ed)
        ent.grid(row=0, column=1, sticky="ew")
        ent.focus_set()
        d_ed = tk.StringVar(value="-")
        ttk.Label(frm, textvariable=d_ed, font=("Arial", 9, "italic")).grid(row=1, column=0, columnspan=2, sticky="w")
        self.create_label(frm, "Ubicación:", 2)
        u_ed = tk.StringVar()
        ttk.Entry(frm, textvariable=u_ed).grid(row=2, column=1, sticky="ew")
        self.create_label(frm, "Mínimo de stock:", 3)
        m_ed = tk.StringVar()
        ttk.Entry(frm, textvariable=m_ed).grid(row=3, column=1, sticky="ew")
        self.create_label(frm, "Criticidad:", 4)
        imp_ed = tk.StringVar(value="BASE")
        cmb_imp = ttk.Combobox(frm, textvariable=imp_ed, values=CRITICIDAD_OPCIONES_MAESTRO, state="readonly")
        cmb_imp.grid(row=4, column=1, sticky="ew")
        self._configurar_combobox_predictivo(cmb_imp, list(CRITICIDAD_OPCIONES_MAESTRO), valores_mayusculas=False)

        loc = {'s_m': None, 'i_m': None, 'c_u': None, 'c_m': None, 'c_imp': None}

        def buscar():
            cod = c_ed.get().strip().upper()
            loc['s_m'] = None
            for s, df in self.master_dict.items():
                if 'codigo' not in df.columns:
                    continue
                match = df[df['codigo'] == cod]
                if match.empty:
                    continue
                idx = match.index[0]
                loc['s_m'] = s
                loc['i_m'] = idx
                loc['c_u'] = next((c for c in df.columns if self._es_columna_ubicacion(c)), 'ubicacion')
                desc_col = next((c for c in ['descripcion', 'articulo'] if c in df.columns), 'descripcion')
                d_ed.set(str(df.at[idx, desc_col]).upper() if desc_col in df.columns else "")
                u_ed.set(str(df.at[idx, loc['c_u']]) if pd.notna(df.at[idx, loc['c_u']]) else "")
                col_m = next((c for c in df.columns if 'min' in self._norm_header_imp(str(c))), None)
                loc['c_m'] = col_m
                if col_m:
                    m_ed.set(str(df.at[idx, col_m]) if pd.notna(df.at[idx, col_m]) else "0")
                else:
                    m_ed.set("0")
                col_imp = self._col_importancia(df)
                loc['c_imp'] = col_imp
                if col_imp and col_imp in df.columns:
                    imp_ed.set(self._normalizar_criticidad_maestro(df.at[idx, col_imp]))
                else:
                    imp_ed.set('BASE')
                break

        def guardar():
            if not loc['s_m']:
                return
            df = self.master_dict[loc['s_m']]
            idx = loc['i_m']
            df.at[idx, loc['c_u']] = u_ed.get().upper()
            if loc['c_m']:
                try:
                    self._set_cell_numeric_safe(df, idx, loc['c_m'], float(str(m_ed.get()).replace(',', '.')))
                except ValueError:
                    messagebox.showerror("Error", "Mínimo inválido.")
                    return
            col_imp = loc['c_imp']
            if not col_imp or col_imp not in df.columns:
                if 'importancia' not in df.columns:
                    df['importancia'] = 'base'
                col_imp = 'importancia'
                loc['c_imp'] = col_imp
            df.at[idx, col_imp] = self._normalizar_criticidad_maestro(imp_ed.get())
            threading.Thread(target=self.guardar_sistemas_simple, daemon=True).start()
            messagebox.showinfo("Éxito", "Guardado.")
            top.destroy()

        tk.Button(frm, text="BUSCAR", bg="#95a5a6", fg="white", command=buscar).grid(row=0, column=2, padx=4)
        tk.Button(frm, text="GUARDAR", bg="#3498db", fg="white", command=guardar).grid(row=5, column=0, columnspan=3, sticky="ew", pady=20)
        ent.bind('<Return>', lambda e: buscar())

    def preparar_cache_buscador(self):
        self.search_cache = []
        for s, df in self.master_dict.items():
            if 'codigo' not in df.columns: continue
            c_d = next((c for c in df.columns if 'desc' in c or 'art' in c), 'DESCRIPCION')
            c_s = next((c for c in df.columns if 'stock' in c or 'act' in c), 'STOCK')
            c_u = next((c for c in df.columns if self._es_columna_ubicacion(c)), 'UBICACION')
            for _, row in df.iterrows():
                c = str(row.get('codigo', '')).upper(); d = str(row.get(c_d, '')).upper()
                st = pd.to_numeric(row.get(c_s, 0), errors='coerce'); u = str(row.get(c_u, 'N/A')).upper()
                self.search_cache.append({'c': c, 'd': d, 's': st, 'u': u, 'txt': f"{c} {d}"})

    def abrir_buscador(self, event=None, callback=None):
        if not self.master_dict: return messagebox.showwarning("Aviso", "Cargue Maestro.")
        self.preparar_cache_buscador()

        if getattr(self, "_buscador_top", None) is not None:
            try:
                if self._buscador_top.winfo_exists():
                    self._buscador_top.deiconify()
                    self._buscador_top.lift()
                    self._buscador_top.focus_force()
                    return
            except tk.TclError:
                pass

        top = tk.Toplevel(self.root)
        self._buscador_top = top
        top.title("Buscador Avanzado Inteligente")
        top.geometry("850x450")
        top.transient(self.root)

        def _cerrar_buscador():
            self._buscador_top = None
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", _cerrar_buscador)

        def _al_restaurar_principal(_evt=None):
            if top.winfo_exists():
                try:
                    top.deiconify()
                    top.lift()
                    top.attributes("-topmost", True)
                    top.after(80, lambda: top.attributes("-topmost", False) if top.winfo_exists() else None)
                    top.focus_force()
                except tk.TclError:
                    pass

        self.root.bind("<Map>", _al_restaurar_principal, add="+")
        top.bind("<Destroy>", lambda e: self.root.unbind("<Map>"), add="+")
        
        ttk.Label(top, text="Escriba palabras sueltas, código o marca (ej: 'buje goma 25'):", font=("Arial", 11, "bold")).pack(pady=10)
        sv = tk.StringVar()
        ent = ttk.Entry(top, textvariable=sv, font=("Arial", 14))
        ent.pack(fill="x", padx=20)
        ent.focus_set()
        
        tree = ttk.Treeview(top, columns=("C", "D", "S", "U"), show="headings", height=15)
        tree.pack(fill="both", expand=True, padx=20, pady=10)
        for c, h in [("C", "Código"), ("D", "Descripción"), ("S", "Stock"), ("U", "Ubicación")]: 
            tree.heading(c, text=h)
        
        def filtrar(e=None):
            q = sv.get().upper().strip()
            tree.delete(*tree.get_children())
            
            palabras_buscadas = q.split() 
            
            for i in self.search_cache:
                if all(p in i['txt'] for p in palabras_buscadas):
                    tree.insert("", "end", values=(i['c'], i['d'], i['s'], i['u']))
                    
        sv.trace_add("write", lambda *a: filtrar())
        
        def seleccionar(e=None):
            sel = tree.selection()
            if sel:
                val = tree.item(sel[0])['values'][0]
                _cerrar_buscador()
                if callback:
                    callback(val)
                else:
                    self.codigo_var.set(val)
                    self.procesar_codigo_y_avanzar()

        tree.bind("<Double-1>", seleccionar)
        tree.bind("<Return>", seleccionar)

    def exportar_reposicion(self, cat, abrir_al_terminar=True):
        target, df_repo = self._obtener_reposicion_df(cat)
        if not target or df_repo is None or df_repo.empty:
            self.actualizar_contadores_reposicion()
            return None
        if df_repo.empty: return None
        slug = str(cat).strip().lower().replace(' ', '_')
        filename = os.path.join(BASE_DIR, f"reposicion_{slug}.xlsx")
        self._escribir_excel_formateado(filename, df_repo, sheet_name="Reposicion", highlight_col="A_REPONER", mostrar_total=True)
        self.actualizar_contadores_reposicion()
        if abrir_al_terminar: os.startfile(filename)
        return filename

    def generar_diario_manual(self):
        f = os.path.join(BASE_DIR, f"salidas_{self.date_entry.get_date().strftime('%d-%m-%Y')}.xlsx")
        if os.path.exists(f): os.startfile(f)

    def limpiar_parcial(self):
        self.codigo_var.set(""); self.desc_var.set(""); self.precio_var.set(""); self.cant_var.set(""); self.stk_ubic_var.set("-"); self.stk_actual_var.set("-"); self.stk_min_var.set("-"); self.ent_codigo.focus_set()

    def limpiar_total(self):
        self.limpiar_parcial()
        self.orden_var.set("")
        self.maquina_var.set("")
        self.cmb_tipo.set("")
        self.cmb_ope.set("")
        self.cmb_ope_det.set("")
        self.tree_orden.delete(*self.tree_orden.get_children())
        self._montos_carga_orden = {}
        self._salidas_pendientes = {}
        self._actualizar_total_carga_orden()
        self._configurar_combobox_predictivo(self.cmb_tipo, self.tipos_comprobante)
        self._configurar_combobox_predictivo(self.cmb_ope, self.sectores_operario)
        self.cmb_ope_det['values'] = []
        if hasattr(self.cmb_ope_det, '_all_values'):
            self.cmb_ope_det._all_values = []
        self.cmb_ope_det.configure(state="disabled")
        self._set_formulario_misma_orden_bloqueado(False)

if __name__ == "__main__":
    try:
        if "--enviar-730" in sys.argv:
            root = tk.Tk()
            root.withdraw()
            app = AlmacenApp(root)
            app._enviar_reportes_automaticos_730()
            root.destroy()
            sys.exit(0)

        root = tk.Tk()
        app = AlmacenApp(root)
        root.mainloop()
    except Exception as e:
        print(f"\n❌ ERROR CRITICO AL INICIAR: {e}\n")
        traceback.print_exc()
        # En ejecutables windowed puede no existir stdin.
        if sys.stdin and sys.stdin.isatty():
            input("Presiona Enter para salir...")