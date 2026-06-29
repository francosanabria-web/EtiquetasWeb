# -*- coding: utf-8 -*-
"""Tests del servicio minutas-api."""

from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

# Base de datos aislada por test file
os.environ["MINUTAS_DB_PATH"] = tempfile.mktemp(suffix=".db")

import repo  # noqa: E402
from main import app  # noqa: E402


class MinutasApiTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.path.exists(repo.DB_PATH):
            os.remove(repo.DB_PATH)
        repo.init_db()
        self.client = TestClient(app)

    def test_flujo_reunion_completo(self) -> None:
        r = self.client.post("/sesiones/iniciar", json={"responsable": "Jefe Pañol"})
        self.assertEqual(r.status_code, 200)
        sesion = r.json()
        sid = sesion["id"]

        r = self.client.post(
            f"/sesiones/{sid}/solicitudes",
            json={
                "numero_referencia": "PED-2026-001",
                "solicitante": "Mantenimiento A",
                "urgencia": "alta",
                "cantidad_items": 10,
                "descripcion": "Repuestos bomba",
            },
        )
        self.assertEqual(r.status_code, 200)
        sol_id = r.json()["id"]

        r = self.client.post(
            f"/sesiones/{sid}/solicitudes/{sol_id}/entregas",
            json={"fecha": "2026-06-26", "cantidad": 4, "observacion": "Primera tanda"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["estado_entrega"], "parcial")

        r = self.client.post(
            f"/sesiones/{sid}/solicitudes/{sol_id}/actualizaciones",
            json={"texto": "Compras confirmó fecha estimada viernes.", "autor": "Pañolero"},
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.post(
            f"/sesiones/{sid}/temas",
            json={"titulo": "Proveedor alternativo", "descripcion": "Evaluar segundo proveedor"},
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.get(f"/sesiones/{sid}/preview-email")
        self.assertEqual(r.status_code, 200)
        self.assertIn("PED-2026-001", r.json()["cuerpo_texto"])

        r = self.client.get("/sesiones/actual")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json())
        self.assertEqual(len(r.json()["solicitudes"]), 1)

    def test_referencia_duplicada_rechazada(self) -> None:
        r = self.client.post("/sesiones/iniciar", json={})
        sid = r.json()["id"]
        payload = {
            "numero_referencia": "PED-DUP",
            "solicitante": "A",
            "urgencia": "media",
            "cantidad_items": 1,
        }
        self.assertEqual(self.client.post(f"/sesiones/{sid}/solicitudes", json=payload).status_code, 200)
        r2 = self.client.post(f"/sesiones/{sid}/solicitudes", json=payload)
        self.assertEqual(r2.status_code, 400)

    def test_entrega_supera_cantidad(self) -> None:
        r = self.client.post("/sesiones/iniciar", json={})
        sid = r.json()["id"]
        r = self.client.post(
            f"/sesiones/{sid}/solicitudes",
            json={
                "numero_referencia": "PED-X",
                "solicitante": "B",
                "urgencia": "baja",
                "cantidad_items": 2,
            },
        )
        sol_id = r.json()["id"]
        r = self.client.post(
            f"/sesiones/{sid}/solicitudes/{sol_id}/entregas",
            json={"fecha": "2026-06-26", "cantidad": 5},
        )
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
