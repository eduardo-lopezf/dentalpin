# Changelog — consents module

## Unreleased

- feat(consents): módulo nuevo, dentro de la App **Expediente clínico**.
  Cartas de consentimiento del paciente, en dos tipos: **consentimiento
  informado** (NOM-004-SSA3-2012; Ley General de Salud Art. 51 Bis 1) y
  **uso de datos personales** (aviso de privacidad).
  - Plantillas de la clínica con versión; cada carta guarda su propia
    copia del texto y la versión de la plantilla.
  - Borrador → firmado / no aceptado; firmado → revocado. Una carta
    firmada no se edita ni se borra (ADR 0032, ADR 0045).
  - Un consentimiento informado no se puede firmar sin indicar qué
    profesional lo explicó; se guarda su nombre y cédula de ese día.
  - Firma en pantalla (tableta, ratón o lápiz).
  - Pestaña *Consentimientos* en la ficha del paciente y página
    *Plantillas de consentimiento* en Configuración → Clínica.
  - Las cartas firmadas, no aceptadas y revocadas forman parte del
    expediente clínico compuesto (sección `consents`).
  - Derechos del paciente: se exportan; no se suprimen.
