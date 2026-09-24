# -*- coding: utf-8 -*-
"""Tests for Slice 2 — Tecnicos-Cards + Historial + KPIs (kpis-cajas spec).

Ejecución: python -m unittest -v tests.test_cajas_tecnicos_kpis
Requiere: MariaDB accesible, módulo cajas inicializado.

Cubre:
- tecnicos-cards pagination limit/offset, q filter
- no ideal -> faltantes null/hint
- with ideal 2 herramientas, tecnico with inventario presente 1/2 -> 50% faltantes
- with ideal vs empty inventario -> 100% faltantes
- with ideal vs full presente -> 0% faltantes
- historial per tecnico ordered DESC, pagination
- historial 401 unauthorized
- kpis resumen global avg
- kpis por tecnico 404 when tecnico not found
- limpieza_score derived from estado malo count
- test invalid limit clamp
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CAJAS_DB_HOST", "127.0.0.1")
os.environ.setdefault("CAJAS_DB_PORT", "3306")
os.environ.setdefault("CAJAS_DB_USER", "root")
os.environ.setdefault("CAJAS_DB_PASSWORD", "")
os.environ.setdefault("CAJAS_DB_NAME", "panol")
os.environ.setdefault("CAJAS_JWT_SECRET", "panol-secret-key-2024")

import db
import service
import store
from jose import jwt as jose_jwt

db.init_db()

JWT_SECRET = os.environ.get("CAJAS_JWT_SECRET", "panol-secret-key-2024")


def _token():
    payload = {"sub": "test", "rol": "panol", "permisos": ["cajas:lectura", "cajas:escritura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _token_lectura():
    payload = {"sub": "test", "rol": "supervisor", "permisos": ["cajas:lectura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _ensure_herramienta(codigo: str, categoria: str = "HERRAMIENTA"):
    result = service.create_herramienta(_token(), {"codigo": codigo, "categoria": categoria})
    if isinstance(result, dict):
        return result
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo FROM cajas_herramientas WHERE codigo = %s", (codigo,))
            row = cur.fetchone()
            if row:
                return row
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass
    raise RuntimeError(f"No se pudo asegurar herramienta {codigo}: {result}")


def _get_personal_tecnico():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, tipo FROM personal WHERE tipo IN ('tecnico','supervisor','generico','panol') AND activo=1 ORDER BY id ASC")
            rows = cur.fetchall()
            return rows
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def _get_caja_id():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cajas_cajas LIMIT 1")
            row = cur.fetchone()
            if row:
                return row["id"]
            # create one
            cur.execute("SELECT id FROM personal WHERE tipo IN ('tecnico','supervisor') LIMIT 1")
            # create caja via service
            result = service.create_caja(_token(), {"codigo": "KPISCAJA001", "descripcion": "Caja KPIs test", "ubicacion": "Panol"})
            if isinstance(result, dict):
                return result["id"]
            cur.execute("SELECT id FROM cajas_cajas WHERE codigo='KPISCAJA001'")
            r2 = cur.fetchone()
            return r2["id"] if r2 else 1
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def _clean_kpis_state():
    """Limpia inventarios e ideal pero mantiene personal y herramientas (excepto KPIs)."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cajas_inventario_detalle")
            cur.execute("DELETE FROM cajas_inventarios")
            cur.execute("DELETE FROM cajas_caja_ideal_detalle")
            cur.execute("DELETE FROM cajas_caja_ideal")
        conn.commit()
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def _create_inventario_via_service(tecnico_id: int, periodo: str, caja_id: int, supervisor_id: int, detalle: list):
    data = {
        "caja_id": caja_id,
        "tecnico_id": tecnico_id,
        "supervisor_id": supervisor_id,
        "periodo": periodo,
        "estado": "borrador",
        "detalle": detalle,
    }
    return service.create_inventario(_token(), data)


def _set_detalle_estado_malo(inventario_id: int, herramienta_codigo: str):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cajas_herramientas WHERE codigo=%s", (herramienta_codigo,))
            hr = cur.fetchone()
            if hr:
                cur.execute("UPDATE cajas_inventario_detalle SET estado='malo' WHERE inventario_id=%s AND herramienta_id=%s", (inventario_id, hr["id"]))
                conn.commit()
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


