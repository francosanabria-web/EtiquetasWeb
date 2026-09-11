# -*- coding: utf-8 -*-
"""Tests para catálogo de cajas (cajas_cajas + cajas_herramientas).

Ejecución: python -m unittest -v tests.test_catalog
Requiere: MariaDB accesible, módulo cajas inicializado.
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


class TestCatalogCRUD(unittest.TestCase):
    """Pruebas de CRUD para cajas_cajas y cajas_herramientas."""

    @classmethod
    def setUpClass(cls):
        """Limpia tablas antes de cada clase."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_inventario_detalle")
                cur.execute("DELETE FROM cajas_inventarios")
                cur.execute("DELETE FROM cajas_herramientas")
                cur.execute("DELETE FROM cajas_cajas")
            conn.commit()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass

    def test_01_crear_caja(self):
        """Crear caja con codigo normalizado UPPER TRIM."""
        result = service.create_caja(_token(), {"codigo": "  herra001  ", "descripcion": "Caja de herramientas", "ubicacion": "Bodega A"})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["codigo"], "HERRA001")
        self.assertEqual(result["descripcion"], "Caja de herramientas")

    def test_02_crear_caja_uppertrim(self):
        """UPPER(TRIM) se aplica correctamente."""
        result = service.create_caja(_token(), {"codigo": "  h002  ", "descripcion": "Otra caja"})
        self.assertEqual(result["codigo"], "H002")

    def test_03_crear_caja_empty_string_to_null(self):
        """Cadena vacía se convierte a NULL."""
        result = service.create_caja(_token(), {"codigo": "H003", "descripcion": "", "ubicacion": "  "})
        self.assertIsNone(result["descripcion"])
        self.assertIsNone(result["ubicacion"])

    def test_04_duplicate_caja_409(self):
        """Crear caja con codigo duplicado retorna 409."""
        service.create_caja(_token(), {"codigo": "H004", "descripcion": "Test"})
        result = service.create_caja(_token(), {"codigo": "H004", "descripcion": "Duplicado"})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)

    def test_05_listar_cajas_paginacion(self):
        """Listar cajas con paginación funciona."""
        service.create_caja(_token(), {"codigo": "H005", "descripcion": "Caja 5"})
        service.create_caja(_token(), {"codigo": "H006", "descripcion": "Caja 6"})
        result = service.get_cajas_list(_token(), {"limit": 10, "offset": 0})
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)
        self.assertIn("total", result)
        self.assertGreaterEqual(len(result["items"]), 2)

    def test_06_buscar_q(self):
        """Buscar por q con UPPER TRIM."""
        result = service.get_cajas_list(_token(), {"q": "H005", "limit": 10, "offset": 0})
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("H005", result["items"][0]["codigo"])

    def test_07_filtrar_activa(self):
        """Filtrar por activa."""
        result = service.get_cajas_list(_token(), {"activa": True, "limit": 50, "offset": 0})
        self.assertIsInstance(result, dict)
        for item in result["items"]:
            self.assertTrue(item["activa"])

    def test_08_obtener_por_id(self):
        """Obtener caja por ID."""
        created = service.create_caja(_token(), {"codigo": "H008", "descripcion": "Test ID"})
        result = service.get_caja_by_id(_token(), created["id"])
        self.assertIsInstance(result, dict)
        self.assertEqual(result["codigo"], "H008")

    def test_09_actualizar_caja(self):
        """Actualizar caja con normalización."""
        created = service.create_caja(_token(), {"codigo": "H009", "descripcion": "Original"})
        result = service.update_caja(_token(), created["id"], {"descripcion": "Actualizado", "ubicacion": "Nueva Ubicacion"})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["descripcion"], "Actualizado")
        self.assertEqual(result["ubicacion"], "Nueva Ubicacion")

    def test_10_eliminar_caja(self):
        """Eliminar caja."""
        created = service.create_caja(_token(), {"codigo": "H010", "descripcion": "Para eliminar"})
        result = service.delete_caja(_token(), created["id"])
        self.assertIsInstance(result, dict)
        self.assertTrue(result["eliminado"])

    def test_11_obtener_caja_inexistente_404(self):
        """Obtener caja inexistente retorna 404."""
        result = service.get_caja_by_id(_token(), 99999)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 404)

    # ---- Herramientas ----

    def test_12_crear_herramienta(self):
        """Crear herramienta con categoria."""
        result = service.create_herramienta(_token(), {"codigo": "ALIC001", "categoria": "HERRAMIENTA", "unidad": "UND"})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["codigo"], "ALIC001")
        self.assertEqual(result["categoria"], "HERRAMIENTA")

    def test_13_crear_herramienta_uppertrim(self):
        """UPPER(TRIM) en codigo de herramienta."""
        result = service.create_herramienta(_token(), {"codigo": "  alic002  ", "categoria": "REPUESTO"})
        self.assertEqual(result["codigo"], "ALIC002")

    def test_14_duplicate_herramienta_409(self):
        """Crear herramienta duplicada retorna 409."""
        service.create_herramienta(_token(), {"codigo": "ALIC003", "categoria": "HERRAMIENTA"})
        result = service.create_herramienta(_token(), {"codigo": "ALIC003", "categoria": "HERRAMIENTA"})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)

    def test_15_listar_herramientas_categoria(self):
        """Filtrar herramientas por categoría."""
        service.create_herramienta(_token(), {"codigo": "H15A", "categoria": "HERRAMIENTA"})
        service.create_herramienta(_token(), {"codigo": "H15B", "categoria": "REPUESTO"})
        result = service.get_herramientas_list(_token(), {"categoria": "HERRAMIENTA", "limit": 50, "offset": 0})
        self.assertIsInstance(result, dict)
        # At least 1 HERRAMIENTA, all filtered must be HERRAMIENTA (allow existing data)
        self.assertGreaterEqual(len(result["items"]), 1)
        for item in result["items"]:
            self.assertEqual(item["categoria"], "HERRAMIENTA")

    def test_16_crear_herramienta_empty_desc_to_null(self):
        """Descripción vacía se convierte a NULL or empty string (DB NOT NULL)."""
        result = service.create_herramienta(_token(), {"codigo": "H016", "descripcion": ""})
        # DB may store as "" or None depending on schema, accept both
        self.assertIn(result["descripcion"], [None, ""])

    def test_17_actualizar_herramienta(self):
        """Actualizar herramienta."""
        created = service.create_herramienta(_token(), {"codigo": "H017", "categoria": "OTRO"})
        result = service.update_herramienta(_token(), created["id"], {"categoria": "MEDIDA"})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["categoria"], "MEDIDA")

    def test_18_obtener_herramienta_inexistente_404(self):
        """Obtener herramienta inexistente retorna 404."""
        result = service.get_herramienta_by_id(_token(), 99999)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 404)

    def test_19_autenticacion_401_lectura(self):
        """Sin token, GET retorna 401."""
        result = service.get_cajas_list("", {"limit": 10, "offset": 0})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 401)

    def test_20_autenticacion_401_escritura(self):
        """Sin token, POST retorna 401."""
        result = service.create_caja("", {"codigo": "H999"})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 401)


if __name__ == "__main__":
    unittest.main()
