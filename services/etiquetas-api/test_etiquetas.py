# -*- coding: utf-8 -*-
"""
Tests del servicio etiquetas-api (stdlib unittest + FastAPI TestClient).

Cada test corre contra una base SQLite temporal y aislada, así no se pisa con la
cola real ni entre tests. Para /catalogo se reemplaza la lectura de Firestore por
una función falsa (no se necesita red ni credenciales).

Ejecutar:  .venv\\Scripts\\python.exe -m unittest -v
"""

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import cola_repo
import main


class BaseTest(unittest.TestCase):
    def setUp(self) -> None:
        # Base temporal por test (aislada).
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        cola_repo.DB_PATH = self._tmp.name
        cola_repo.init_db()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass


class TestHealth(BaseTest):
    def test_health_ok(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["estado"], "ok")


PEDIDO_SIMPLE = {
    "tipo": "simple",
    "texto_libre": "ESTANTE EN MANTENIMIENTO",
    "cantidad": 1,
    "solicitado_por": "tablet-panol",
}

PEDIDO_CODIGO = {
    "tipo": "codigo",
    "codigo": "A-10543",
    "descripcion": "RODAMIENTO RIGIDO DE BOLAS 6204 2RS",
    "ubicacion": "10065C",
    "qr_data": "A-10543",
    "cantidad": 2,
    "solicitado_por": "tablet-panol",
}


class TestCrearEtiqueta(BaseTest):
    def test_crear_simple_ok(self) -> None:
        r = self.client.post("/etiquetas", json=PEDIDO_SIMPLE)
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertIsInstance(body["id"], int)
        self.assertEqual(body["estado"], "pendiente")

    def test_crear_codigo_ok(self) -> None:
        r = self.client.post("/etiquetas", json=PEDIDO_CODIGO)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["estado"], "pendiente")

    def test_simple_sin_texto_libre_rechaza(self) -> None:
        r = self.client.post("/etiquetas", json={"tipo": "simple"})
        self.assertEqual(r.status_code, 422)

    def test_codigo_sin_campos_rechaza(self) -> None:
        r = self.client.post("/etiquetas", json={"tipo": "codigo", "codigo": "X1"})
        self.assertEqual(r.status_code, 422)

    def test_tipo_invalido_rechaza(self) -> None:
        r = self.client.post("/etiquetas", json={"tipo": "otro", "texto_libre": "x"})
        self.assertEqual(r.status_code, 422)

    def test_cantidad_invalida_rechaza(self) -> None:
        payload = dict(PEDIDO_SIMPLE, cantidad=0)
        r = self.client.post("/etiquetas", json=payload)
        self.assertEqual(r.status_code, 422)


class TestListarPendientes(BaseTest):
    def test_lista_vacia_al_inicio(self) -> None:
        r = self.client.get("/etiquetas/pendientes")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_lista_devuelve_creados_en_orden_fifo(self) -> None:
        id1 = self.client.post("/etiquetas", json=PEDIDO_SIMPLE).json()["id"]
        id2 = self.client.post("/etiquetas", json=PEDIDO_CODIGO).json()["id"]
        r = self.client.get("/etiquetas/pendientes")
        self.assertEqual(r.status_code, 200)
        ids = [p["id"] for p in r.json()]
        self.assertEqual(ids, [id1, id2])
        # El de tipo 'simple' no arrastra campos de código.
        primero = r.json()[0]
        self.assertEqual(primero["tipo"], "simple")
        self.assertIsNone(primero["codigo"])
        self.assertEqual(primero["intentos"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