class TestTecnicosKpis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Limpieza inicial general
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'KPISCAJA%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'KPISCAJA%')")
                cur.execute("DELETE FROM cajas_inventario_detalle")
                cur.execute("DELETE FROM cajas_inventarios")
                cur.execute("DELETE FROM cajas_caja_ideal_detalle")
                cur.execute("DELETE FROM cajas_caja_ideal")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'KPISTOOL%'")
                cur.execute("DELETE FROM cajas_cajas WHERE codigo LIKE 'KPISCAJA%'")
            conn.commit()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        # Asegurar herramientas
        for code in ("KPISTOOL001", "KPISTOOL002", "KPISTOOL003"):
            try:
                _ensure_herramienta(code)
            except Exception:
                pass
        # Asegurar caja
        result = service.create_caja(_token(), {"codigo": "KPISCAJA001", "descripcion": "Caja KPIs", "ubicacion": "Deposito KPIs"})
        if isinstance(result, tuple):
            # ya existe, obtener id
            pass
        cls.personal = _get_personal_tecnico()
        # Buscar ids especificos
        cls.tecnico_id = next((p["id"] for p in cls.personal if p["tipo"] == "tecnico"), cls.personal[0]["id"] if cls.personal else 38)
        cls.supervisor_id = next((p["id"] for p in cls.personal if p["tipo"] == "supervisor"), cls.personal[1]["id"] if len(cls.personal) > 1 else cls.tecnico_id)
        # Obtener caja id
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM cajas_cajas WHERE codigo='KPISCAJA001'")
                r = cur.fetchone()
                cls.caja_id = r["id"] if r else 1
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass

    @classmethod
    def tearDownClass(cls):
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'KPISCAJA%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'KPISCAJA%')")
                cur.execute("DELETE FROM cajas_inventario_detalle")
                cur.execute("DELETE FROM cajas_inventarios")
                cur.execute("DELETE FROM cajas_caja_ideal_detalle")
                cur.execute("DELETE FROM cajas_caja_ideal")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'KPISTOOL%'")
                cur.execute("DELETE FROM cajas_cajas WHERE codigo LIKE 'KPISCAJA%'")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass

    def setUp(self):
        # Asegurar herramientas existen antes de cada test
        for code in ("KPISTOOL001", "KPISTOOL002", "KPISTOOL003"):
            try:
                _ensure_herramienta(code)
            except Exception:
                pass

    def test_01_tecnicos_cards_pagination_limit_offset(self):
        """Paginación limit/offset en tecnicos-cards."""
        _clean_kpis_state()
        # Restaurar ideal minimal para que no sea 0? Pero para pagination no importa.
        # Sin limpiar personal, total debe ser >=2
        result = service.get_tecnicos_cards(_token_lectura(), {"limit": 2, "offset": 0})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)
        self.assertIn("total", result)
        self.assertGreaterEqual(result["total"], 2)
        self.assertLessEqual(len(result["items"]), 2)
        # Segunda página
        result2 = service.get_tecnicos_cards(_token_lectura(), {"limit": 2, "offset": 2})
        self.assertIsInstance(result2, dict)
        self.assertEqual(len(result2["items"]), min(2, result["total"] - 2) if result["total"] > 2 else 0)
        # Verificar campos requeridos
        for item in result["items"]:
            self.assertIn("tecnico_id", item)
            self.assertIn("tecnico_nombre", item)
            self.assertIn("tecnico_tipo", item)
            self.assertIn("ideal_count", item)
            self.assertIn("faltantes_pct", item)
            self.assertIn("completitud_pct", item)
            self.assertIn("limpieza_score", item)

    def test_02_tecnicos_cards_q_filter(self):
        """Filtro q por nombre debe retornar solo coincidencias."""
        _clean_kpis_state()
        # Buscar un nombre conocido, ej: MANTTO (generico)
        result = service.get_tecnicos_cards(_token_lectura(), {"q": "MANTTO"})
        self.assertIsInstance(result, dict)
        # Debe encontrar al menos 1 (MANTTO.)
        self.assertGreaterEqual(result["total"], 1)
        for item in result["items"]:
            # nombre debe contener mantto case-insensitive o legajo
            self.assertIn("MANTTO", item["tecnico_nombre"].upper())
        # Buscar query inexistente -> 0
        result2 = service.get_tecnicos_cards(_token_lectura(), {"q": "ZZZNOEXISTE123"})
        self.assertEqual(result2["total"], 0)
        self.assertEqual(len(result2["items"]), 0)

    def test_03_no_ideal_faltantes_null_hint(self):
        """Sin ideal activo -> faltantes null y mensaje/hint."""
        _clean_kpis_state()
        # Asegurar no hay ideal
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_caja_ideal_detalle")
                cur.execute("DELETE FROM cajas_caja_ideal")
            conn.commit()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        result = service.get_tecnicos_cards(_token_lectura(), {"limit": 5})
        self.assertIsInstance(result, dict)
        # ideal_count debe ser 0, faltantes_pct null
        for item in result["items"]:
            self.assertEqual(item["ideal_count"], 0)
            self.assertIsNone(item["faltantes_pct"])
            self.assertEqual(item["completitud_pct"], 0)
        # KPIs resumen debe retornar hint
        kpis = service.get_kpis_resumen(_token_lectura(), {})
        self.assertIsInstance(kpis, dict)
        self.assertEqual(kpis.get("ideal_count"), 0)
        self.assertIn("No hay Caja Ideal", kpis.get("mensaje") or kpis.get("hint") or "")
        # KPIs por tecnico también hint
        kpi_single = service.get_kpis_por_tecnico(_token_lectura(), self.tecnico_id)
        self.assertIsInstance(kpi_single, dict)
        self.assertEqual(kpi_single.get("ideal_count"), 0)
        self.assertIn("No hay Caja Ideal", kpi_single.get("mensaje") or kpi_single.get("hint") or "")

    def test_04_with_ideal_50_percent(self):
        """Ideal 2 herramientas, inventario con 1 presente -> 50% faltantes."""
        _clean_kpis_state()
        # Crear ideal con 2 herramientas
        created = service.put_ideal(_token(), {
            "nombre": "Ideal 50%",
            "detalle": [
                {"herramienta_codigo": "KPISTOOL001", "cantidad_minima": 1},
                {"herramienta_codigo": "KPISTOOL002", "cantidad_minima": 1},
            ]
        })
        self.assertIsInstance(created, dict)
        # Crear inventario para tecnico con 1 presente, 1 faltante (solo 1 detalle presente)
        # Para simular 1/2 presente, creamos detalle con solo 1 herramienta presente=True
        # Pero necesitamos contar presente_count vs ideal_count: presente 1 de 2 => 50%
        # Creamos inventario con detalle de solo KPISTOOL001 presente True
        res = _create_inventario_via_service(self.tecnico_id, "2026-09-01", self.caja_id, self.supervisor_id, [
            {"herramienta_codigo": "KPISTOOL001", "cantidad": 1, "presente": True},
        ])
        self.assertIsInstance(res, dict, msg=f"inventario creación falló {res}")
        inv_id = res["id"]
        # Verificar tecnicos-cards
        cards = service.get_tecnicos_cards(_token_lectura(), {"limit": 25})
        self.assertIsInstance(cards, dict)
        target = next((c for c in cards["items"] if c["tecnico_id"] == self.tecnico_id), None)
        self.assertIsNotNone(target, msg="tecnico no encontrado en cards")
        self.assertEqual(target["ideal_count"], 2)
        self.assertEqual(target["presente_count"], 1)
        self.assertAlmostEqual(target["faltantes_pct"], 50.0, places=1)
        self.assertAlmostEqual(target["completitud_pct"], 50.0, places=1)
        # KPIs por tecnico también 50%
        kpi = service.get_kpis_por_tecnico(_token_lectura(), self.tecnico_id)
        self.assertAlmostEqual(kpi["faltantes_pct"], 50.0, places=1)
        self.assertAlmostEqual(kpi["completitud_pct"], 50.0, places=1)

    def test_05_with_ideal_empty_100_percent(self):
        """Ideal existe, tecnico sin inventario -> 100% faltantes."""
        _clean_kpis_state()
        # Crear ideal 2 herramientas
        service.put_ideal(_token(), {
            "nombre": "Ideal Empty 100",
            "detalle": [
                {"herramienta_codigo": "KPISTOOL001", "cantidad_minima": 1},
                {"herramienta_codigo": "KPISTOOL002", "cantidad_minima": 1},
            ]
        })
        # No crear inventario para tecnico (limpio)
        # Asegurar que no hay inventario para tecnico
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_inventario_detalle WHERE inventario_id IN (SELECT id FROM cajas_inventarios WHERE tecnico_id=%s)", (self.tecnico_id,))
                cur.execute("DELETE FROM cajas_inventarios WHERE tecnico_id=%s", (self.tecnico_id,))
            conn.commit()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        cards = service.get_tecnicos_cards(_token_lectura(), {"limit": 50})
        target = next((c for c in cards["items"] if c["tecnico_id"] == self.tecnico_id), None)
        self.assertIsNotNone(target)
        self.assertEqual(target["ideal_count"], 2)
        self.assertEqual(target["presente_count"], 0)
        self.assertAlmostEqual(target["faltantes_pct"], 100.0, places=1)
        self.assertAlmostEqual(target["completitud_pct"], 0.0, places=1)
        # KPIs resumen debe contar este tecnico como 100% faltantes
        kpis = service.get_kpis_resumen(_token_lectura(), {})
        self.assertGreater(kpis["avg_faltantes_pct"], 0)

    def test_06_with_ideal_full_0_percent(self):
        """Ideal 2 herramientas, inventario full presente -> 0% faltantes."""
        _clean_kpis_state()
        service.put_ideal(_token(), {
            "nombre": "Ideal Full 0%",
            "detalle": [
                {"herramienta_codigo": "KPISTOOL001", "cantidad_minima": 1},
                {"herramienta_codigo": "KPISTOOL002", "cantidad_minima": 1},
            ]
        })
        # Crear inventario con ambas herramientas presente True
        res = _create_inventario_via_service(self.tecnico_id, "2026-09-01", self.caja_id, self.supervisor_id, [
            {"herramienta_codigo": "KPISTOOL001", "cantidad": 1, "presente": True},
            {"herramienta_codigo": "KPISTOOL002", "cantidad": 1, "presente": True},
        ])
        self.assertIsInstance(res, dict)
        cards = service.get_tecnicos_cards(_token_lectura(), {"limit": 50})
        target = next((c for c in cards["items"] if c["tecnico_id"] == self.tecnico_id), None)
        self.assertAlmostEqual(target["faltantes_pct"], 0.0, places=1)
        self.assertAlmostEqual(target["completitud_pct"], 100.0, places=1)
        kpi = service.get_kpis_por_tecnico(_token_lectura(), self.tecnico_id)
        self.assertAlmostEqual(kpi["faltantes_pct"], 0.0, places=1)
        self.assertAlmostEqual(kpi["completitud_pct"], 100.0, places=1)

    def test_07_historial_per_tecnico_ordered_desc_pagination(self):
        """Historial ordenado periodo DESC con paginación."""
        _clean_kpis_state()
        # Crear 3 inventarios para tecnico en diferentes periodos
        for periodo in ("2026-01-01", "2026-02-01", "2026-03-01"):
            # limpiar previamente por periodo unico por caja -> need different caja or same periodo? UNIQUE caja_id+periodo, so same caja different periodo is ok
            _create_inventario_via_service(self.tecnico_id, periodo, self.caja_id, self.supervisor_id, [
                {"herramienta_codigo": "KPISTOOL001", "cantidad": 1, "presente": True},
            ])
        # Obtener historial sin paginar
        hist = service.get_inventarios_por_tecnico(_token_lectura(), self.tecnico_id, {"limit": 10, "offset": 0})
        self.assertIsInstance(hist, dict)
        self.assertIn("items", hist)
        self.assertIn("total", hist)
        self.assertGreaterEqual(hist["total"], 3)
        # Orden DESC: primer item debe ser 2026-03-01
        self.assertEqual(hist["items"][0]["periodo"], "2026-03-01")
        self.assertEqual(hist["items"][1]["periodo"], "2026-02-01")
        self.assertEqual(hist["items"][2]["periodo"], "2026-01-01")
        # Verificar que detalle viene con herramienta_codigo
        self.assertIn("detalle", hist["items"][0])
        self.assertEqual(hist["items"][0]["detalle"][0]["herramienta_codigo"], "KPISTOOL001")
        # Paginación limit 2 offset 0 vs offset 2
        page1 = service.get_inventarios_por_tecnico(_token_lectura(), self.tecnico_id, {"limit": 2, "offset": 0})
        page2 = service.get_inventarios_por_tecnico(_token_lectura(), self.tecnico_id, {"limit": 2, "offset": 2})
        self.assertEqual(len(page1["items"]), 2)
        self.assertEqual(len(page2["items"]), hist["total"] - 2)
        self.assertNotEqual(page1["items"][0]["id"], page2["items"][0]["id"])

    def test_08_historial_401_unauthorized(self):
        """Sin token historial debe 401."""
        result = service.get_inventarios_por_tecnico("", self.tecnico_id, {"limit": 10})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 401)
        result2 = service.get_tecnicos_cards("", {"limit": 10})
        self.assertIsInstance(result2, tuple)
        self.assertEqual(result2[1], 401)
        result3 = service.get_kpis_resumen("", {})
        self.assertIsInstance(result3, tuple)
        self.assertEqual(result3[1], 401)
        result4 = service.get_kpis_por_tecnico("", self.tecnico_id)
        self.assertIsInstance(result4, tuple)
        self.assertEqual(result4[1], 401)

    def test_09_kpis_resumen_global_avg(self):
        """KPIs resumen global avg debe calcularse correctamente."""
        _clean_kpis_state()
        service.put_ideal(_token(), {
            "nombre": "Ideal Global Avg",
            "detalle": [
                {"herramienta_codigo": "KPISTOOL001", "cantidad_minima": 1},
                {"herramienta_codigo": "KPISTOOL002", "cantidad_minima": 1},
            ]
        })
        # Técnico 1: 100% faltantes (sin inventario) -> usaremos otro tecnico generico sin inventario
        # Técnico under test: crear inventario full 0% faltantes
        _create_inventario_via_service(self.tecnico_id, "2026-09-01", self.caja_id, self.supervisor_id, [
            {"herramienta_codigo": "KPISTOOL001", "cantidad": 1, "presente": True},
            {"herramienta_codigo": "KPISTOOL002", "cantidad": 1, "presente": True},
        ])
        # Buscar otro tecnico (generico) que no tenga inventario -> será 100% faltantes
        # Ya tenemos 5 tecnicos; uno es self.tecnico_id con 0%, resto sin inventario => 100%
        kpis = service.get_kpis_resumen(_token_lectura(), {})
        self.assertIsInstance(kpis, dict)
        self.assertIn("avg_faltantes_pct", kpis)
        self.assertIn("avg_completitud_pct", kpis)
        self.assertIn("total_tecnicos", kpis)
        self.assertIn("tecnicos_con_inventario", kpis)
        self.assertIn("distribucion_faltantes", kpis)
        # avg deberia estar entre 0 y 100, no 0 ni 100 puro porque mezcla
        self.assertGreater(kpis["avg_faltantes_pct"], 0)
        self.assertLess(kpis["avg_faltantes_pct"], 100)
        # distribucion debe sumar total_tecnicos (incluye sin inventario como 75-100)
        total_dist = sum(kpis["distribucion_faltantes"].values())
        self.assertEqual(total_dist, kpis["total_tecnicos"])

    def test_10_kpis_por_tecnico_404(self):
        """KPIs por tecnico inexistente -> 404."""
        result = service.get_kpis_por_tecnico(_token_lectura(), 999999)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 404)
        # Historial también 404 para tecnico no encontrado
        result2 = service.get_inventarios_por_tecnico(_token_lectura(), 999999, {"limit": 10})
        self.assertIsInstance(result2, tuple)
        self.assertEqual(result2[1], 404)

    def test_11_limpieza_score_malo(self):
        """Limpieza_score derivado de estado='malo' / total *100."""
        _clean_kpis_state()
        service.put_ideal(_token(), {
            "nombre": "Ideal Limpieza",
            "detalle": [
                {"herramienta_codigo": "KPISTOOL001", "cantidad_minima": 1},
                {"herramienta_codigo": "KPISTOOL002", "cantidad_minima": 1},
            ]
        })
        # Crear inventario con 2 detalles ambos presente, uno malo
        res = _create_inventario_via_service(self.tecnico_id, "2026-09-01", self.caja_id, self.supervisor_id, [
            {"herramienta_codigo": "KPISTOOL001", "cantidad": 1, "presente": True},
            {"herramienta_codigo": "KPISTOOL002", "cantidad": 1, "presente": True},
        ])
        self.assertIsInstance(res, dict)
        inv_id = res["id"]
        # Cambiar segundo a malo
        _set_detalle_estado_malo(inv_id, "KPISTOOL002")
        # Verificar cards limpieza 50%
        cards = service.get_tecnicos_cards(_token_lectura(), {"limit": 50})
        target = next((c for c in cards["items"] if c["tecnico_id"] == self.tecnico_id), None)
        self.assertIsNotNone(target)
        # malos 1 / total 2 = 50%
        self.assertAlmostEqual(target["limpieza_score"], 50.0, places=1)
        # Verificar historial detalle también refleja malo
        hist = service.get_inventarios_por_tecnico(_token_lectura(), self.tecnico_id, {"limit": 5})
        inventario = next((h for h in hist["items"] if h["id"] == inv_id), None)
        self.assertIsNotNone(inventario)
        estados = {d["herramienta_codigo"]: d["estado"] for d in inventario["detalle"]}
        self.assertEqual(estados["KPISTOOL002"], "malo")
        # KPIs por tecnico limpieza también 50%
        kpi = service.get_kpis_por_tecnico(_token_lectura(), self.tecnico_id)
        self.assertAlmostEqual(kpi["limpieza_score"], 50.0, places=1)
        self.assertIn("historial", kpi)
        # Historial entry también debe tener mal_count
        hist_entry = kpi["historial"][0]
        self.assertIn("mal_count", hist_entry)
        self.assertEqual(hist_entry["mal_count"], 1)

    def test_12_invalid_limit_clamp(self):
        """Limit inválido se clamp a 1..100."""
        _clean_kpis_state()
        # limit 200 -> clamp 100
        result = service.get_tecnicos_cards(_token_lectura(), {"limit": 200, "offset": 0})
        self.assertIsInstance(result, dict)
        self.assertLessEqual(len(result["items"]), 100)
        # limit 0 -> clamp 1
        result2 = service.get_tecnicos_cards(_token_lectura(), {"limit": 0, "offset": 0})
        self.assertIsInstance(result2, dict)
        # Debe retornar max 1 por página si total>0? Pero clamp a 1 => limit 1 => 1 item
        if result2["total"] > 0:
            self.assertEqual(len(result2["items"]), 1)
        # limit negativo, offset negativo
        result3 = service.get_tecnicos_cards(_token_lectura(), {"limit": -5, "offset": -10})
        self.assertIsInstance(result3, dict)
        self.assertLessEqual(len(result3["items"]), 100)
        # Historial clamp
        hist = service.get_inventarios_por_tecnico(_token_lectura(), self.tecnico_id, {"limit": 500})
        self.assertLessEqual(len(hist["items"]), 100)
        # KPIs clamp via store directly
        kpis = service.get_kpis_resumen(_token_lectura(), {"limit": 500})
        # No error, limit clamped internally? Por ahora kpis no usa limit estrictamente pero no debe fallar
        self.assertIsInstance(kpis, dict)


if __name__ == "__main__":
    unittest.main()
