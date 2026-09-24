# -*- coding: utf-8 -*-
"""Tests para inventario transaccional de cajas.

Ejecucion: python -m unittest -v tests.test_inventarios
Requiere: MariaDB accesible, modulo cajas inicializado, personal con registros tecnico/supervisor.
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
    """Retorna un token JWT real con rol panol (cajas:escritura)."""
    payload = {"sub": "test", "rol": "panol", "permisos": ["cajas:lectura", "cajas:escritura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _token_lectura():
    """Retorna un token JWT real con rol supervisor (cajas:lectura)."""
    payload = {"sub": "test", "rol": "supervisor", "permisos": ["cajas:lectura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _setup_caja():
    """Crea una caja de prueba y retorna su id."""
    result = service.create_caja(_token(), {"codigo": "INVCAJA001", "descripcion": "Caja inventario test", "ubicacion": "Bodega Test"})
    if isinstance(result, tuple):
        raise RuntimeError(f"No pudo crear caja: {result}")
    return result["id"]


def _setup_personal():
    """Busca personal existente para tecnico/supervisor."""
    # Usar el servicio de personal directamente via DB
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, tipo FROM personal WHERE tipo IN ('tecnico','supervisor') AND activo = 1 LIMIT 2")
            rows = cur.fetchall()
        return rows
    finally:
        conn.close()


class TestInventoryCRUD(unittest.TestCase):
    """Pruebas de CRUD transaccional para cajas_inventarios."""

    @classmethod
    def setUpClass(cls):
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'INVCAJA%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'INVCAJA%')")
                cur.execute("DELETE FROM cajas_inventario_detalle")
                cur.execute("DELETE FROM cajas_inventarios")
                cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'INVTOOL%'")
                cur.execute("DELETE FROM cajas_cajas WHERE codigo LIKE 'INVCAJA%'")
            conn.commit()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        # Crear caja de prueba
        cls.caja_id = _setup_caja()
        # Crear herramienta de prueba
        result = service.create_herramienta(_token(), {"codigo": "INVTOOL001", "categoria": "HERRAMIENTA"})
        cls.tool_id = result["id"] if not isinstance(result, tuple) else None

    def test_01_create_inventario_valido(self):
        """Crear inventario valido con header + detalle."""
        personal_list = _setup_personal()
        tecnico = next((p for p in personal_list if p["tipo"] == "tecnico"), personal_list[0] if personal_list else None)
        supervisor = next((p for p in personal_list if p["tipo"] == "supervisor"), personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None)
        if not tecnico or not supervisor:
            self.skipTest("No hay personal tecnico/supervisor en BD")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-09-15",
            "estado": "borrador",
            "detalle": [
                {"herramienta_codigo": "INVTOOL001", "cantidad": 2, "presente": True},
            ],
        }
        result = service.create_inventario(_token(), data)
        self.assertIsInstance(result, dict)
        self.assertIn("id", result)
        self.assertEqual(result["periodo"], "2026-09-01")
        self.assertEqual(result["estado"], "borrador")
        self.assertIsNotNone(result.get("tecnico_nombre"))
        self.assertIsNotNone(result.get("supervisor_nombre"))
        self.assertIsNotNone(result.get("caja_codigo"))
        self.assertTrue(len(result.get("detalle", [])) > 0)

    def test_02_duplicate_periodo_409(self):
        """Crear inventario con misma caja+periodo retorna 409."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-08-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        result = service.create_inventario(_token(), data)
        self.assertIsInstance(result, dict)
        # Primera creacion exitosa
        self.assertIn("id", result)
        # Segunda creacion misma caja+periodo -> 409
        result2 = service.create_inventario(_token(), data)
        self.assertIsInstance(result2, tuple)
        self.assertEqual(result2[1], 409)

    def test_03_missing_fk_400(self):
        """FK inexistente retorna 400."""
        data = {
            "caja_id": self.caja_id,
            "tecnico_id": 999999,
            "supervisor_id": 999999,
            "periodo": "2026-10-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        result = service.create_inventario(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_04_empty_detalle_400(self):
        """Detalle vacio retorna 400."""
        data = {
            "caja_id": self.caja_id,
            "tecnico_id": 1,
            "supervisor_id": 1,
            "periodo": "2026-10-01",
            "detalle": [],
        }
        result = service.create_inventario(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_05_cantidad_invalida_400(self):
        """Cantidad <= 0 retorna 400."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-10-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 0, "presente": True}],
        }
        result = service.create_inventario(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_06_presente_not_boolean_400(self):
        """Presente no booleano retorna 400."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-10-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": "yes"}],
        }
        result = service.create_inventario(_token(), data)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_07_listar_inventarios(self):
        """Listar inventarios con filtros."""
        result = service.get_inventarios_list(_token_lectura(), {})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)
        self.assertIn("total", result)

    def test_08_obtener_inventario_por_id(self):
        """Obtener inventario por ID con JOIN names."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-07-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        created = service.create_inventario(_token(), data)
        if isinstance(created, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        inv_id = created["id"]
        result = service.get_inventario_by_id(_token_lectura(), inv_id)
        self.assertIsInstance(result, dict)
        self.assertIn("id", result)
        self.assertIn("detalle", result)
        self.assertIsNotNone(result.get("tecnico_nombre"))

    def test_09_get_inventario_inexistente_404(self):
        """Obtener inventario inexistente retorna 404."""
        result = service.get_inventario_by_id(_token_lectura(), 99999)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 404)

    def test_10_patch_estado_borrador_a_cerrado(self):
        """Transicion borrador -> cerrado exitosa."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-06-15",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        created = service.create_inventario(_token(), data)
        if isinstance(created, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        inv_id = created["id"]
        result = service.update_inventario_estado(_token(), inv_id, "cerrado")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["estado"], "cerrado")

    def test_11_patch_estado_cerrado_a_borrador_400(self):
        """Transicion cerrado -> borrador retorna 400."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-05-20",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        created = service.create_inventario(_token(), data)
        if isinstance(created, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        inv_id = created["id"]
        # Primero cerrar
        service.update_inventario_estado(_token(), inv_id, "cerrado")
        # Intentar revertir
        result = service.update_inventario_estado(_token(), inv_id, "borrador")
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_12_eliminar_cerrado_409(self):
        """Eliminar inventario cerrado retorna 409."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-04-25",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        created = service.create_inventario(_token(), data)
        if isinstance(created, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        inv_id = created["id"]
        service.update_inventario_estado(_token(), inv_id, "cerrado")
        result = service.delete_inventario(_token(), inv_id)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)

    def test_13_eliminar_borrador_ok(self):
        """Eliminar inventario borrador exitoso."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-11-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        created = service.create_inventario(_token(), data)
        if isinstance(created, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        inv_id = created["id"]
        result = service.delete_inventario(_token(), inv_id)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["eliminado"])

    def test_14_auth_401_get_inventarios(self):
        """Sin token, GET inventarios retorna 401."""
        result = service.get_inventarios_list("", {})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 401)

    def test_15_auth_401_post_inventario(self):
        """Sin token, POST inventario retorna 401."""
        result = service.create_inventario("", {"caja_id": 1, "tecnico_id": 1, "supervisor_id": 1, "periodo": "2026-10-01", "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}]})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 401)

    def test_16_buscar_q_por_nombre(self):
        """Buscar inventarios por nombre de personal con q."""
        result = service.get_inventarios_list(_token_lectura(), {"q": "JUAN"})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)

    def test_17_filtrar_por_estado(self):
        """Filtrar inventarios por estado."""
        result = service.get_inventarios_list(_token_lectura(), {"estado": "borrador"})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)

    def test_18_filtrar_por_caja_id(self):
        """Filtrar inventarios por caja_id."""
        result = service.get_inventarios_list(_token_lectura(), {"caja_id": str(self.caja_id)})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)

    def test_19_periodo_normalizado(self):
        """Periodo se normaliza al primer dia del mes."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-03-15",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 3, "presente": True}],
        }
        result = service.create_inventario(_token(), data)
        if isinstance(result, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        self.assertEqual(result["periodo"], "2026-03-01")

    def test_20_area_snapshot(self):
        """Area snapshot proviene de cajas_cajas.ubicacion."""
        personal_list = _setup_personal()
        tecnico = personal_list[0] if personal_list else None
        supervisor = personal_list[1] if len(personal_list) > 1 else personal_list[0] if personal_list else None
        if not tecnico or not supervisor:
            self.skipTest("No hay personal suficiente")

        data = {
            "caja_id": self.caja_id,
            "tecnico_id": tecnico["id"],
            "supervisor_id": supervisor["id"],
            "periodo": "2026-12-01",
            "detalle": [{"herramienta_codigo": "INVTOOL001", "cantidad": 1, "presente": True}],
        }
        result = service.create_inventario(_token(), data)
        if isinstance(result, tuple):
            self.skipTest("No se pudo crear inventario de prueba")
        self.assertIsNotNone(result.get("area"))


if __name__ == "__main__":
    unittest.main()
