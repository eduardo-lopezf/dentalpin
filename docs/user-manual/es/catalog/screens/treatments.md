---
module: catalog
screen: treatments
route: /treatments
related_permissions:
  - catalog.read
  - treatment_plan.plans.read
related_paths:
  - backend/app/modules/catalog/frontend/pages/treatments/index.vue
last_verified_commit: 42c33757157786fe53cdb00fc76091e9922be1c5
---

# /treatments

Punto de entrada de la sección — no es una pantalla propia. Redirige de
inmediato a una de las dos superficies de "Tratamientos" según el rol
actual:

- **[Bandeja de planes](../../treatment_plan/screens/treatments_plans.md)**
  (`/treatments/plans`) — el trabajo diario, para quien tenga
  `treatment_plan.plans.read`.
- **[Catálogo de tratamientos](./treatments_catalog.md)**
  (`/treatments/catalog`) — alternativa para roles sin acceso a planes;
  todos los perfiles tienen `catalog.read`.

La sección junta dos entradas de menú anteriores (planes, catálogo) en
una sola. Aterrizar en la bandeja por defecto mantiene la tarea de uso
diario a un clic, en vez de detrás de la página de referencia.

## Permisos

- `catalog.read` — todos los perfiles; garantiza que el destino de
  respaldo siempre sea alcanzable.
- `treatment_plan.plans.read` — cuando está presente, tiene prioridad y
  dirige a la bandeja de planes.
