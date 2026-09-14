# -*- coding: utf-8 -*-
"""Migrar minutas.db local -> share G: (Plan A shared SQLite).

- Detecta DB mas nueva entre local y share
- Copia al share con backup atomico
- Sincroniza sectores/*.json
- Idempotente: ejecutar varias veces no duplica ni rompe

Uso:
  python scripts/migrar_minuta_a_share.py
  # Desde PC de Panol (con datos actualizados) ejecutar mismo script para subir al share.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_MINUTA = PROJECT_ROOT / "backend" / "minuta_reunion"
LOCAL_DIR = BACKEND_MINUTA / "data"
SHARE_DIR = Path(r"G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\minuta_data")
LOCAL_DB = LOCAL_DIR / "minutas.db"
SHARE_DB = SHARE_DIR / "minutas.db"
LOCAL_SECTORES = LOCAL_DIR / "sectores"
SHARE_SECTORES = SHARE_DIR / "sectores"


def _fmt_size(p: Path) -> str:
    try:
        return f"{p.stat().st_size} bytes"
    except OSError:
        return "N/A"


def _fmt_mtime(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).isoformat(sep=" ", timespec="seconds")
    except OSError:
        return "N/A"


def _ensure_dirs() -> None:
    print(f"[INFO] LOCAL_DIR: {LOCAL_DIR} exists={LOCAL_DIR.is_dir()}")
    print(f"[INFO] SHARE_DIR: {SHARE_DIR} exists={SHARE_DIR.is_dir()}")
    try:
        SHARE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[OK] SHARE_DIR ensured: {SHARE_DIR}")
    except OSError as e:
        print(f"[ERROR] No se pudo crear SHARE_DIR {SHARE_DIR}: {e}")
        raise SystemExit(1)
    try:
        SHARE_SECTORES.mkdir(parents=True, exist_ok=True)
        print(f"[OK] SHARE_SECTORES ensured: {SHARE_SECTORES}")
    except OSError as e:
        print(f"[ERROR] No se pudo crear SHARE_SECTORES: {e}")
        raise SystemExit(1)
    # Local dirs should already exist but ensure
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_SECTORES.mkdir(parents=True, exist_ok=True)


def _backup_file(target: Path) -> Path | None:
    if not target.is_file():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = target.with_name(f"{target.name}.BAK_{stamp}")
    shutil.copy2(target, bak)
    print(f"[BACKUP] {target.name} -> {bak.name} ({_fmt_size(bak)}) mtime={_fmt_mtime(bak)}")
    # Also backup -wal/-shm if present (SQLite WAL)
    for suffix in ("-wal", "-shm"):
        wal = target.with_name(target.name + suffix)
        if wal.is_file() and wal.stat().st_size > 0:
            bak_wal = bak.with_name(bak.name + suffix)
            try:
                shutil.copy2(wal, bak_wal)
                print(f"[BACKUP] {wal.name} -> {bak_wal.name}")
            except OSError as e:
                print(f"[WARN] No se pudo backup {wal}: {e}")
    return bak


def _copy_db(src: Path, dst: Path) -> None:
    if not src.is_file():
        print(f"[SKIP] Source DB no existe: {src}")
        return
    if src.stat().st_size < 1024:
        print(f"[WARN] Source DB muy pequeña (<1KB): {src} size={_fmt_size(src)} - posible corrupta, abortando copia")
        return
    # Validate SQLite header before copy
    try:
        conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        cur = conn.execute("SELECT count(*) FROM sqlite_master;")
        cur.fetchone()
        conn.close()
        print(f"[CHECK] Source DB valid SQLite: {src}")
    except Exception as e:
        print(f"[WARN] Source DB no parece SQLite valido: {e} - se copia igual con advertencia")

    # Backup dst if exists
    if dst.is_file():
        _backup_file(dst)

    # Atomic copy via .tmp + replace
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    print(f"[COPY] {src} ({_fmt_size(src)} mtime={_fmt_mtime(src)}) -> {tmp}")
    shutil.copy2(src, tmp)
    # Ensure tmp is valid
    try:
        conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Temporal DB invalida tras copia: {e}")
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, dst)
    print(f"[OK] Atomico replace: {tmp.name} -> {dst.name} ({_fmt_size(dst)})")
    # Clean WAL/SHM from dst (force checkpoint by opening with WAL then closing?)
    for suffix in ("-wal", "-shm"):
        p = dst.with_name(dst.name + suffix)
        if p.is_file():
            try:
                p.unlink(missing_ok=True)
                print(f"[CLEAN] Removed leftover {p.name}")
            except OSError:
                pass


def _sync_sectores() -> None:
    # Copy sectores/*.json from local to share if missing or newer (idempotent)
    local_files = list(LOCAL_SECTORES.glob("*.json")) if LOCAL_SECTORES.is_dir() else []
    share_files = {p.name: p for p in SHARE_SECTORES.glob("*.json")} if SHARE_SECTORES.is_dir() else {}
    print(f"[INFO] Local sectores: {len(local_files)} files, Share sectores: {len(share_files)} files")
    copied = 0
    for lf in local_files:
        sf = SHARE_SECTORES / lf.name
        should_copy = False
        if not sf.is_file():
            should_copy = True
            reason = "no existe en share"
        else:
            # Compare mtime and size
            try:
                l_mtime = lf.stat().st_mtime
                s_mtime = sf.stat().st_mtime
                if l_mtime > s_mtime + 1.0:
                    should_copy = True
                    reason = f"local mas nuevo ({_fmt_mtime(lf)} > {_fmt_mtime(sf)})"
                elif lf.stat().st_size != sf.stat().st_size:
                    # Different size but not newer -> log and maybe copy if local larger?
                    # Idempotent: don't overwrite if share newer
                    reason = f"mismo mtime pero distinto size (local {_fmt_size(lf)} vs share {_fmt_size(sf)}) - skip"
                    should_copy = False
                    print(f"[SKIP] {lf.name}: {reason}")
                    continue
                else:
                    reason = "igual"
                    should_copy = False
            except OSError as e:
                print(f"[WARN] stat error {lf.name}: {e}")
                should_copy = False
        if should_copy:
            try:
                shutil.copy2(lf, sf)
                print(f"[COPY] sectores {lf.name} -> share ({reason})")
                copied += 1
            except OSError as e:
                print(f"[ERROR] No se pudo copiar {lf.name}: {e}")
        else:
            print(f"[SKIP] sectores {lf.name} ya sincronizado ({reason})")
    # Also report share-only files (present in share but not local) - keep them
    local_names = {p.name for p in local_files}
    share_only = [n for n in share_files if n not in local_names]
    if share_only:
        print(f"[INFO] Archivos solo en share (se conservan): {share_only}")
    print(f"[INFO] Sectores sincronizados: {copied} copiados")


def main() -> None:
    print("=" * 70)
    print(" Migrar minutas.db -> Share G: (Plan A)")
    print("=" * 70)
    _ensure_dirs()

    print(f"[INFO] LOCAL_DB: {LOCAL_DB} exists={LOCAL_DB.is_file()} size={_fmt_size(LOCAL_DB) if LOCAL_DB.is_file() else 'N/A'} mtime={_fmt_mtime(LOCAL_DB) if LOCAL_DB.is_file() else 'N/A'}")
    print(f"[INFO] SHARE_DB: {SHARE_DB} exists={SHARE_DB.is_file()} size={_fmt_size(SHARE_DB) if SHARE_DB.is_file() else 'N/A'} mtime={_fmt_mtime(SHARE_DB) if SHARE_DB.is_file() else 'N/A'}")

    # Decide action
    local_exists = LOCAL_DB.is_file()
    share_exists = SHARE_DB.is_file()

    if not local_exists and not share_exists:
        print("[ERROR] Ni local ni share tienen DB. Nada que migrar. Inicialice la app para crear DB vacia.")
        raise SystemExit(1)

    if not share_exists and local_exists:
        print("[ACTION] Share vacio -> copiar LOCAL como base inicial")
        _copy_db(LOCAL_DB, SHARE_DB)
        _sync_sectores()
        print("[DONE] Share inicializado desde local.")
        _print_next_steps()
        return

    if share_exists and not local_exists:
        print("[INFO] Local no tiene DB pero share si. No se sobrescribe share. Opcional: copiar share->local para backup local")
        # Optionally copy share to local as backup (idempotent)
        # Do not auto-copy to avoid confusion, just inform
        print(f"[INFO] Share DB es fuente de verdad: {SHARE_DB} ({_fmt_size(SHARE_DB)})")
        _print_next_steps()
        return

    # Both exist -> compare mtimes
    try:
        l_mtime = LOCAL_DB.stat().st_mtime
        s_mtime = SHARE_DB.stat().st_mtime
    except OSError as e:
        print(f"[ERROR] stat fallo: {e}")
        raise SystemExit(1)

    print(f"[INFO] Local mtime: {_fmt_mtime(LOCAL_DB)} ({l_mtime:.0f})")
    print(f"[INFO] Share mtime: {_fmt_mtime(SHARE_DB)} ({s_mtime:.0f})")
    diff = l_mtime - s_mtime
    print(f"[INFO] Diferencia (local - share): {diff:.1f}s")

    if abs(diff) < 1.0:
        print("[SKIP] Ambas DB tienen mtime similar (dentro 1s). Se asumen sincronizadas. Verificando sectores...")
        # Still sync sectores
        _sync_sectores()
        # Verify share is readable
        try:
            conn = sqlite3.connect(f"file:{SHARE_DB}?mode=ro", uri=True)
            cur = conn.execute("SELECT count(*) FROM pedidos;")
            print(f"[CHECK] Share DB pedidos count: {cur.fetchone()[0]}")
            cur = conn.execute("SELECT count(*) FROM reuniones;")
            print(f"[CHECK] Share DB reuniones count: {cur.fetchone()[0]}")
            conn.close()
        except Exception as e:
            print(f"[WARN] No se pudo contar filas en share: {e}")
        _print_next_steps()
        return

    if l_mtime > s_mtime:
        print("[ACTION] Local mas nueva -> backup share y copiar local -> share")
        _copy_db(LOCAL_DB, SHARE_DB)
        _sync_sectores()
        print("[DONE] Local -> Share completado.")
    else:
        print("[ACTION] Share mas nueva -> NO sobrescribir share (share es fuente de verdad)")
        print("         Si desea forzar local->share, borre share o use --force (no implementado, hacerlo manual)")
        # Still sync sectores local->share only if local newer files
        _sync_sectores()
        # Optionally copy share->local for consistency? But spec says detectar mas nueva y copiar al share, so if share newer, no action
        print("[INFO] Se conserva share. Si local esta desactualizado, proxima ejecucion desde PC con datos nuevos actualizara share.")
        # Offer to sync share->local as backup
        try:
            backup_local = LOCAL_DB.with_name(f"minutas.db.BAK_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            if LOCAL_DB.is_file():
                shutil.copy2(LOCAL_DB, backup_local)
                print(f"[BACKUP] Local backup: {backup_local.name}")
            # Do not auto-overwrite local; user decision
            print(f"[INFO] Para sincronizar local con share, copie manualmente: {SHARE_DB} -> {LOCAL_DB}")
        except Exception as e:
            print(f"[WARN] Backup local fallo: {e}")

    _print_next_steps()


def _print_next_steps() -> None:
    print("\n" + "=" * 70)
    print(" Pasos para PC de Pañol (datos actualizados)")
    print("=" * 70)
    print("1. En la PC de Pañol (que tiene la DB mas reciente), ejecutar:")
    print(r"     python C:\Users\Pañol\Desktop\sistemas_panol\Server\AppWebSalidas\scripts\migrar_minuta_a_share.py")
    print("   Esto detectara su DB local mas nueva y la subira al share (con backup).")
    print("")
    print("2. En el Server, verificar que minuta_reunion usa share:")
    print(r"     set MINUTA_DATA_DIR=G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\minuta_data")
    print(r"     python -c ""import db; print(db.DATA_DIR, db.DB_PATH); db.init_db(); print(db.listar_sectores())""")
    print("")
    print("3. Reiniciar servicio Minuta (scripts/_internal/_start_minuta.bat ya setea MINUTA_DATA_DIR)")
    print("")
    print("4. Verificar health: http://localhost:8013/health")
    print("")
    print("README share: G:\\...\\minuta_data\\README_SYNC.txt contiene estos pasos.")
    print("=" * 70)


if __name__ == "__main__":
    main()
