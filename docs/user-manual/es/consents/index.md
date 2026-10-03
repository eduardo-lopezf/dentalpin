---
module: consents
last_verified_commit: 0d60d45
---

# Consentimientos

Las cartas de consentimiento del paciente. Forma parte de la app **Expediente
clínico**.

## Qué hace

- **Consentimiento informado.** La carta en la que un profesional explica al
  paciente un procedimiento, sus riesgos y sus alternativas, y el paciente
  acepta o no. No se puede firmar sin indicar qué profesional lo explicó.
- **Uso de datos personales.** El paciente acepta el aviso de privacidad de
  la clínica.

## Dónde está

- **Ficha del paciente → Consentimientos.** Lista las cartas del paciente.
  *Nuevo consentimiento* crea un borrador a partir de una plantilla;
  *Firmar* muestra el texto al paciente y recoge su firma en pantalla (o
  registra que no acepta).
- **Configuración → Clínica → Plantillas de consentimiento.** Los textos de la
  clínica: uno por procedimiento, y el aviso de privacidad. Editar una
  plantilla crea una versión nueva; las cartas ya escritas no cambian.

## Lo que conviene saber

- Un borrador se puede editar o descartar. **Una carta firmada no se edita
  ni se borra**: si el paciente retira su consentimiento, se **revoca**, y
  queda constancia de lo que firmó y de cuándo lo retiró.
- Las cartas firmadas, las no aceptadas y las revocadas aparecen en el
  expediente clínico del paciente.
- El texto de las plantillas es responsabilidad de la clínica y de su asesor
  legal; el programa no trae redacción legal.
- Con la app Profesionales deshabilitada no se puede indicar quién explicó
  el procedimiento, así que no se puede firmar un consentimiento informado.

## Permisos

- `consents.read`
- `consents.write`
- `consents.templates.write`

## Recursos técnicos

- [Resumen técnico](../../../technical/consents/overview.md)
- [Permisos](../../../technical/consents/permissions.md)
