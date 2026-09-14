# Google Drive Source for Reportes (master_salidas.xlsx)

The reportes service can read `master_salidas.xlsx` directly from Google Drive
instead of the `G:\` filesystem share. Daily files (`salidas_*.xlsx`) are not
migrated and keep being read from disk.

If the environment variables below are not set, or Drive authentication fails,
the service logs a warning and falls back to the disk source unchanged.

## 1. Create a service account

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable the **Google Drive API** (APIs & Services → Library → "Google Drive API" → Enable).
4. Go to **APIs & Services → Credentials → Create Credentials → Service Account**.
5. Name it (e.g. `reportes-reader`), create it, and skip role assignment
   (drive sharing grants access, not IAM roles).
6. Open the service account → **Keys → Add Key → Create new key → JSON**.
   Download the JSON key file and store it on the server in a secure,
   non-committable path (e.g. `C:\secrets\reportes-drive-sa.json`).

## 2. Share the file with the service account

- In Drive, share `master_salidas.xlsx` (or its parent folder) **with the
  service account's email** (shown in the JSON as `client_email`), with
  **Viewer** permission.
- Copy the file ID from the Drive URL:
  `https://drive.google.com/file/d/<FILE_ID>/view`

The service uses scope `https://www.googleapis.com/auth/drive.readonly` only.

## 3. Set environment variables

Add the following lines to `scripts/_internal/_start_reportes.bat` (do not
commit the key file or real IDs if the script is under version control):

```bat
set REPORTES_DRIVE_SERVICE_ACCOUNT=C:\secrets\reportes-drive-sa.json
set REPORTES_DRIVE_FILE_ID=<FILE_ID>
```

## 4. Verify

1. Restart the reportes service.
2. Check the startup log for `Reportes: Google Drive source initialized (read-only).`
3. Confirm the metadata endpoint reports the Drive source:

```bat
curl http://127.0.0.1:8017/api/reportes/resumen
```

Expected: inside the `fuente` object, `"path": "drive:master_salidas.xlsx"`,
`archivo_ok: true`, and a row count consistent with the master file.

## Behavior notes

- Freshness is detected via the file's `modifiedTime` + `md5Checksum`
  (single `files.get` metadata call per check), replacing the filesystem mtime
  check for the master. Daily files still use mtime as before.
- The master is downloaded fully in memory (`files.get_media`), no temp files.
- On any Drive read failure after a successful load, the previous in-memory
  snapshot keeps being served.
