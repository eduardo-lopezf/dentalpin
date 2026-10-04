---
module: patients_clinical
last_verified_commit: 0000000
---

# Patients Clinical

> _Esqueleto generado automáticamente — reemplazar con documentación real cuando se toque este módulo._

Página de aterrizaje del módulo `patients_clinical` en el manual de usuario.

## Cuestionario de salud

**Ficha del paciente → Cuestionario de salud.** Lo que el paciente declara
en su consulta: motivo de consulta, grupo sanguíneo, alergias, doce
preguntas de sí o no (con su causa) y la lista de padecimientos.

- **En pantalla:** *Nuevo cuestionario*. Una pregunta que se deja sin
  contestar queda como no preguntada, no como «no».
- **En papel:** *Imprimir en blanco* saca la hoja con los datos del
  paciente; se llena a mano, se escanea y se sube desde *Nuevo
  cuestionario → En papel*. El motivo de consulta se escribe aparte para
  que aparezca en el expediente.
- Un cuestionario guardado no se edita: en la siguiente visita se llena
  otro. Si se guardó por error, *Anular* lo retira dejando constancia.
- No sustituye al historial médico: las alergias, la medicación y las
  enfermedades que la clínica mantiene al día siguen en su sitio.

## Pantallas

Este módulo no aporta páginas Nuxt propias.

## Permisos

- `patients_clinical.medical.read`
- `patients_clinical.medical.write`
- `patients_clinical.emergency.read`
- `patients_clinical.emergency.write`

## Recursos técnicos

- [Resumen técnico](../../../technical/patients_clinical/overview.md)
- [Permisos](../../../technical/patients_clinical/permissions.md)
- [Eventos](../../../technical/patients_clinical/events.md)
