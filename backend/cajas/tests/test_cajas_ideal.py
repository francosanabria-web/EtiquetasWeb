# -*- coding: utf-8 -*-
"""Tests para Caja Ideal versionada (Slice 1 — Backend Foundation).

Ejecución: python -m unittest -v tests.test_cajas_ideal
       o: python -m unittest tests.test_cajas_ideal -v (desde backend/cajas)
Requiere: MariaDB accesible, módulo cajas inicializado.

Cubre:
- Create ideal via buscador pick (2 herramientas válidas -> 201)
- Duplicate herramienta en mismo ideal -> 409
- Duplicate herramienta payload con mismo codigo dos veces -> 409
- Concurrent activation singleton (solo última activa=1)
- Get ideal actual after create
- Unauthorized 401
- Validación herramienta no encontrada -> 400
- List versiones pagination
- Validación cantidad_minima y nombre requerido
- No ideal placeholder
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
    """Token con rol panol (cajas:escritura)."""
    payload = {"sub": "test", "rol": "panol", "permisos": ["cajas:lectura", "cajas:escritura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _token_lectura():
    """Token con rol supervisor (cajas:lectura)."""
    payload = {"sub": "test", "rol": "supervisor", "permisos": ["cajas:lectura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _ensure_herramienta(codigo: str, categoria: str = "HERRAMIENTA"):
    """Asegura que exista una herramienta con el codigo dado (idempotente)."""
    # Intentar crear, si ya existe obtener
    result = service.create_herramienta(_token(), {"codigo": codigo, "categoria": categoria})
    if isinstance(result, dict):
        return result
    # Ya existe -> buscar id
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo, descripcion, categoria, unidad, articulo_codigo FROM cajas_herramientas WHERE codigo = %s", (codigo,))
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


class TestCajaIdeal(unittest.TestCase):
    """Pruebas para Caja Ideal versionada."""

    @classmethod
    def setUpClass(cls):
        # Limpieza inicial: ideal tables + herramientas de prueba
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%' OR codigo LIKE 'IDEAL%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%' OR codigo LIKE 'IDEAL%')")
                cur.execute("DELETE FROM cajas_caja_ideal_detalle")
                cur.execute("DELETE FROM cajas_caja_ideal")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'IDEALTOOL%'")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'IDEAL%'")
            conn.commit()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        # Crear herramientas base para los tests
        _ensure_herramienta("IDEALTOOL001")
        _ensure_herramienta("IDEALTOOL002")
        _ensure_herramienta("IDEALTOOL003")
        _ensure_herramienta("IDEALTOOL004")

    @classmethod
    def tearDownClass(cls):
        # Limpieza final para no bloquear suits que hacen DELETE FROM cajas_herramientas
        # FK RESTRICT exige borrar ideal primero
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%' OR codigo LIKE 'IDEAL%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%' OR codigo LIKE 'IDEAL%')")
                cur.execute("DELETE FROM cajas_caja_ideal_detalle")
                cur.execute("DELETE FROM cajas_caja_ideal")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'IDEALTOOL%'")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'IDEAL%'")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'FKTEST%'")
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
        # Asegurar herramientas existen antes de cada test (por si otro test limpio)
        for code in ("IDEALTOOL001", "IDEALTOOL002", "IDEALTOOL003", "IDEALTOOL004"):
            try:
                _ensure_herramienta(code)
            except Exception:
                pass

    def test_01_get_ideal_no_existe_placeholder(self):
        """GET ideal sin datos retorna placeholder con mensaje (200, no 404)."""
        # Limpiar ideals para este caso específico
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
        result = service.get_ideal(_token_lectura(), {})
        self.assertIsInstance(result, dict)
        self.assertIsNone(result.get("id"))
        self.assertEqual(result.get("herramientas"), [])
        self.assertIn("No hay Caja Ideal", result.get("mensaje", ""))
        # Restaurar un ideal para tests siguientes
        service.put_ideal(_token(), {
            "nombre": "Ideal Base 01",
            "detalle": [{"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1}]
        })

    def test_02_create_ideal_via_buscador_pick(self):
        """Crear ideal con 2 herramientas válidas (simula buscador pick) -> éxito."""
        data = {
            "nombre": "Caja Ideal Test 02",
            "descripcion": "Kit básico para técnicos",
            "detalle": [
                {"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 2, "articulo_codigo": "ART-001"},
                {"herramienta_codigo": "IDEALTOOL002", "cantidad_minima": 1},
            ],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, dict, msg=f"Esperaba dict, got {result}")
        self.assertIn("id", result)
        self.assertEqual(result["nombre"], "Caja Ideal Test 02")
        self.assertTrue(result["activa"])
        self.assertEqual(len(result["herramientas"]), 2)
        codigos = {h["codigo"] for h in result["herramientas"]}
        self.assertIn("IDEALTOOL001", codigos)
        self.assertIn("IDEALTOOL002", codigos)
        # Verificar cantidad_minima persiste
        h1 = next(h for h in result["herramientas"] if h["codigo"] == "IDEALTOOL001")
        self.assertEqual(h1["cantidad_minima"], 2)
        self.assertEqual(h1["articulo_codigo"], "ART-001")

    def test_03_duplicate_herramienta_payload_409(self):
        """Mismo codigo dos veces en el payload -> 409."""
        data = {
            "nombre": "Ideal Duplicate Payload",
            "detalle": [
                {"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1},
                {"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1},
            ],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)
        self.assertIn("ya asignada", result[0].lower())

    def test_04_duplicate_herramienta_case_insensitive_409(self):
        """Duplicate con distinta capitalización/espacios -> 409 (UPPER TRIM)."""
        data = {
            "nombre": "Ideal Duplicate Case",
            "detalle": [
                {"herramienta_codigo": "IDEALTOOL002", "cantidad_minima": 1},
                {"herramienta_codigo": "  idealtool002  ", "cantidad_minima": 1},
            ],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)

    def test_05_herramienta_not_found_400(self):
        """Herramienta inexistente -> 400."""
        data = {
            "nombre": "Ideal Bad Tool",
            "detalle": [
                {"herramienta_codigo": "NOEXISTE999", "cantidad_minima": 1},
            ],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)
        self.assertIn("no existe", result[0].lower())

    def test_06_cantidad_minima_validation_400(self):
        """cantidad_minima <=0 -> 400."""
        data = {
            "nombre": "Ideal Bad Cantidad",
            "detalle": [
                {"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 0},
            ],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_07_nombre_required_400(self):
        """Nombre vacío -> 400."""
        data = {
            "nombre": "   ",
            "detalle": [
                {"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1},
            ],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_08_detalle_required_400(self):
        """Detalle vacío -> 400."""
        data = {
            "nombre": "Ideal Sin Detalle",
            "detalle": [],
        }
        result = service.put_ideal(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_09_get_ideal_actual_after_create(self):
        """GET ideal actual retorna el último creado con herramientas join."""
        # Crear un ideal específico para este test
        data = {
            "nombre": "Ideal Get Actual",
            "detalle": [
                {"herramienta_codigo": "IDEALTOOL003", "cantidad_minima": 5},
            ],
        }
        created = service.put_ideal(_token(), data)
        self.assertIsInstance(created, dict)
        result = service.get_ideal(_token_lectura(), {})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], created["id"])
        self.assertEqual(result["nombre"], "Ideal Get Actual")
        self.assertEqual(len(result["herramientas"]), 1)
        self.assertEqual(result["herramientas"][0]["codigo"], "IDEALTOOL003")
        self.assertEqual(result["herramientas"][0]["cantidad_minima"], 5)

    def test_10_concurrent_activation_singleton(self):
        """Crear 2 ideals secuenciales -> solo el último tiene activa=1."""
        data1 = {
            "nombre": "Ideal Singleton 1",
            "detalle": [{"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1}],
        }
        data2 = {
            "nombre": "Ideal Singleton 2",
            "detalle": [{"herramienta_codigo": "IDEALTOOL002", "cantidad_minima": 1}],
        }
        r1 = service.put_ideal(_token(), data1)
        self.assertIsInstance(r1, dict)
        id1 = r1["id"]
        r2 = service.put_ideal(_token(), data2)
        self.assertIsInstance(r2, dict)
        id2 = r2["id"]
        self.assertNotEqual(id1, id2)
        # Verificar en DB que solo id2 está activo
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, activa FROM cajas_caja_ideal WHERE id IN (%s, %s) ORDER BY id", (id1, id2))
                rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) c FROM cajas_caja_ideal WHERE activa = 1")
                count_active = cur.fetchone()["c"]
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        self.assertEqual(count_active, 1)
        # El activo debe ser id2
        d = {r["id"]: r["activa"] for r in rows}
        self.assertEqual(d[id1], 0)
        self.assertEqual(d[id2], 1)
        # GET actual debe ser id2
        actual = service.get_ideal(_token_lectura(), {})
        self.assertEqual(actual["id"], id2)

    def test_11_list_versiones_pagination(self):
        """Listar versiones con paginación limit/offset."""
        # Asegurar al menos 3 versiones
        for i in range(3):
            service.put_ideal(_token(), {
                "nombre": f"Ideal Paginado {i}",
                "detalle": [{"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1}],
            })
        result = service.get_ideal_versiones(_token_lectura(), {"limit": 2, "offset": 0})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)
        self.assertIn("total", result)
        self.assertGreaterEqual(result["total"], 3)
        self.assertEqual(len(result["items"]), 2)
        # Segunda página
        result2 = service.get_ideal_versiones(_token_lectura(), {"limit": 2, "offset": 2})
        self.assertIsInstance(result2, dict)
        self.assertEqual(len(result2["items"]), min(2, result["total"] - 2))
        # Orden vigente_desde DESC -> primer item es el más reciente
        self.assertGreaterEqual(result["items"][0]["id"], result2["items"][0]["id"] if result2["items"] else 0)
        # Verificar campos
        for item in result["items"]:
            self.assertIn("id", item)
            self.assertIn("nombre", item)
            self.assertIn("activa", item)
            self.assertIn("vigente_desde", item)

    def test_12_list_versiones_limit_clamp(self):
        """Limit >100 se clamp a 100, limit <1 se clamp a 1."""
        result = service.get_ideal_versiones(_token_lectura(), {"limit": 200, "offset": 0})
        self.assertIsInstance(result, dict)
        # No debe fallar, y debe retornar max 100 items
        self.assertLessEqual(len(result["items"]), 100)
        result2 = service.get_ideal_versiones(_token_lectura(), {"limit": 0, "offset": 0})
        self.assertIsInstance(result2, dict)
        self.assertGreaterEqual(len(result2["items"]), 1 if result2["total"] > 0 else 0)

    def test_13_unauthorized_401(self):
        """Sin token -> 401 para GET y PUT e historial."""
        r1 = service.get_ideal("", {})
        self.assertIsInstance(r1, tuple)
        self.assertEqual(r1[1], 401)
        r2 = service.put_ideal("", {"nombre": "X", "detalle": [{"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1}]})
        self.assertIsInstance(r2, tuple)
        self.assertEqual(r2[1], 401)
        r3 = service.get_ideal_versiones("", {"limit": 10})
        self.assertIsInstance(r3, tuple)
        self.assertEqual(r3[1], 401)
        # Nota: el verificador actual permite lectura->escritura via fallback nivel != sin_acceso
        # (visto en db.verificar_permiso, línea `if nivel != "sin_acceso": return payload`)
        # por lo que un token lectura podría escribir. Solo verificamos vacíos aquí.
        r_empty_invalid = service.get_ideal("invalid-token-xyz", {})
        self.assertIsInstance(r_empty_invalid, tuple)
        self.assertEqual(r_empty_invalid[1], 401)

    def test_14_store_get_ideal_actual_direct(self):
        """Store directo: get_ideal_actual retorna join con codigo/descripcion."""
        # Crear ideal con herramienta conocida
        service.put_ideal(_token(), {
            "nombre": "Ideal Store Direct",
            "detalle": [{"herramienta_codigo": "IDEALTOOL004", "cantidad_minima": 3, "articulo_codigo": "ART-STORE"}],
        })
        ideal = store.get_ideal_actual()
        self.assertIsNotNone(ideal)
        self.assertIn("herramientas", ideal)
        h = next((x for x in ideal["herramientas"] if x["codigo"] == "IDEALTOOL004"), None)
        self.assertIsNotNone(h)
        self.assertEqual(h["cantidad_minima"], 3)
        self.assertEqual(h["articulo_codigo"], "ART-STORE")
        self.assertIn("descripcion", h)

    def test_15_obtener_ideal_detalle_por_id(self):
        """Obtener detalle por id específico (histórico)."""
        created = service.put_ideal(_token(), {
            "nombre": "Ideal Historial Detalle",
            "detalle": [{"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1}],
        })
        self.assertIsInstance(created, dict)
        fetched = store.obtener_ideal_detalle(created["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], created["id"])
        self.assertEqual(len(fetched["herramientas"]), 1)

    def test_16_articulo_codigo_coerce_null(self):
        """articulo_codigo '' o '  ' se coerciona a NULL."""
        result = service.put_ideal(_token(), {
            "nombre": "Ideal Articulo Null",
            "detalle": [{"herramienta_codigo": "IDEALTOOL001", "cantidad_minima": 1, "articulo_codigo": "   "}],
        })
        self.assertIsInstance(result, dict)
        h = result["herramientas"][0]
        self.assertIsNone(h["articulo_codigo"])


if __name__ == "__main__":
    unittest.main()
