# -*- coding: utf-8 -*-
"""Script temp para crear tabla salida_activos en MariaDB."""
import pymysql

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='panol', charset='utf8mb4')
cur = conn.cursor()

sql = """CREATE TABLE IF NOT EXISTS `salida_activos` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `fecha` date NOT NULL COMMENT 'FECHA_SALIDA',
  `equipo` varchar(200) NOT NULL DEFAULT '',
  `codigo` varchar(40) NOT NULL DEFAULT '',
  `descripcion` varchar(200) NOT NULL DEFAULT '',
  `sector` varchar(100) NOT NULL DEFAULT '',
  `cantidad` int(10) unsigned NOT NULL DEFAULT 1,
  `nro_serie` varchar(100) NOT NULL DEFAULT '',
  `numero_pedido` varchar(40) NOT NULL DEFAULT '',
  `numero_oc` varchar(40) NOT NULL DEFAULT '',
  `numero_remito` varchar(40) NOT NULL DEFAULT '',
  `proveedor` varchar(150) NOT NULL DEFAULT '',
  `fecha_salida` date DEFAULT NULL,
  `fecha_regreso` date DEFAULT NULL,
  `estado_al_ingreso` varchar(100) NOT NULL DEFAULT '',
  `observaciones` text,
  `dias_fuera` int(10) unsigned NOT NULL DEFAULT 0,
  `estado` enum('fuera_de_planta','ingresado_a_planta','devuelto') NOT NULL DEFAULT 'fuera_de_planta',
  `fingerprint` varchar(500) NOT NULL DEFAULT '',
  `creado_en` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `actualizado_en` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_salida_activos_fecha` (`fecha`),
  KEY `idx_salida_activos_equipo` (`equipo`(50)),
  KEY `idx_salida_activos_estado` (`estado`),
  KEY `idx_salida_activos_sector` (`sector`(50)),
  UNIQUE KEY `uk_salida_activos_fingerprint` (`fingerprint`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tabla de activos'"""

cur.execute(sql)
conn.commit()
cur.execute('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA="panol" AND TABLE_NAME="salida_activos"')
print('Table exists:', cur.fetchone()[0] > 0)
conn.close()
print('Done.')
