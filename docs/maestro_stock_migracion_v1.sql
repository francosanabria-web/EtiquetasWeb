-- ===========================================================
-- Panol - Migracion Maestro Stock a MariaDB v1
-- Base: panol (D:\xampp\mysql\data\panol, utf8mb4_unicode_ci, MariaDB 10.4.32)
-- Fecha: 2026-09-18
-- Principio: Tablas GENERALES sin prefijo para catalogo maestro,
--            tabla de log con prefijo maestro_stock_
--            Motor InnoDB, utf8mb4_unicode_ci, INT UNSIGNED,
--            DATETIME CURRENT_TIMESTAMP, idempotente (IF NOT EXISTS)
--            Sin FKs para portabilidad (maestro es fuente primaria)
-- ===========================================================
-- Purpose:
--   maestro_stock        - Master catalog of stock items (replaces ARTICULOS
--                          sheet from base_datos.xlsx / master_codes.xlsx,
--                          ~6988 rows, dynamic columns). One row per codigo.
--   maestro_stock_import_log - Audit trail per imported Excel file.
-- Business rules (must be enforced in app/seed/import):
--   - Empty cells in import never overwrite existing data.
--   - Price 0 never overwrites price > 0 (preserves manual price).
-- ===========================================================

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------------
-- maestro_stock: catalog master (replaces Excel ARTICULOS)
-- Source: LABORATORIO BASE/base_datos.xlsx (preferred) or
--         master_codes.xlsx fallback, sheet ARTICULOS.
-- One row per codigo (VARCHAR 40 PK, UPPER, no trailing .0).
-- Columns mirror Excel dynamic headers normalized:
--   descripcion, stock, stock_minimo, ubicacion, precio_unitario,
--   importancia (CRITICO/ALTA FRECUENCIA/BASE), categoria.
-- activo=1 soft-delete flag. Timestamps for audit.
-- Indexes on ubicacion/importancia/categoria for filter queries.
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `maestro_stock` (
  `codigo` VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CODIGO - PK, UPPER, sin sufijo .0, ref articulo',
  `descripcion` TEXT COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'DESCRIPCION snapshot UPPER del maestro',
  `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm',
  `stock` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Stock actual/disponible (from valorizado file, or general)',
  `stock_minimo` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Stock minimo / punto reposicion (from detallado file)',
  `ubicacion` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'UBICACION (ej 10065C, estanteria)',
  `precio_unitario` DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT 'PRECIO_UNITARIO - 0 = sin precio, no pisa >0 en import',
  `importancia` ENUM('CRITICO','ALTA FRECUENCIA','BASE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'BASE' COMMENT 'Criticidad normalizada: CRITICO / ALTA FRECUENCIA / BASE',
  `categoria` VARCHAR(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Categoria articulo (ej GENERAL, LUBRICANTES)',
  `activo` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '1=activo, 0=soft-deleted',
  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'timestamp creacion fila',
  `actualizado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'timestamp ultima actualizacion',
  PRIMARY KEY (`codigo`),
  KEY `idx_maestro_stock_ubicacion` (`ubicacion`),
  KEY `idx_maestro_stock_importancia` (`importancia`),
  KEY `idx_maestro_stock_categoria` (`categoria`),
  KEY `idx_maestro_stock_activo` (`activo`),
  KEY `idx_maestro_stock_actualizado` (`actualizado_en`),
  KEY `idx_maestro_stock_alias` (`alias`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Catalogo maestro de stock - reemplaza ARTICULOS de base_datos.xlsx (regla: vacio no borra, precio 0 no pisa)';

-- v1.1 alias column for backward compat (idempotent)
-- Future option: if upgrading from v1.0 without alias, run:
-- ALTER TABLE `maestro_stock` ADD COLUMN `alias` VARCHAR(300) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Alias de busqueda, ej T10 para tornillo 10mm' AFTER `descripcion`;
-- CREATE INDEX `idx_maestro_stock_alias` ON `maestro_stock` (`alias`);

-- -----------------------------------------------------------
-- maestro_stock_import_log: audit per file import
-- One row per Excel file processed via POST /api/maestro-stock/import
-- or seed script. tipo_archivo derived from filename:
--   detallado  -> contains "detallado" (only minimo+ubicacion)
--   valorizado -> contains "valorizado" (stock+resto, price 0 no pisa)
--   general    -> other (resto without stock/minimo)
-- reporte TEXT stores human-readable summary for UI.
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `maestro_stock_import_log` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `archivo_origen` VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Nombre archivo Excel origen',
  `tipo_archivo` ENUM('detallado','valorizado','general') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Clasificacion por nombre archivo',
  `codigos_nuevos` INT NOT NULL DEFAULT 0 COMMENT 'Cantidad codigos insertados (no existian)',
  `codigos_modificados` INT NOT NULL DEFAULT 0 COMMENT 'Cantidad codigos con cambio efectivo',
  `codigos_sin_precio` INT NOT NULL DEFAULT 0 COMMENT 'Snapshot global sin precio (>0) tras import',
  `duracion_ms` INT NOT NULL DEFAULT 0 COMMENT 'Duracion procesamiento archivo en ms',
  `reporte` TEXT COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Detalle reporte texto (lineas modificados/nuevos/propagados)',
  `creado_en` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'timestamp import',
  PRIMARY KEY (`id`),
  KEY `idx_import_log_tipo` (`tipo_archivo`),
  KEY `idx_import_log_creado` (`creado_en`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Log auditoria importaciones maestro_stock por archivo';

-- ===========================================================
-- SEEDS / EJEMPLOS (idempotentes)
-- No hay catalogos propios; importancia es ENUM cerrado.
-- Ver scripts/seed_maestro_stock.py para poblado inicial.
-- ===========================================================
-- Ejemplo insert idempotente:
-- INSERT INTO maestro_stock (codigo, descripcion, stock, stock_minimo, ubicacion, precio_unitario, importancia, categoria)
-- VALUES ('DEMO-001','TORNILLO HEX M8x20',100,10,'A-01',15.50,'BASE','GENERAL')
-- ON DUPLICATE KEY UPDATE
--   descripcion=VALUES(descripcion), stock=VALUES(stock),
--   stock_minimo=VALUES(stock_minimo), ubicacion=VALUES(ubicacion),
--   precio_unitario=VALUES(precio_unitario), importancia=VALUES(importancia),
--   categoria=VALUES(categoria);

-- ===========================================================
-- CONSULTAS DE VERIFICACION
-- ===========================================================
-- -- Total y estados
-- SELECT COUNT(*) AS total FROM maestro_stock WHERE activo=1;
-- SELECT COUNT(*) AS sin_precio FROM maestro_stock WHERE activo=1 AND (precio_unitario IS NULL OR precio_unitario <= 0);
-- SELECT COUNT(*) AS criticos FROM maestro_stock WHERE activo=1 AND stock <= stock_minimo;
--
-- -- Por importancia
-- SELECT importancia, COUNT(*) AS cnt FROM maestro_stock WHERE activo=1 GROUP BY importancia;
--
-- -- Ultimas importaciones
-- SELECT id, archivo_origen, tipo_archivo, codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, creado_en
-- FROM maestro_stock_import_log ORDER BY id DESC LIMIT 20;
--
-- -- Ver maestro paginado con filtros
-- SELECT codigo, descripcion, stock, stock_minimo, ubicacion, precio_unitario, importancia, categoria
-- FROM maestro_stock WHERE activo=1
--   AND (importancia='CRITICO' OR importancia IS NOT NULL)
-- ORDER BY codigo LIMIT 20;
