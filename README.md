# Paneles de ventas Paris Night

Dos paneles públicos (GitHub Pages), instalables como app en el celular y actualizados solos cada hora.

| Panel | Link | Carpeta | Datos | Script |
|---|---|---|---|---|
| Mercado Libre (Click and Carry, PARISNIGHT/NAVY) — "PN Ventas" | https://osamizcarlos-arch.github.io/panel-click-and-carry/ | raíz | API de Mercado Libre | `actualizar.py` |
| Locales Cabildo y DOT — "PN Locales" | https://osamizcarlos-arch.github.io/panel-click-and-carry/locales/ | `locales/` | Odoo (Punto de venta) | `actualizar_locales.py` |

## Estructura
- **Raíz = panel de Mercado Libre:** `index.html` (el panel con los datos adentro), `actualizar.py`, `manifest.webmanifest`, `sw.js` e íconos. No se mueve: cambiaría el link y habría que reinstalar la app en los teléfonos.
- **`locales/` = panel de locales:** `index.html`, `manifest.webmanifest`, `sw.js` e íconos. Su script, `actualizar_locales.py`, está en la raíz.

## Cómo se actualizan
Dos tareas programadas de Claude, cada una toca solo sus archivos:
- **Actualizar panel Mercado Libre** (minuto :09): renueva el token de ML, corre `ML_ACCESS_TOKEN=... python3 -I actualizar.py` y sube `index.html` ("Actualización automática de ventas").
- **Actualizar panel locales** (minuto :51): corre `ODOO_KEY=... python3 -I actualizar_locales.py` y sube `locales/index.html` ("Actualización automática de locales").

Si un script falla, no se sube nada y el panel queda con la última foto buena. Los scripts reescriben solo los datos y el pie "Actualizado: …"; si se cambia ese texto, hay que ajustar la regex del script.

## Seguridad
- **El repo es público.** Nunca subir credenciales: los scripts reciben el token de ML y la clave de Odoo por variables de entorno.
- Los paneles muestran solo totales (por día, artículo, ciudad, local y caja) y nombre + inicial de las vendedoras. No hay datos de compradores.
- Cualquiera con el link ve las ventas.

## Documentación
La documentación completa (accesos, métodos y pendientes) está en el proyecto "Paris Night" de Claude: `ML_panel-ventas` y `LOC_panel-locales`.
