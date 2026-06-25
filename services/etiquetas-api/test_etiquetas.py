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


if __name__ == "__main__":
    unittest.main(verbosity=2)
