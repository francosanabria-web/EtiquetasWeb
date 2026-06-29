# minutas-web

Frontend del módulo **Minutas** — reuniones semanales de seguimiento de solicitudes a Compras.

## Acceso

| Desde | URL |
|-------|-----|
| Local | http://localhost:5175 |
| LAN | http://IP-PC:5175 |

Requiere **minutas-api** en el puerto 8012.

## Desarrollo

```powershell
cd services\minutas-web
npm install
copy .env.example .env.local
npm run dev:lan
```

## Flujo

1. **Comenzar reunión** — arrastra solicitudes y temas pendientes de semanas anteriores.
2. **Registrar solicitudes** — referencia, solicitante, urgencia, cantidad de ítems.
3. **Entregas parciales** — desplegable por pedido con historial y registro de nuevas entregas.
4. **Notas y temas** — actualizaciones por pedido y temas generales.
5. **Finalizar y enviar mail** — vista previa + envío SMTP (configurado en la API).

## Configuración

`.env.local`:

```
VITE_API_URL=http://localhost:8012
```
