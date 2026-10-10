# Changelog — consents module

## Unreleased

- fix(consents): cargas de escaneos y aperturas de documentos usan el transporte BFF autenticado con cookie HttpOnly.
- feat(consents): la carta impresa lleva el **membrete del profesional
  que la explicó** o, si no tiene uno propio, el de la clínica — nunca el
  de otro doctor (`app.core.letterhead`, ADR 0046). Bajo el membrete sale
  el profesional que informa, con su cédula; antes encabezaba la hoja.

- feat(consents): tipo de carta nuevo, **conformidad con el tratamiento**
  (`conformity`): el paciente firma que el tratamiento se concluyó a su
  satisfacción — la *firma de conformidad* de la historia en papel. No
  exige nombrar a un profesional y no sustituye al consentimiento
  informado. No comprueba que no haya adeudo.

- feat(consents): **firma en papel**. Una carta se puede imprimir, llenar
  y firmar a mano, y después subir escaneada.
  - `GET /{id}/pdf`: la carta como hoja para imprimir. En borrador es un
    formulario: los datos del paciente y el texto ya vienen escritos, y el
    diagnóstico, el plan, los nombres, las fechas y las firmas (paciente o
    responsable, quien informó y dos testigos) son líneas para llenar a
    mano. Una carta firmada en pantalla se imprime con su firma.
  - `POST /{id}/sign` acepta `method: "paper"` con `document_id`: el
    escaneo, ya subido a los documentos del paciente. Se comprueba, a
    través del contrato `PatientDocuments`, que el archivo es de ese mismo
    paciente. La carta guarda `signature_method` (`screen` | `paper`).
  - Pantalla de firma: selector *En pantalla / En papel*; en papel, botón
    *Imprimir* y campo para subir el escaneo (PDF, JPG o PNG). En la lista,
    *Imprimir* en cada carta y *Escaneo* en las firmadas en papel.
  - `integrates` añade `media`: con Media apagado se puede imprimir y
    firmar en pantalla, pero no archivar un escaneo.
  - Migración `con_0002`: columna `signature_method`; las cartas ya
    firmadas quedan como `screen`.

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
