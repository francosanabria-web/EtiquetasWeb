# Correos automáticos — tipos

## Hoja `correos` en master_codes.xlsx

| remitente | password | destinatario | tipo |
|---|---|---|---|
| almacen@... | app_password | jefe@... | pañol |
| | | compras@... | compras |
| | | sup@... | supervisor |

- `remitente` y `password`: primera fila (no repetir en cada fila).
- `destinatario`: uno o varios mails (coma o `;`).
- Sin columna `tipo`: solo el primario recibe todo (compatibilidad).

## Reportes automáticos (07:30)
| Reporte | Destinatarios |
|---|---|
| Reposición diaria | pañol + **compras** |
| Gasto diario por sector | solo pañol |
| Gasto mensual | solo pañol |
| Salida de activos | pañol + supervisor + **compras** |

## Prueba manual
```powershell
Remove-Item .ultimo_mail*.txt -ErrorAction SilentlyContinue
python almacen_gui.py --enviar-730
```
Log: `mail_automatico.log`
