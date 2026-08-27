---
module: catalog
screen: treatments_catalog
route: /treatments/catalog
related_endpoints:
  - GET /api/v1/catalog/categories
  - GET /api/v1/catalog/items
  - GET /api/v1/catalog/specialties
  - GET /api/v1/professionals
related_permissions:
  - catalog.read
related_paths:
  - backend/app/modules/catalog/frontend/pages/treatments/catalog.vue
last_verified_commit: 3568519
---

# /treatments/catalog

Vista clínica del catálogo, para todo el equipo. Es la contraparte de
**Ajustes → Catálogo de tratamientos**, que administra precios y altas y solo
ve el administrador: aquí se consulta *qué ofrecemos y quién lo hace*.

## Permisos

- `catalog.read` — todos los perfiles.

## Los tres ejes

Cada tratamiento se cruza por tres clasificaciones independientes que se
combinan entre sí:

| Eje | Responde | Ejemplo |
|---|---|---|
| **Categoría** | dónde está archivado | Restauradora |
| **Especialidad** | quién lo realiza | Implantología |
| **Fase** | cuándo dentro del tratamiento | Rehabilitación |

Por defecto se ven **todos** los tratamientos activos. Los filtros solo
reducen; ninguno oculta nada de forma permanente.

Los ejes no son subconjuntos entre sí, y ahí está su utilidad: filtrar por
**Implantología** reúne el implante (categoría Cirugía), la corona sobre
implante (Restauradora) y la sobredentadura (Prótesis) — un solo flujo
clínico repartido en tres categorías.

## Solo lo que mi equipo realiza

Este interruptor reduce la lista a las especialidades que cubren los
profesionales **activos** de la clínica.

Es un filtro, no un candado: apagándolo vuelve a verse el catálogo completo.
Eso importa porque el catálogo también es histórico — necesitas poder
presupuestar una derivación, consultar un tratamiento que hizo un compañero
que ya no está, o revisar algo facturado el año pasado.

Si ningún profesional tiene especialidad asignada, el interruptor lo avisa y
no muestra nada: la especialidad se asigna en **Profesionales**.
