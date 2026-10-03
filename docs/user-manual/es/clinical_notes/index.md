---
module: clinical_notes
last_verified_commit: 0d60d45
---

# Clinical Notes

> _Esqueleto generado automáticamente — reemplazar con documentación real cuando se toque este módulo._

Página de aterrizaje del módulo `clinical_notes` en el manual de usuario.

## Pantallas

Este módulo no aporta páginas Nuxt propias.

## Corregir una nota

Una nota se corrige, no se reescribe. Al editar el texto, el anterior **se
guarda como versión**: con su número, el momento en que dejó de estar vigente,
quién lo sustituyó y el motivo, si se escribió uno.

Antes se sobrescribía en el sitio. El texto previo desaparecía, así que una
corrección y un original eran la misma cosa y no había forma de responder qué
decía la nota el día del procedimiento — que es justo lo que pregunta una
reclamación o una revisión de una aseguradora.

- La nota sigue mostrando **el texto actual**; el historial está detrás, en
  `GET /notes/{id}/versions`, con el mismo permiso que leer la nota.
- **Guardar sin cambiar nada no cuenta como corrección.** Si contara, abrir una
  nota y pulsar guardar llenaría el expediente de versiones idénticas y las
  correcciones de verdad quedarían enterradas.
- **El motivo es opcional.** Exigirlo llenaría el expediente de la palabra
  «corrección»; los motivos que valen se escriben cuando hay algo que decir.
- **Corregir no cambia el autor.** Si un administrador corrige la nota de otro,
  la nota sigue siendo de quien la escribió; la versión guarda quién la
  sustituyó.

## Permisos

- `clinical_notes.notes.read`
- `clinical_notes.notes.write`

## Recursos técnicos

- [Resumen técnico](../../../technical/clinical_notes/overview.md)
- [Permisos](../../../technical/clinical_notes/permissions.md)
- [Eventos](../../../technical/clinical_notes/events.md)
