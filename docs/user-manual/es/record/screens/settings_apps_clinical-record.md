---
module: record
screen: settings_apps_clinical-record
route: /settings/apps/clinical-record
related_endpoints:
  - GET /api/v1/record/format
  - PUT /api/v1/record/format
  - GET /api/v1/auth/clinic/settings/letterheads
  - PUT /api/v1/auth/clinic/settings/letterheads/{owner}
  - DELETE /api/v1/auth/clinic/settings/letterheads/{owner}
  - GET /api/v1/auth/clinic/settings/letterheads/{owner}/logo
  - PUT /api/v1/auth/clinic/settings/letterheads/{owner}/logo
  - DELETE /api/v1/auth/clinic/settings/letterheads/{owner}/logo
related_permissions:
  - record.read
  - record.configure
  - admin.clinic.read
  - admin.clinic.write
related_paths:
  - backend/app/modules/record/frontend/pages/settings/apps/clinical-record.vue
last_verified_commit: 5421a03
---

# Configuración del Expediente clínico

**Configuración → Apps → Expediente clínico → Configurar.** Cómo se arma el
expediente clínico en esta clínica. Lo que se elige aquí aplica a toda la
clínica, en la pestaña *Expediente* de cada paciente y en el documento que
se imprime o entrega.

## Permisos

- `record.read` — ver el formato.
- `record.configure` — cambiarlo (solo administrador).

## Membretes

Lo que encabeza **todo lo que la clínica imprime**: el expediente, las
cartas de consentimiento y el cuestionario de salud en blanco.

- **Clínica**: el membrete por defecto.
- **Uno por profesional**: en *Membrete propio para* se elige al profesional
  y se pulsa *Añadir*; la tarjeta aparece con su nombre y su cédula ya
  propuestos en la línea adicional.

Cada tarjeta tiene:

- **Logotipo**: PNG o JPG de hasta 512 KB. Se guarda en el momento de
  elegirlo.
- **Encabezado**: si se deja vacío, es el nombre de la clínica.
- **Línea adicional**: texto libre — el profesional y su cédula, la
  especialidad.
- **Mostrar domicilio** y **Mostrar teléfono y correo**: son los datos de
  la clínica; aquí solo se decide si salen.
- Su propio botón **Guardar**, y *Quitar membrete*.

### Qué membrete lleva cada documento

No se elige al imprimir; lo decide el sistema:

- **Carta de consentimiento**: el del profesional que la explicó.
- **Expediente** y **cuestionario en blanco**: el del profesional que lo
  imprime o entrega.
- Si ese profesional no tiene membrete propio, o quien imprime no es un
  profesional de la clínica, sale el de la clínica.
- **Nunca sale el membrete de otro doctor.**

Desde esta página los administra quien puede cambiar los datos de la
clínica. Además, **cada profesional puede configurar el suyo** en
*Configuración → Cuenta → Mi membrete*, sin poder tocar el de la clínica ni
el de un colega. Para eso su cuenta debe estar vinculada a su ficha de
profesional.

## Secciones y orden

Cada sección del expediente tiene un interruptor y flechas para subir o
bajar.

- **Apagar una sección** la quita de la pestaña *Expediente* y de lo que se
  puede imprimir o entregar. **No borra nada**: los datos siguen donde se
  capturan, y al encenderla vuelve a aparecer.
- **El orden** es el que sigue el expediente en pantalla y en papel.
- Una sección que añada una app habilitada después aparece al final.

## Qué debe tener el expediente

Los puntos que la pestaña *Expediente* revisa en cada paciente. Apaga los
que no apliquen a tu clínica; dejarán de mostrarse como pendientes.

## Plantillas de consentimiento

Acceso directo a los textos de las cartas de consentimiento.

## Guardar y restablecer

Nada cambia hasta pulsar **Guardar**. **Restablecer** vuelve al formato por
defecto —todas las secciones, en el orden de un expediente en papel, todos
los puntos revisados— y también hay que guardarlo.
