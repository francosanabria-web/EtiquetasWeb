# -*- coding: utf-8 -*-
import os
import unittest
from pathlib import Path

from excel_parser import es_fila_elegible, parsear_excel, resumen_importacion


class ExcelParserTests(unittest.TestCase):
    def test_elegibilidad_reglas(self):
        self.assertFalse(es_fila_elegible("Anulado", "Con pendientes"))
        self.assertTrue(es_fila_elegible("Recibido", "Con pendientes"))
        self.assertFalse(es_fila_elegible("Recibido", "cumplida"))

    def test_orden_fecha_solicitud(self):
        from excel_parser import parse_fecha_orden

        self.assertLess(parse_fecha_orden("1/1/2025"), parse_fecha_orden("15/3/2025"))
        self.assertLess(parse_fecha_orden("15/3/2025"), parse_fecha_orden(""))

    def test_parsea_archivo_ejemplo(self):
        base = Path(__file__).resolve().parents[2] / "docs" / "ejemplos"
        preferido = base / "solicitudes_compras_ejemplo.xlsx"
        files = [preferido] if preferido.is_file() else list(base.glob("*.xlsx"))
        if not files:
            self.skipTest("Sin archivo de ejemplo en docs/ejemplos")
        with open(files[0], "rb") as f:
            hoja, filas = parsear_excel(f.read())
        self.assertTrue(len(filas) > 100)
        res = resumen_importacion(filas)
        self.assertGreater(res["elegibles"], 0)
        self.assertGreater(res["pedidos_elegibles"], 0)


if __name__ == "__main__":
    unittest.main()
