# -*- coding: utf-8 -*-
"""Script de migración para crear la tabla personal_mail_prefs en MariaDB.

Crea la tabla si no existe y precarga prefs para los personales existentes
(todos habilitados por defecto para ambos tipos).

Uso:
    python migrate_personal_mail_prefs.py
    python migrate_personal_mail_prefs.py --no-seed   # Solo crear tabla
    PERSONAL_DB_ENABLED=1 python migrate_personal_mail_prefs.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "personal"))

import pymysql
import db

TIPOS_MAIL = ["diario_gastos", "activos_fuera"]


def _get_conn():
    return pymysql.connect(
        host=db.DB_HOST,
        port=int(db.DB_PORT),
        user=db.DB_USER,
        password=db.DB_PASSWORD,
        database=db.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def create_table(conn) -> bool:
    """Crea la tabla personal_mail_prefs si no existe. Retorna True si se creó."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS `personal_mail_prefs` (
                `personal_id`   INT UNSIGNED NOT NULL COMMENT 'FK -> personal(id)',
                `mail_tipo`     VARCHAR(50) NOT NULL COMMENT 'Tipo de mail: diario_gastos, activos_fuera',
                `habilitado`    TINYINT(1)  NOT NULL DEFAULT 1 COMMENT '1=recibe mail, 0=no recibe',
                PRIMARY KEY (`personal_id`, `mail_tipo`),
                CONSTRAINT `fk_pmp_personal`
                    FOREIGN KEY (`personal_id`)
                    REFERENCES `personal`(`id`)
                    ON DELETE CASCADE,
                INDEX `idx_pmp_mail_tipo` (`mail_tipo`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='Preferencias de mail por personal'
        """)
        conn.commit()

    # Verificar si se creó (o ya existía)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (db.DB_NAME, "personal_mail_prefs"),
        )
        exists = cur.fetchone()["c"] > 0
    return exists


def seed_prefs(conn) -> int:
    """Precarga prefs para todos los personales activos. Retorna cantidad de filas insertadas/actualizadas."""
    count = 0
    with conn.cursor() as cur:
        for mail_tipo in TIPOS_MAIL:
            cur.execute(
                """INSERT INTO `personal_mail_prefs` (`personal_id`, `mail_tipo`, `habilitado`)
                   SELECT `id`, %s, 1 FROM `personal` WHERE `activo` = 1
                   ON DUPLICATE KEY UPDATE `habilitado` = VALUES(`habilitado`)""",
                (mail_tipo,),
            )
            count += cur.rowcount
        conn.commit()
    return count


def count_prefs(conn) -> dict[str, int]:
    """Retorna conteo de prefs por tipo."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT `mail_tipo`, COUNT(*) AS c FROM `personal_mail_prefs` GROUP BY `mail_tipo`"
        )
        rows = cur.fetchall()
    return {r["mail_tipo"]: r["c"] for r in rows}


def main() -> None:
    db.init_db()  # Asegura que las tablas base existan
    conn = _get_conn()
    try:
        table_exists = create_table(conn)
        if table_exists:
            print("[OK] Tabla personal_mail_prefs lista.")
        else:
            print("[ERROR] Error creando tabla personal_mail_prefs.")
            return

        # Precargar prefs
        count = seed_prefs(conn)
        print(f"[OK] Precargadas {count} filas de prefs (2 tipos x personales activos).")

        # Verificar
        summary = count_prefs(conn)
        for tipo, c in summary.items():
            print(f"  {tipo}: {c} registros")

        # Verificar que la tabla existe y tiene datos
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM `personal_mail_prefs`")
            total = cur.fetchone()["c"]
        print(f"\nTotal de filas en personal_mail_prefs: {total}")
        print("[DONE] Migracion completada")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
