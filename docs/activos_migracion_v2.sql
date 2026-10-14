-- ===========================================================
-- Panol - Migracion Activos MariaDB v2 (fotos + aprobacion)
-- Base: panol (MariaDB, utf8mb4_unicode_ci)
-- Fecha: 2026-10-14
-- Cambios:
--   - Nueva tabla salida_activos_fotos (MEDIUMBLOB + hash_sha256,
--     tipo retiro/ingreso, FK ON DELETE CASCADE a salida_activos).
--   - ALTER salida_activos: estado_aprobacion, encargado_salida_id,
--     aprobado_por, aprobado_en, usuario_creador_id, usuario_ur.
--     FK fk_activos_encargado -> personal(id).
--   - Backfill: estado_aprobacion='aprobado' SOLO en filas
--     preexistentes al momento de agregar la columna.
-- Principio: idempotente (segunda corrida es no-op).
-- ===========================================================

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET FOREIGN_KEY_CHECKS = 1;

-- ===========================================================
-- salida_activos_fotos: evidencia fotografica por salida
-- ===========================================================
CREATE TABLE IF NOT EXISTS `salida_activos_fotos` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `salida_activo_id` bigint(20) unsigned NOT NULL COMMENT 'FK salida_activos(id)',
  `tipo` enum('retiro','ingreso') NOT NULL DEFAULT 'retiro',
  `foto` mediumblob NOT NULL COMMENT 'WebP (1280px max, 5 MB max)',
  `mime` varchar(30) NOT NULL DEFAULT 'image/webp',
  `tamano_bytes` int(10) unsigned NOT NULL,
  `hash_sha256` char(64) NOT NULL COMMENT 'Integridad / dedup',
  `numero_remito` varchar(40) NOT NULL DEFAULT '' COMMENT 'Remito asociado si aplica',
  `usuario_id` int(11) DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_fotos_salida` (`salida_activo_id`),
  CONSTRAINT `fk_fotos_activo` FOREIGN KEY (`salida_activo_id`)
    REFERENCES `salida_activos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Fotos de activos: retiro (1-3) e ingreso (0-1 opcional)';

-- ===========================================================
-- ALTER salida_activos: columnas de aprobacion y auditoria
-- MariaDB >= 10.5 soporta IF NOT EXISTS en ADD COLUMN / ADD KEY.
-- ===========================================================
-- Snapshot pre-ALTER: 1 si la columna estado_aprobacion YA existe
-- (corrida previa). El backfill solo corre cuando es 0.
SET @col_estado_aprobacion_existed := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'salida_activos'
    AND COLUMN_NAME = 'estado_aprobacion'
);

ALTER TABLE `salida_activos`
  ADD COLUMN IF NOT EXISTS `estado_aprobacion` enum('pendiente','aprobado') NOT NULL DEFAULT 'pendiente' COMMENT 'Flujo de aprobacion (nuevas salidas entran pendiente)',
  ADD COLUMN IF NOT EXISTS `encargado_salida_id` int(11) DEFAULT NULL COMMENT 'FK personal(id) encargado de la salida',
  ADD COLUMN IF NOT EXISTS `aprobado_por` int(11) DEFAULT NULL COMMENT 'usuarios.id que aprobo',
  ADD COLUMN IF NOT EXISTS `aprobado_en` datetime DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS `usuario_creador_id` int(11) DEFAULT NULL COMMENT 'usuarios.id del alta',
  ADD COLUMN IF NOT EXISTS `usuario_ur` int(11) DEFAULT NULL COMMENT 'usuarios.id ultima recepcion (ingreso)',
  ADD KEY IF NOT EXISTS `idx_activos_estado_aprob` (`estado_aprobacion`),
  ADD CONSTRAINT IF NOT EXISTS `fk_activos_encargado` FOREIGN KEY (`encargado_salida_id`)
    REFERENCES `personal` (`id`);

-- ===========================================================
-- Backfill: marcar filas PREEXISTENTES como aprobadas.
-- Solo corre cuando la columna acaba de ser agregada en ESTA
-- ejecucion; si ya existia, es no-op (evita aprobar pendientes
-- nuevos en reinicios).
-- ===========================================================
UPDATE `salida_activos`
SET `estado_aprobacion` = 'aprobado'
WHERE `estado_aprobacion` = 'pendiente'
  AND @col_estado_aprobacion_existed = 0;

-- ===========================================================
-- Rollback (manual):
--   ALTER TABLE salida_activos
--     DROP FOREIGN KEY fk_activos_encargado,
--     DROP KEY idx_activos_estado_aprob,
--     DROP COLUMN estado_aprobacion,
--     DROP COLUMN encargado_salida_id,
--     DROP COLUMN aprobado_por,
--     DROP COLUMN aprobado_en,
--     DROP COLUMN usuario_creador_id,
--     DROP COLUMN usuario_ur;
--   DROP TABLE salida_activos_fotos;
-- ===========================================================
