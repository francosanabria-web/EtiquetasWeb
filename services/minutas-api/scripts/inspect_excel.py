# -*- coding: utf-8 -*-
"""Inspección puntual del Excel de solicitudes (solo desarrollo)."""
import sys
from pathlib import Path

import openpyxl

path = Path(__file__).resolve().parents[3] / "docs" / "ejemplos"
candidates = list(path.glob("*.xlsx"))
if not candidates:
    print("No xlsx in", path)
    sys.exit(1)
path = candidates[0]
print("Using:", path)
wb = openpyxl.load_workbook(path, data_only=False)
print("Sheets:", wb.sheetnames)
ws = wb[wb.sheetnames[0]]
print("Sheet:", ws.title, "rows", ws.max_row, "cols", ws.max_column)

COLS = "ABCDEFGHIJKLMNOPQRSTUVWX"
for r in range(1, 4):
    vals = {c: ws[f"{c}{r}"].value for c in "ABCDEFGHIJKLMNOPQRSTUVWX"}
    print(f"Row {r}:", {k: vals[k] for k in vals if vals[k] is not None})

def rgb(cell):
    fill = cell.fill
    if not fill or fill.fill_type != "solid":
        return None
    c = fill.fgColor
    if c.type == "rgb" and c.rgb:
        return c.rgb
    if c.type == "theme":
        return f"theme:{c.theme}"
    return str(c.value)

print("\nSample data rows (W/X states and colors):")
for r in range(2, min(ws.max_row + 1, 40)):
    x_val = ws[f"X{r}"].value
    w_val = ws[f"W{r}"].value
    if not x_val and not w_val and not ws[f"B{r}"].value:
        continue
    h, j = ws[f"H{r}"].value, ws[f"J{r}"].value
    print(
        f"R{r} A={ws[f'A{r}'].value} B={ws[f'B{r}'].value} C={ws[f'C{r}'].value} "
        f"H={h} J={j} W={w_val}({rgb(ws[f'W{r}'])}) X={x_val}({rgb(ws[f'X{r}'])})"
    )

# unique W/X and row fill on X
wx = set()
row_colors = set()
for r in range(2, ws.max_row + 1):
    if ws[f"X{r}"].value:
        wx.add((str(ws[f"W{r}"].value).strip(), str(ws[f"X{r}"].value).strip()))
    rc = rgb(ws[f"X{r}"])
    if rc:
        row_colors.add(rc)
print("\nRows with Con pendientes (first 15):")
n = 0
for r in range(2, ws.max_row + 1):
    x_val = str(ws[f"X{r}"].value or "").strip()
    if "pendiente" not in x_val.lower():
        continue
    w_val = ws[f"W{r}"].value
    fills = {c: rgb(ws[f"{c}{r}"]) for c in "ABCDEXW"}
    print(f"R{r} J={ws[f'J{r}'].value} W={w_val} X={x_val} fills={fills}")
    n += 1
    if n >= 15:
        break

# scan all unique row background from column A
from collections import Counter
counters = Counter()
for r in range(2, min(ws.max_row + 1, 500)):
    for c in "ABCDEFGHIJKLMNOPQRSTUVWX":
        rc = rgb(ws[f"{c}{r}"])
        if rc:
            counters[rc] += 1
print("\nTop fill colors (first 500 rows):", counters.most_common(10))
