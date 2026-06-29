# -*- coding: utf-8 -*-
"""Tests de caché en memoria del catálogo (sin Firestore)."""

import unittest

import firebase_lectura as fb


class TestCatalogoMemoria(unittest.TestCase):
    def setUp(self) -> None:
        self._indice_orig = dict(fb._indice)
        self._estado_orig = fb._estado

    def tearDown(self) -> None:
        fb._indice.clear()
        fb._indice.update(self._indice_orig)
        fb._estado = self._estado_orig

    def test_buscar_solo_memoria_sin_get(self) -> None:
        fb._indice["M2271MEC"] = {
            "codigo": "M2271MEC",
            "descripcion": "TORNILLO",
            "ubicacion": "20027C",
            "_doc_id": "M2271MEC",
        }
        fb._estado = "listo"
        item = fb.buscar_catalogo("m2271mec")
        self.assertIsNotNone(item)
        self.assertEqual(item["codigo"], "M2271MEC")

    def test_sincronizando_sin_datos_503(self) -> None:
        fb._indice.clear()
        fb._estado = "sincronizando"
        with self.assertRaises(fb.CatalogoSincronizando):
            fb.buscar_catalogo("X")


if __name__ == "__main__":
    unittest.main(verbosity=2)
