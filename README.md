# AppWebSalidas — Sistema integrado de pañol

Monorepo del ecosistema de aplicaciones de pañol. Cada módulo es independiente
pero comparte este repositorio y despliega por separado.

## Arquitectura

```
AppWebSalidas/                    ← este repo (GitHub)
├── apps/
│   └── web/                      → Vercel: portal / login / shell (futuro)
├── services/
│   ├── etiquetas-web/            → Vercel: app de etiquetas (separada)
│   ├── etiquetas-api/            → PC impresora (LAN): cola + catálogo
│   └── print-agent/              → PC impresora (LAN): impresión física
└── scripts/                      → supervisor, monitoreo
```

| App | Dónde corre | Vercel |
|-----|-------------|--------|
| App móvil pañol (`AppPanolWeb`) | Repo / proyecto **propio** | Ya desplegada |
| **Etiquetas web** | `services/etiquetas-web` | **Proyecto Vercel aparte** |
| Shell principal | `apps/web` | Proyecto futuro |
| API + impresión | PC de la impresora | No va a Vercel |

## Despliegue — Etiquetas en Vercel

1. Conectar este repo a GitHub (`scripts/setup_github.ps1`).
2. En Vercel: **Add Project** → importar repo.
3. **Root Directory:** `services/etiquetas-web`
4. Variable **Production:** `ETIQUETAS_API_ORIGIN` = URL HTTPS pública de `etiquetas-api`.
5. Deploy.

La PC impresora sigue con el supervisor (`scripts/instalar_autostart.ps1`).
Para Vercel desde internet, exponé el puerto 8010 con túnel HTTPS.

Ver `COMO_IMPRIMIR.txt` y READMEs en cada servicio.
