# -*- coding: utf-8 -*-
"""Script de seed idempotente para el módulo Personal.

Puebla las tablas areas y personal en MariaDB (puerto :8019).
- 5 áreas por defecto
- 3 genéricos (MANTTO., PAÑOL, PRODUCCION)
- 31 personas reales desde master_codes.xlsx (o fallback demo)

Uso:
    python seed_personal.py
    PERSONAL_DB_ENABLED=1 python seed_personal.py  # Fuerza población completa
    PERSONAL_DB_ENABLED=0 python seed_personal.py  # Solo log, sin DB
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Añadir el directorio personal al path para imports relativos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "personal"))

import db

# Áreas por defecto
AREAS_POR_DEFECTO = [
    "Mantenimiento",
    "Edilicio",
    "Autoelevadores",
    "Proyectos",
    "Produccion",
]

# Genericos: MANTTO. → Mantenimiento
AREA_ALIAS = {
    "MANTTO.": "Mantenimiento",
    "MANTTO": "Mantenimiento",
    "MANTTO -": "Mantenimiento",
}

# 31 personas de referencia (placeholder cuando no se encuentra master_codes.xlsx)
PERSONAS_FALLBACK = [
    ("GARCIA, JUAN", "tecnico", "MANTTO."),
    ("LOPEZ, MARIA", "supervisor", "EDILICIO"),
    ("MARTINEZ, CARLOS", "tecnico", "AUTOELEVADORES"),
    ("RODRIGUEZ, ANA", "produccion", "PROYECTOS"),
    ("FERNANDEZ, PABLO", "tecnico", "MANTENIMIENTO"),
    ("GOMEZ, LUCIA", "supervisor", "EDILICIO"),
    ("PEREZ, DIEGO", "produccion", "PROYECTOS"),
    ("SANTOS, VALENTINA", "tecnico", "AUTOELEVADORES"),
    ("TORRES, MIGUEL", "generico", None),
    ("MOLINA, ROMINA", "tecnico", "MANTENIMIENTO"),
    ("VARGAS, HORACIO", "supervisor", "EDILICIO"),
    ("CASTRO, FERNANDO", "produccion", "PROYECTOS"),
    ("RUIZ, CAMILA", "tecnico", "AUTOELEVADORES"),
    ("DIAZ, SEBASTIAN", "generico", None),
    ("MUÑOZ, GABRIELA", "tecnico", "MANTENIMIENTO"),
    ("CORDOVA, ANDRES", "supervisor", "EDILICIO"),
    ("PRIETO, ISABEL", "produccion", "PROYECTOS"),
    ("ORTEGA, TOMAS", "tecnico", "AUTOELEVADORES"),
    ("QUIROGA, NADIA", "generico", "PRODUCCION"),
    ("LUNA, JAVIER", "tecnico", "MANTENIMIENTO"),
    ("SILVA, FLORENCIA", "supervisor", "EDILICIO"),
    ("MORA, ERNESTO", "produccion", "PROYECTOS"),
    ("AGUILAR, MILAGROS", "tecnico", "AUTOELEVADORES"),
    ("ESCOBAR, RICARDO", "generico", "PRODUCCION"),
    ("PONCE, VALENTINA", "tecnico", "MANTENIMIENTO"),
    ("ACOSTA, MATIAS", "supervisor", "EDILICIO"),
    ("MEDINA, SOFIA", "produccion", "PROYECTOS"),
    ("BRITO, FELIPE", "tecnico", "AUTOELEVADORES"),
    ("ZAMORA, ADRIANA", "generico", None),
    ("NARVAEZ, CRISTIAN", "tecnico", "MANTENIMIENTO"),
    ("JIMENEZ, YANINA", "supervisor", "EDILICIO"),
]

_TIPOS_VALIDOS = {"tecnico", "supervisor", "produccion", "generico", "panol"}


def _obtener_db() -> bool:
    """Retorna True si PERSONAL_DB_ENABLED=1."""
    flag = os.environ.get("PERSONAL_DB_ENABLED", "0").strip()
    return flag not in ("0", "false", "False", "no")


def _maestro_path() -> Path:
    """Busca master_codes.xlsx en ubicaciones conocidas."""
    candidates = [
        Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\master_codes.xlsx"),
        Path(r"C:\Users\Pañol\Desktop\sistemas_panol\Server\AppWebSalidas\backend\salidas\data_prueba\base_datos.xlsx"),
        Path(r"C:\Users\Pañol\Desktop\sistemas_panol\Server\AppWebSalidas\backend\salidas\data_prueba\master_codes.xlsx"),
        Path(r"C:\Users\Pañol\Desktop\sistemas_panol\master_codes.xlsx"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _cargar_personas_desde_maestro() -> list[tuple[str, str, str | None]]:
    """Intenta cargar personas desde master_codes.xlsx. Retorna lista de (nombre, tipo, area)."""
    path = _maestro_path()
    if not path:
        return []

    try:
        import pandas as pd
        df = pd.read_excel(path, sheet_name="ARTICULOS")
        # Procesar columnas relevantes si existen
        personas = []
        for _, row in df.iterrows():
            nombre = str(row.get("OPERARIO", ""))
            tipo = str(row.get("TIPO", "tecnico"))
            area = str(row.get("SECTOR", ""))
            if nombre and nombre.strip():
                personas.append((nombre.strip(), tipo.strip(), area.strip() or None))
        return personas if personas else []
    except Exception:
        return []


def seed_areas() -> None:
    """Inserta 5 áreas por defecto (idempotente)."""
    for nombre in AREAS_POR_DEFECTO:
        nombre_norm = nombre.strip().upper()
        db_conn = db.get_connection()
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO areas (nombre) VALUES (%s) ON DUPLICATE KEY UPDATE nombre = VALUES(nombre)",
                    (nombre_norm,),
                )
            db_conn.commit()
        finally:
            db_conn.close()


def seed_genericos() -> None:
    """Inserta 3 registros genéricos (idempotente)."""
    genericos = [
        ("MANTTO.", None, "generico"),
        ("PAÑOL", None, "generico"),
        ("PRODUCCION", None, "generico"),
    ]
    for nombre, _email, tipo in genericos:
        db_conn = db.get_connection()
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """INSERT IGNORE INTO personal (legajo, nombre, email, area_id, tipo, activo)
                       VALUES (NULL, %s, NULL, NULL, %s, 1)""",
                    (nombre.strip(), tipo),
                )
            db_conn.commit()
        finally:
            db_conn.close()


def seed_personas_real(personas: list[tuple[str, str, str | None]]) -> int:
    """Inserta/actualiza personas reales. Retorna cantidad procesada."""
    count = 0
    for nombre_raw, tipo, area_name in personas:
        if tipo not in _TIPOS_VALIDOS:
            tipo = "tecnico"

        nombre = nombre_raw.strip().upper()

        # Resolver area_id
        area_id = None
        if area_name:
            area_norm = area_name.strip().upper()
            alias = AREA_ALIAS.get(area_norm)
            target_name = alias if alias else area_norm
            db_conn = db.get_connection()
            try:
                with db_conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM areas WHERE UPPER(TRIM(nombre)) = %s AND activo = 1",
                        (target_name,),
                    )
                    row = cur.fetchone()
                if row:
                    area_id = row["id"]
                else:
                    print(f"  ADVERTENCIA: Área '{area_name}' no encontrada para '{nombre}'")
            finally:
                db_conn.close()

        db_conn = db.get_connection()
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO personal (legajo, nombre, email, area_id, tipo, activo)
                       VALUES (NULL, %s, NULL, %s, %s, 1)
                       ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), area_id = VALUES(area_id), tipo = VALUES(tipo)""",
                    (nombre, area_id, tipo),
                )
            db_conn.commit()
            count += 1
        except Exception as e:
            print(f"  ADVERTENCIA: No se pudo insertar '{nombre}': {e}")
        finally:
            db_conn.close()

    return count


def main() -> None:
    """Ejecuta el pipeline de seed completo (idempotente)."""
    if not _obtener_db():
        print("PERSONAL_DB_ENABLED=0, omitiendo seed de base de datos.")
        return

    print("=== Personal Seed Pipeline ===")
    print("Conectando a MariaDB...")

    db.init_db()

    # 1. Áreas
    print("\n[1/3] Sembrando áreas...")
    seed_areas()
    print("  ✓ 5 áreas sembradas")

    # 2. Genericos
    print("\n[2/3] Sembrando genéricos...")
    seed_genericos()
    print("  ✓ 3 genéricos sembrados")

    # 3. Personas reales
    print("\n[3/3] Cargando personal real...")
    personas = _cargar_personas_desde_maestro()
    if not personas:
        personas = PERSONAS_FALLBACK
        print("  Usando dataset de fallback (master_codes.xlsx no encontrado)")

    count = seed_personas_real(personas)
    print(f"  ✓ {count} personas procesadas")

    print("\n=== Seed completado exitosamente ===")


if __name__ == "__main__":
    main()
