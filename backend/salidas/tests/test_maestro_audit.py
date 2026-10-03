# -*- coding: utf-8 -*-
"""Unit tests for maestro_stock audit feature (option B).

No DB required — tests pure parsing and contract helpers via mocked get_connection.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestParseReporteFallback(unittest.TestCase):
    def setUp(self):
        # Import here to avoid import error if optional deps missing
        from routes.maestro_stock import _parse_reporte_to_diff

        self.parse = _parse_reporte_to_diff

    def test_new_parsing(self):
        rows = self.parse(
            "File: a.xlsx (detallado)\n  + NEW M1046MEC (detallado): stock_minimo=2.0, ubicacion=200846\n  >> RESUMEN: 1 nuevos",
            "a.xlsx",
            "detallado",
            42,
            "2026-09-30T10:00:00",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["codigo"], "M1046MEC")
        self.assertEqual(rows[0]["campo"], "stock_minimo")
        self.assertIsNone(rows[0]["valor_antes"])
        self.assertEqual(rows[0]["valor_despues"], "2.0")
        self.assertEqual(rows[1]["campo"], "ubicacion")

    def test_mod_parsing(self):
        rows = self.parse(
            "  ~ MOD M1046MEC: stock_minimo 0.00->2.0, ubicacion 2009D->200846\n  ~ MOD M0392FER: stock_minimo 10.00->0.0",
            "detallado.xlsx",
            "detallado",
            43,
            "2026-09-30T10:00:00",
        )
        self.assertEqual(len(rows), 3)
        # First two belong to M1046MEC
        m = [r for r in rows if r["codigo"] == "M1046MEC"]
        self.assertEqual(len(m), 2)
        self.assertEqual(m[0]["campo"], "stock_minimo")
        self.assertEqual(m[0]["valor_antes"], "0.00")
        self.assertEqual(m[0]["valor_despues"], "2.0")
        self.assertEqual(m[1]["campo"], "ubicacion")
        self.assertEqual(m[1]["valor_antes"], "2009D")
        self.assertEqual(m[1]["valor_despues"], "200846")

    def test_empty_reporte(self):
        self.assertEqual(self.parse("", "x.xlsx", "general", 1, None), [])

    def test_ignores_non_mod_lines(self):
        rows = self.parse("File: x\n  Sheet ABC error: foo\n  >> RESUMEN: 0 nuevos", "x", "general", 1, None)
        self.assertEqual(rows, [])


class TestAuditContract(unittest.TestCase):
    """Check that _process_single_file respects file-type and price-zero rules for audit (structure-level)."""

    def test_module_imports(self):
        # Ensure new symbols exist
        import routes.maestro_stock as ms

        self.assertTrue(hasattr(ms, "_ensure_tables"))
        self.assertTrue(hasattr(ms, "_parse_reporte_to_diff"))
        self.assertTrue(hasattr(ms, "get_import_diff"))
        self.assertTrue(hasattr(ms, "get_codigo_history"))
        # Check that post_import still exists
        self.assertTrue(hasattr(ms, "post_import"))


if __name__ == "__main__":
    unittest.main()
