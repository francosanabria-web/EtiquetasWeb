# -*- coding: utf-8 -*-
"""Tests Fase 2 — Backend hardening (permisos estrictos) + DDL limpieza/asignaciones + CRUD.

Ejecución: python -m unittest -v tests.test_cajas_fase2_backend
Requiere: MariaDB accesible, módulo cajas inicializado.

Cubre:
- permiso strict: supervisor lectura PUT ideal →401, admin escritura →201, jefatura lectura GET 200 pero PUT 401
- limpieza: create valid →201, list pagination, filter estado, invalid estado 400, FK not found 400, update transición, delete solo pendiente
- asignaciones: create →201, second assign misma caja diferente técnico cierra previa (activa invariant), list active filter, cerrar endpoint, duplicate active 409, invalid 400
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


def _token_admin():
    """admin → cajas:escritura"""
    payload = {"sub": "1", "rol": "admin", "permisos": ["cajas:escritura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _token_panol():
    """panol → cajas:escritura"""
    payload = {"sub": "2", "rol": "panol", "permisos": ["cajas:escritura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _token_supervisor():
    """supervisor → cajas:lectura"""
    payload = {"sub": "3", "rol": "supervisor", "permisos": ["cajas:lectura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _token_jefatura():
    """jefatura → cajas:lectura"""
    payload = {"sub": "4", "rol": "jefatura", "permisos": ["cajas:lectura"]}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _ensure_herramienta(codigo: str):
    result = service.create_herramienta(_token_panol(), {"codigo": codigo, "categoria": "HERRAMIENTA"})
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
    raise RuntimeError(f"No se pudo asegurar herramienta {codigo}")


def _ensure_caja(codigo: str = "FASE2CAJA001"):
    # Buscar existente
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo FROM cajas_cajas WHERE codigo = %s", (codigo,))
            row = cur.fetchone()
            if row:
                return row
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass
    result = service.create_caja(_token_panol(), {"codigo": codigo, "descripcion": "Caja fase2", "ubicacion": "Panol"})
    if isinstance(result, dict):
        return result
    # Fallback fetch again
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, codigo FROM cajas_cajas WHERE codigo = %s", (codigo,))
            return cur.fetchone()
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


def _get_personal_tecnico_ids(limit=5):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, tipo FROM personal WHERE tipo IN ('tecnico','supervisor','generico','panol') AND activo=1 ORDER BY id ASC LIMIT %s", (limit,))
            return cur.fetchall()
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass
    return []


def _clean_fase2():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cajas_asignaciones")
            cur.execute("DELETE FROM cajas_limpieza_historial")
        conn.commit()
    finally:
        try:
            if conn.open:
                conn.close()
        except Exception:
            pass


class TestPermisosEstrictos(unittest.TestCase):
    """Permisos estrictos: verificar que escritura requiere escritura, lectura requiere lectura/escritura."""

    @classmethod
    def setUpClass(cls):
        # Asegurar herramientas para ideal
        for code in ("FASE2TOOL001", "FASE2TOOL002"):
            try:
                _ensure_herramienta(code)
            except Exception:
                pass
        _ensure_caja("FASE2CAJA001")
        _clean_fase2()

    def setUp(self):
        for code in ("FASE2TOOL001", "FASE2TOOL002"):
            try:
                _ensure_herramienta(code)
            except Exception:
                pass

    def test_01_supervisor_lectura_put_ideal_401(self):
        """supervisor (lectura) PUT ideal → 401."""
        data = {"nombre": "Ideal Permiso Test Supervisor", "detalle": [{"herramienta_codigo": "FASE2TOOL001", "cantidad_minima": 1}]}
        result = service.put_ideal(_token_supervisor(), data)
        self.assertIsInstance(result, tuple, msg=f"Se esperaba 401, got {result}")
        self.assertEqual(result[1], 401)

    def test_02_admin_escritura_put_ideal_201(self):
        """admin (escritura) PUT ideal → 201/200."""
        data = {"nombre": "Ideal Permiso Admin", "detalle": [{"herramienta_codigo": "FASE2TOOL001", "cantidad_minima": 1}]}
        result = service.put_ideal(_token_admin(), data)
        self.assertIsInstance(result, dict, msg=f"Esperaba dict, got {result}")
        self.assertIn("id", result)
        self.assertTrue(result["activa"])

    def test_03_jefatura_lectura_get_200_put_401(self):
        """jefatura lectura GET →200 pero PUT →401."""
        # GET debe pasar
        get_res = service.get_ideal(_token_jefatura(), {})
        self.assertIsInstance(get_res, dict, msg=f"GET jefatura debería ser 200 dict, got {get_res}")
        # No debe ser tuple 401
        self.assertNotIsInstance(get_res, tuple)
        # PUT debe fallar
        data = {"nombre": "Ideal Jefatura Fail", "detalle": [{"herramienta_codigo": "FASE2TOOL001", "cantidad_minima": 1}]}
        put_res = service.put_ideal(_token_jefatura(), data)
        self.assertIsInstance(put_res, tuple)
        self.assertEqual(put_res[1], 401)

    def test_04_lectura_no_puede_crear_limpieza(self):
        """supervisor lectura no puede POST limpieza →401, pero puede GET."""
        personal = _get_personal_tecnico_ids(2)
        if len(personal) < 1:
            self.skipTest("No hay personal")
        caja = _ensure_caja("FASE2CAJA001")
        # GET con lectura debe pasar (200)
        list_res = service.get_limpieza_list(_token_supervisor(), {})
        self.assertIsInstance(list_res, dict)
        self.assertIn("items", list_res)
        # POST con lectura debe 401
        post_res = service.create_limpieza(_token_supervisor(), {"caja_id": caja["id"], "tecnico_id": personal[0]["id"]})
        self.assertIsInstance(post_res, tuple)
        self.assertEqual(post_res[1], 401)

    def test_05_lectura_no_puede_crear_asignacion(self):
        """supervisor lectura no puede POST asignacion →401, pero puede GET."""
        personal = _get_personal_tecnico_ids(2)
        if len(personal) < 1:
            self.skipTest("No hay personal")
        caja = _ensure_caja("FASE2CAJA001")
        list_res = service.get_asignaciones_list(_token_supervisor(), {})
        self.assertIsInstance(list_res, dict)
        post_res = service.create_asignacion(_token_supervisor(), {"caja_id": caja["id"], "tecnico_id": personal[0]["id"], "desde": "2026-09-01"})
        self.assertIsInstance(post_res, tuple)
        self.assertEqual(post_res[1], 401)

    def test_06_sin_token_401(self):
        """Sin token →401 para todas las operaciones fase2."""
        self.assertEqual(service.get_limpieza_list("", {})[1], 401)
        self.assertEqual(service.create_limpieza("", {"caja_id": 1, "tecnico_id": 1})[1], 401)
        self.assertEqual(service.get_asignaciones_list("", {})[1], 401)
        self.assertEqual(service.create_asignacion("", {"caja_id": 1, "tecnico_id": 1, "desde": "2026-09-01"})[1], 401)

    def test_07_escritura_puede_todo(self):
        """panol/admin escritura puede crear limpieza y asignacion →201."""
        personal = _get_personal_tecnico_ids(2)
        if len(personal) < 1:
            self.skipTest("No hay personal")
        caja = _ensure_caja("FASE2CAJA001")
        _clean_fase2()
        res_lim = service.create_limpieza(_token_panol(), {"caja_id": caja["id"], "tecnico_id": personal[0]["id"], "observaciones": "test escritura"})
        self.assertIsInstance(res_lim, dict, msg=f"panol limpieza fail {res_lim}")
        res_asig = service.create_asignacion(_token_admin(), {"caja_id": caja["id"], "tecnico_id": personal[0]["id"], "desde": "2026-09-15"})
        self.assertIsInstance(res_asig, dict, msg=f"admin asignacion fail {res_asig}")

    @classmethod
    def tearDownClass(cls):
        # Limpieza para no dejar residuos que bloqueen otros suites (FK RESTRICT)
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
                cur.execute("DELETE FROM cajas_caja_ideal_detalle WHERE caja_ideal_id IN (SELECT id FROM cajas_caja_ideal WHERE nombre LIKE 'Ideal Permiso%%')")
                cur.execute("DELETE FROM cajas_caja_ideal WHERE nombre LIKE 'Ideal Permiso%%'")
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


class TestLimpiezaCRUD(unittest.TestCase):
    """CRUD limpieza_historial."""

    @classmethod
    def setUpClass(cls):
        for code in ("FASE2TOOL001",):
            try:
                _ensure_herramienta(code)
            except Exception:
                pass
        cls.caja = _ensure_caja("FASE2CAJA001")
        cls.caja2 = _ensure_caja("FASE2CAJA_LIMPIEZA")
        personal = _get_personal_tecnico_ids(4)
        cls.personal = personal
        cls.tecnico_id = personal[0]["id"] if personal else 1
        cls.tecnico2_id = personal[1]["id"] if len(personal) > 1 else cls.tecnico_id
        _clean_fase2()

    def setUp(self):
        # Asegurar caja/personal existen
        try:
            _ensure_caja("FASE2CAJA001")
            _ensure_caja("FASE2CAJA_LIMPIEZA")
        except Exception:
            pass

    def test_10_create_limpieza_valid_201(self):
        """Crear limpieza con caja/tecnico válidos →201."""
        _clean_fase2()
        data = {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "observaciones": "limpieza test", "estado": "pendiente"}
        result = service.create_limpieza(_token_panol(), data)
        self.assertIsInstance(result, dict, msg=f"create limpieza fail {result}")
        self.assertIn("id", result)
        self.assertEqual(result["caja_id"], self.caja["id"])
        self.assertEqual(result["tecnico_id"], self.tecnico_id)
        self.assertEqual(result["estado"], "pendiente")
        self.assertIsNotNone(result.get("fecha"))
        # verificar técnico nombre viene join
        self.assertIsNotNone(result.get("tecnico_nombre"))

    def test_11_list_pagination(self):
        """Listar limpieza con paginación limit/offset."""
        _clean_fase2()
        # Crear 3 eventos
        for i in range(3):
            service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "observaciones": f"evento {i}", "estado": "pendiente"})
        # Listar con limit 2
        res = service.get_limpieza_list(_token_supervisor(), {"limit": 2, "offset": 0})
        self.assertIsInstance(res, dict)
        self.assertIn("items", res)
        self.assertIn("total", res)
        self.assertGreaterEqual(res["total"], 3)
        self.assertEqual(len(res["items"]), 2)
        res2 = service.get_limpieza_list(_token_supervisor(), {"limit": 2, "offset": 2})
        self.assertEqual(len(res2["items"]), res["total"] - 2)
        # Orden fecha DESC
        if res["items"] and res2["items"]:
            self.assertGreaterEqual(res["items"][0]["id"], res2["items"][0]["id"])

    def test_12_filter_estado(self):
        """Filtrar limpieza por estado."""
        _clean_fase2()
        service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "pendiente"})
        service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "realizada"})
        service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "vencida"})
        res_pend = service.get_limpieza_list(_token_supervisor(), {"estado": "pendiente"})
        self.assertIsInstance(res_pend, dict)
        for item in res_pend["items"]:
            self.assertEqual(item["estado"], "pendiente")
        res_real = service.get_limpieza_list(_token_supervisor(), {"estado": "realizada"})
        for item in res_real["items"]:
            self.assertEqual(item["estado"], "realizada")
        self.assertGreaterEqual(res_pend["total"], 1)
        self.assertGreaterEqual(res_real["total"], 1)

    def test_13_invalid_estado_400(self):
        """Estado inválido →400."""
        result = service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "invalido"})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_14_fk_caja_not_found_400(self):
        """FK caja_id inexistente →400."""
        result = service.create_limpieza(_token_panol(), {"caja_id": 999999, "tecnico_id": self.tecnico_id})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)
        self.assertIn("no existe", result[0].lower())

    def test_15_fk_tecnico_not_found_400(self):
        """FK tecnico_id inexistente →400."""
        result = service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": 999999})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)

    def test_16_update_estado_pendiente_to_realizada(self):
        """Actualizar estado pendiente→realizada →200, luego realizada→vencida debe 409."""
        _clean_fase2()
        created = service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "pendiente"})
        self.assertIsInstance(created, dict)
        lid = created["id"]
        updated = service.update_limpieza_estado(_token_panol(), lid, {"estado": "realizada"})
        self.assertIsInstance(updated, dict, msg=f"update fail {updated}")
        self.assertEqual(updated["estado"], "realizada")
        # Intentar cambiar desde realizada a vencida →409
        res2 = service.update_limpieza_estado(_token_panol(), lid, {"estado": "vencida"})
        self.assertIsInstance(res2, tuple)
        self.assertEqual(res2[1], 409)

    def test_17_update_observaciones_sin_cambio_estado(self):
        """Actualizar solo observaciones debe funcionar."""
        _clean_fase2()
        created = service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "pendiente", "observaciones": "orig"})
        lid = created["id"]
        updated = service.update_limpieza_estado(_token_panol(), lid, {"observaciones": "nueva obs"})
        self.assertIsInstance(updated, dict)
        self.assertEqual(updated["observaciones"], "nueva obs")
        self.assertEqual(updated["estado"], "pendiente")

    def test_18_delete_pendiente_ok(self):
        """Eliminar pendiente →200, eliminar no existente →404."""
        _clean_fase2()
        created = service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "pendiente"})
        lid = created["id"]
        deleted = service.delete_limpieza(_token_panol(), lid)
        self.assertIsInstance(deleted, dict)
        self.assertTrue(deleted["eliminado"])
        # Verificar que ya no existe
        not_found = service.delete_limpieza(_token_panol(), lid)
        self.assertIsInstance(not_found, tuple)
        self.assertEqual(not_found[1], 404)

    def test_19_delete_realizada_409(self):
        """Eliminar realizada →409."""
        _clean_fase2()
        created = service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "pendiente"})
        lid = created["id"]
        # Pasar a realizada
        service.update_limpieza_estado(_token_panol(), lid, {"estado": "realizada"})
        result = service.delete_limpieza(_token_panol(), lid)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)
        self.assertIn("pendiente", result[0].lower())

    def test_20_filter_caja_id_and_tecnico(self):
        """Filtrar por caja_id y tecnico_id."""
        _clean_fase2()
        caja2 = _ensure_caja("FASE2CAJA_LIMPIEZA")
        # Crear eventos en diferentes cajas
        service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id})
        service.create_limpieza(_token_panol(), {"caja_id": caja2["id"], "tecnico_id": self.tecnico_id})
        res_caja = service.get_limpieza_list(_token_supervisor(), {"caja_id": self.caja["id"]})
        for item in res_caja["items"]:
            self.assertEqual(item["caja_id"], self.caja["id"])
        res_tec = service.get_limpieza_list(_token_supervisor(), {"tecnico_id": self.tecnico_id})
        self.assertGreaterEqual(res_tec["total"], 2)

    def test_21_store_listar_limpieza_direct(self):
        """Store directo: listar_limpieza con JOIN."""
        _clean_fase2()
        service.create_limpieza(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico_id, "estado": "pendiente"})
        result = store.listar_limpieza(caja_id=self.caja["id"], limit=10, offset=0)
        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result["total"], 1)
        self.assertIsNotNone(result["items"][0].get("caja_codigo"))
        self.assertIsNotNone(result["items"][0].get("tecnico_nombre"))

    @classmethod
    def tearDownClass(cls):
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
                # No asignaciones here, but clean just in case
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
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


class TestAsignacionesCRUD(unittest.TestCase):
    """CRUD asignaciones con transacción singleton."""

    @classmethod
    def setUpClass(cls):
        cls.caja = _ensure_caja("FASE2CAJA001")
        cls.caja2 = _ensure_caja("FASE2CAJA_ASIG")
        personal = _get_personal_tecnico_ids(4)
        cls.personal = personal
        cls.tecnico1 = personal[0]["id"] if len(personal) > 0 else 1
        cls.tecnico2 = personal[1]["id"] if len(personal) > 1 else cls.tecnico1
        cls.tecnico3 = personal[2]["id"] if len(personal) > 2 else cls.tecnico1
        _clean_fase2()

    def setUp(self):
        # Asegurar cajas existen
        try:
            _ensure_caja("FASE2CAJA001")
            _ensure_caja("FASE2CAJA_ASIG")
        except Exception:
            pass

    def test_30_create_asignacion_valid_201(self):
        """Crear asignación válida →201."""
        _clean_fase2()
        result = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        self.assertIsInstance(result, dict, msg=f"create asignacion fail {result}")
        self.assertIn("id", result)
        self.assertEqual(result["caja_id"], self.caja["id"])
        self.assertEqual(result["tecnico_id"], self.tecnico1)
        self.assertEqual(result["desde"], "2026-09-01")
        self.assertTrue(result["activa"])
        self.assertIsNone(result["hasta"])
        self.assertIsNotNone(result.get("caja_codigo"))
        self.assertIsNotNone(result.get("tecnico_nombre"))

    def test_31_second_assign_same_caja_different_tecnico_closes_previous(self):
        """Segunda asignación misma caja diferente técnico cierra previa (activa invariant)."""
        _clean_fase2()
        r1 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        self.assertIsInstance(r1, dict)
        id1 = r1["id"]
        # Segunda con diferente técnico
        r2 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico2, "desde": "2026-09-02"})
        self.assertIsInstance(r2, dict, msg=f"second assign fail {r2}")
        id2 = r2["id"]
        self.assertNotEqual(id1, id2)
        # Verificar en DB que solo una activa
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) c FROM cajas_asignaciones WHERE caja_id=%s AND activa=1", (self.caja["id"],))
                count_active = cur.fetchone()["c"]
                cur.execute("SELECT id, activa, hasta FROM cajas_asignaciones WHERE id IN (%s,%s) ORDER BY id", (id1, id2))
                rows = cur.fetchall()
        finally:
            try:
                if conn.open:
                    conn.close()
            except Exception:
                pass
        self.assertEqual(count_active, 1)
        d = {r["id"]: r for r in rows}
        self.assertEqual(d[id1]["activa"], 0)
        self.assertIsNotNone(d[id1]["hasta"])
        self.assertEqual(d[id2]["activa"], 1)
        self.assertIsNone(d[id2]["hasta"])
        # List active filter debe retornar solo id2
        active_list = service.get_asignaciones_list(_token_supervisor(), {"caja_id": self.caja["id"], "activa": 1})
        self.assertEqual(active_list["total"], 1)
        self.assertEqual(active_list["items"][0]["id"], id2)

    def test_32_list_active_filter(self):
        """Listar asignaciones filtrando por activa."""
        _clean_fase2()
        r1 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        # Cerrar
        service.cerrar_asignacion(_token_panol(), r1["id"])
        r2 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico2, "desde": "2026-09-02"})
        self.assertTrue(r2["activa"])
        # Filtrar activa=1 → solo r2
        res_active = service.get_asignaciones_list(_token_supervisor(), {"activa": 1, "caja_id": self.caja["id"]})
        self.assertEqual(res_active["total"], 1)
        self.assertEqual(res_active["items"][0]["id"], r2["id"])
        # Filtrar activa=0 → solo r1
        res_inactive = service.get_asignaciones_list(_token_supervisor(), {"activa": 0, "caja_id": self.caja["id"]})
        self.assertEqual(res_inactive["total"], 1)
        self.assertEqual(res_inactive["items"][0]["id"], r1["id"])

    def test_33_cerrar_endpoint_ok(self):
        """Cerrar asignación activa → activa=0, hasta=CURDATE()."""
        _clean_fase2()
        created = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        aid = created["id"]
        closed = service.cerrar_asignacion(_token_panol(), aid)
        self.assertIsInstance(closed, dict, msg=f"cerrar fail {closed}")
        self.assertFalse(closed["activa"])
        self.assertIsNotNone(closed["hasta"])
        # Verificar que no queda activa para esa caja
        active = service.get_asignaciones_list(_token_supervisor(), {"caja_id": self.caja["id"], "activa": 1})
        self.assertEqual(active["total"], 0)

    def test_34_cerrar_already_closed_409(self):
        """Cerrar ya cerrada →409."""
        _clean_fase2()
        created = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        aid = created["id"]
        service.cerrar_asignacion(_token_panol(), aid)
        result = service.cerrar_asignacion(_token_panol(), aid)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 409)

    def test_35_duplicate_same_tecnico_409(self):
        """Duplicar asignación misma caja y mismo técnico activa →409."""
        _clean_fase2()
        r1 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        self.assertIsInstance(r1, dict)
        r2 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-02"})
        self.assertIsInstance(r2, tuple, msg=f"expected 409 duplicate, got {r2}")
        self.assertEqual(r2[1], 409)
        self.assertIn("ya hay una asignación activa", r2[0].lower())

    def test_36_invalid_missing_desde_400(self):
        """Falta desde →400."""
        result = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1})
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)
        result2 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "invalid-date"})
        self.assertIsInstance(result2, tuple)
        self.assertEqual(result2[1], 400)

    def test_37_invalid_fk_400(self):
        """FK caja/tecnico inexistente →400."""
        res1 = service.create_asignacion(_token_panol(), {"caja_id": 999999, "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        self.assertIsInstance(res1, tuple)
        self.assertEqual(res1[1], 400)
        res2 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": 999999, "desde": "2026-09-01"})
        self.assertIsInstance(res2, tuple)
        self.assertEqual(res2[1], 400)

    def test_38_pagination_and_filters(self):
        """Listar asignaciones paginación y filtros caja_id/tecnico_id."""
        _clean_fase2()
        # Crear asignaciones en dos cajas diferentes para poder listar
        r1 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        # cerrar para liberar caja
        service.cerrar_asignacion(_token_panol(), r1["id"])
        r2 = service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico2, "desde": "2026-09-03"})
        r3 = service.create_asignacion(_token_panol(), {"caja_id": self.caja2["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-02"})
        # Paginación
        all_res = service.get_asignaciones_list(_token_supervisor(), {"limit": 2, "offset": 0})
        self.assertGreaterEqual(all_res["total"], 3)
        self.assertEqual(len(all_res["items"]), 2)
        page2 = service.get_asignaciones_list(_token_supervisor(), {"limit": 2, "offset": 2})
        self.assertEqual(len(page2["items"]), all_res["total"] - 2)
        # Filtro caja_id
        filt_caja = service.get_asignaciones_list(_token_supervisor(), {"caja_id": self.caja["id"]})
        for item in filt_caja["items"]:
            self.assertEqual(item["caja_id"], self.caja["id"])
        # Filtro tecnico_id
        filt_tec = service.get_asignaciones_list(_token_supervisor(), {"tecnico_id": self.tecnico1})
        for item in filt_tec["items"]:
            self.assertEqual(item["tecnico_id"], self.tecnico1)

    def test_39_store_listar_asignaciones_direct(self):
        """Store directo: listar_asignaciones con filtros."""
        _clean_fase2()
        service.create_asignacion(_token_panol(), {"caja_id": self.caja["id"], "tecnico_id": self.tecnico1, "desde": "2026-09-01"})
        result = store.listar_asignaciones(caja_id=self.caja["id"], limit=10, offset=0)
        self.assertGreaterEqual(result["total"], 1)
        self.assertIsNotNone(result["items"][0].get("caja_codigo"))

    def test_40_not_found_404(self):
        """Cerrar/eliminar inexistente →404."""
        result = service.cerrar_asignacion(_token_panol(), 999999)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 404)
        # get por id inexistente via store helper service
        result2 = service.get_asignacion_by_id(_token_supervisor(), 999999)
        self.assertIsInstance(result2, tuple)
        self.assertEqual(result2[1], 404)

    @classmethod
    def tearDownClass(cls):
        # Solo limpiar asignaciones/limpieza parcial; las cajas se mantienen para las otras clases (orden alfabético)
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
                cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
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


def tearDownModule():
    """Limpieza final del módulo — asegura que no queden residuos FASE2 que bloqueen otros suites (FK RESTRICT)."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cajas_asignaciones WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
            cur.execute("DELETE FROM cajas_limpieza_historial WHERE caja_id IN (SELECT id FROM cajas_cajas WHERE codigo LIKE 'FASE2%%')")
            # Limpiar ideal creado por permisos tests
            cur.execute("DELETE FROM cajas_caja_ideal_detalle WHERE caja_ideal_id IN (SELECT id FROM cajas_caja_ideal WHERE nombre LIKE 'Ideal Permiso%%')")
            cur.execute("DELETE FROM cajas_caja_ideal WHERE nombre LIKE 'Ideal Permiso%%'")
            cur.execute("DELETE FROM cajas_herramientas WHERE codigo LIKE 'FASE2%%'")
            cur.execute("DELETE FROM cajas_cajas WHERE codigo LIKE 'FASE2%%'")
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


if __name__ == "__main__":
    unittest.main()
