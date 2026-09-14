# -*- coding: utf-8 -*-
"""Google Drive data source for master_salidas.xlsx (optional, read-only).

Lazy initialization: Drive mode is only active when BOTH environment
variables are set:
  - REPORTES_DRIVE_SERVICE_ACCOUNT: path to a service account JSON key file
  - REPORTES_DRIVE_FILE_ID: Drive file ID of master_salidas.xlsx

If either is missing, or Drive auth/import fails, the store falls back to
the current disk path (G:\\...) unchanged.
"""

from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger("reportes.drive_source")

_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"

_lock = threading.Lock()
_service = None  # googleapiclient drive service, lazily built
_init_attempted = False
_init_error: str | None = None


def _env_config() -> tuple[str, str]:
    """Return (service_account_path, file_id), stripped. Empty strings if unset."""
    sa_path = os.environ.get("REPORTES_DRIVE_SERVICE_ACCOUNT", "").strip()
    file_id = os.environ.get("REPORTES_DRIVE_FILE_ID", "").strip()
    return sa_path, file_id


def is_configured() -> bool:
    """True only when both Drive env vars are set (regardless of init result)."""
    sa_path, file_id = _env_config()
    return bool(sa_path and file_id)


def _build_service():
    """Build the Drive API service from the service account JSON.

    Raises on import/auth errors; caller handles fallback.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_path, _file_id = _env_config()
    creds = service_account.Credentials.from_service_account_file(
        sa_path, scopes=[_DRIVE_SCOPE]
    )
    # cache_discovery avoids local discovery-doc caching issues on Windows
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _get_service():
    """Lazily build a thread-safe Drive service. Returns None on failure."""
    global _service, _init_attempted, _init_error
    if _service is not None:
        return _service
    with _lock:
        if _service is not None:
            return _service
        if _init_attempted and _init_error is not None:
            return None
        _init_attempted = True
        try:
            _service = _build_service()
            log.info("Reportes: Google Drive source initialized (read-only).")
            return _service
        except Exception as e:  # pragma: no cover - depends on env/creds
            _init_error = str(e)
            log.warning(
                "Reportes: Drive auth/init failed (%s); falling back to disk source.",
                e,
            )
            return None


def is_enabled() -> bool:
    """True when Drive mode is configured AND the client initialized OK."""
    if not is_configured():
        return False
    return _get_service() is not None


def get_modified_etag() -> str | None:
    """Freshness token for the master file: modifiedTime + md5Checksum + id.

    Returns None if Drive is unavailable or the metadata call fails.
    """
    service = _get_service()
    if service is None:
        return None
    _sa, file_id = _env_config()
    try:
        meta = (
            service.files()
            .get(fileId=file_id, fields="id,modifiedTime,md5Checksum")
            .execute()
        )
    except Exception as e:
        log.warning("Reportes: Drive metadata fetch failed: %s", e)
        return None
    return "%s|%s|%s" % (
        meta.get("id", ""),
        meta.get("modifiedTime", ""),
        meta.get("md5Checksum", ""),
    )


def download_bytes() -> bytes:
    """Download the master file fully in memory (no temp files)."""
    service = _get_service()
    if service is None:
        raise RuntimeError("Google Drive source is not available")
    _sa, file_id = _env_config()
    request = service.files().get_media(fileId=file_id)
    return request.execute()
