---
module: treatment_plan
screen: treatments_plans_new
route: /treatments/plans/new
related_endpoints:
  - POST /api/v1/treatment_plan/treatment-plans
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/catalog-items
  - GET /api/v1/treatment_plan/plan-templates
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/new.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanDraftChart.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanTreatmentSearch.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanDraftLines.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: 75cd119
---

# Nuevo plan de tratamiento

Se dibuja primero y se firma después. La pantalla abre en un odontograma
en blanco: tocas una pieza, dices qué necesita, y solo cuando el plan ya
está en pantalla te pregunta de quién era la boca. Al guardar, el plan
nace en estado `draft` y se abre el
[detalle](./treatments_plans_id.md) para confirmarlo y generar
presupuesto.

## De un vistazo

- **Dos pasos, en este orden.** Primero el odontograma y los
  tratamientos; después el paciente, el título, el profesional y las
  notas. Es el orden en el que trabaja quien acaba de mirar una boca.
- **El odontograma está en blanco.** No hay paciente todavía, así que no
  hay historial que dibujar: lo que ves es el plan que estás haciendo, no
  lo que el paciente tiene. **Nada impide planificar sobre una pieza
  ausente** — de eso avisa el paso siguiente.
- **Nada se guarda hasta *Crear*.** El paciente (si es nuevo), el plan y
  todas las líneas se escriben de una vez al final. Un plan a medias que
  abandonas no deja nada detrás.
- **Desde la ficha del paciente** (*Clínico → Planes → Nuevo plan*) se
  llega a esta misma pantalla con el paciente ya puesto y el título ya
  escrito. El odontograma sigue siendo lo primero.
- **Boca completa.** Los tratamientos que no cuelgan de ninguna pieza
  —limpieza, panorámica, primera consulta— se añaden por el botón *Boca
  completa*, no tocando un diente.

## Paso 1 — Dibujar el plan

> Requiere `treatment_plan.plans.write`.

1. Toca una pieza (o una cara, si el tratamiento va por caras). Se abre
   un panel lateral titulado con la pieza.
2. **Sin escribir nada** el panel ya ofrece *Usados recientemente*: los
   tratamientos que tu clínica ha usado últimamente, que suelen ser la
   respuesta. No es «los más usados de siempre»: es recencia, porque una
   consulta repite lo de esta semana.
3. Al teclear, el panel busca en dos sitios a la vez: tus **plantillas**
   y el **catálogo**. Ignora acentos, y las plantillas se encuentran
   también por lo que llevan dentro, así que «implante» saca la plantilla
   aunque su nombre no lo diga.
4. Elegir un tratamiento lo añade a la pieza. Elegir una **plantilla**
   añade todas sus líneas de golpe: las que van por diente se ponen en la
   pieza donde estabas, y las de boca completa no piden ninguna.
5. La lista de la derecha (debajo, en vertical) es el plan. El lápiz abre
   la línea para editarla; la papelera la quita. El total se actualiza
   solo.
6. **Continuar** cuando haya al menos un tratamiento, y ninguno sin pieza.

### Corregir una línea antes de crear el plan

Mientras el plan no exista, **todo lo de una línea se puede cambiar** las
veces que haga falta: no hay nada escrito, ni presupuesto que lo cite.
Después de *Crear* deja de ser así y para tocar los tratamientos hay que
**Reabrir** el plan, lo que cancela el presupuesto vigente.

El lápiz de la línea abre:

- **Piezas.** Cada pieza es una chapa con su ✕ para quitarla. *Elegir en
  el odontograma* le entrega el odontograma a esa línea: mientras el aviso
  azul esté arriba, tocar una pieza la añade y volver a tocarla la quita,
  en lugar de abrir el panel de tratamientos. *Listo* devuelve el
  odontograma a lo suyo. Los tratamientos de boca completa o de arcada no
  tienen esta sección: no cuelgan de ninguna pieza.
- **Caras**, solo en los tratamientos que el catálogo describe por caras
  (una obturación sí; una corona no, porque cubre el diente). Se escriben
  siempre en orden de odontograma, así que las mismas tres caras se leen
  igual las toques en el orden que las toques.
- **Fase** y **nota de la línea**.

El **precio no se edita aquí**: es el del catálogo, y cambiarlo pertenece
al presupuesto, donde queda constancia de la negociación. Para cambiar el
tratamiento en sí, quita la línea y añade la correcta.

> Una línea de diente a la que le quitas todas las piezas se marca en
> ámbar como *Falta la pieza* y bloquea **Continuar** nombrándola. Es a
> propósito: durante una corrección tiene que poder quedarse vacía un
> momento, y el bloqueo es lo que evita que el plan salga así.

### Tratamientos sin precio

El catálogo es de donde el plan saca lo que cuesta cada cosa. Si un
tratamiento **no tiene precio**, su línea lo muestra como «-» y el total
lo cuenta como **cero** — no hay otra aritmética posible, pero es una
omisión que importa: cuatro tratamientos de los que dos no tienen precio
suman una cifra que **parece completa**, y esa cifra es la que *Confirmar*
convierte en el presupuesto que el paciente firma.

Por eso, junto al total aparece un aviso con cuántas líneas van sin precio
y un enlace a **Catálogo** para ponérselo (si tienes permiso para
editarlo). El aviso se repite en el paso 2, que es donde está el botón
*Crear*, y otra vez en la ventana de **Confirmar plan**: «N tratamientos
entran sin precio, así que el presupuesto no los cobrará».

**Avisa, no impide.** Una clínica presupuesta legítimamente algunos
trabajos caso por caso, y aquí vale la misma regla que para los conflictos
del odontograma: quien mira la boca sabe más que una regla sobre ella.

## Paso 2 — De quién es la boca

1. Busca al paciente por nombre o teléfono, o pulsa **Crear paciente
   nuevo** y escribe nombre, apellidos y teléfono. El paciente se crea
   al pulsar *Crear*, no antes.
2. Al elegirlo, la pantalla lee su odontograma real y **avisa de lo que
   choca**: una pieza que consta como ausente, o un tratamiento igual ya
   planificado en esa misma pieza. Es un aviso, no un bloqueo: puedes
   **Corregir en el odontograma** o seguir adelante.
3. El **título** se escribe solo como *Plan de Tratamiento para [nombre]*
   y puedes cambiarlo. Si lo tocas, deja de reescribirse.
4. Asigna el profesional. Viene preseleccionado si tu usuario es un
   profesional de la clínica.
5. Las notas de diagnóstico e internas están en **Más opciones**.
6. **Crear**. Se publica `treatment_plan.created`, se añaden todas las
   líneas y entras al detalle con el plan montado.

> Si algún tratamiento ya no está en tu catálogo, esa línea se omite y el
> aviso te dice cuál. El resto del plan se crea igualmente.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Acceder al formulario y ver plantillas y catálogo | `treatment_plan.plans.read` |
| Crear el plan y añadir sus tratamientos | `treatment_plan.plans.write` |
| Crear, editar u ocultar plantillas | `treatment_plan.plans.templates` |

## Resolución de problemas

- **No sale nada en «Usados recientemente».** La lista se llena con lo
  que la clínica va registrando; en una clínica recién creada está vacía
  y el panel lo dice. Busca en el catálogo mientras tanto.
- **Busco un tratamiento y no aparece.** El buscador necesita dos letras
  y solo ofrece tratamientos activos. Los diagnósticos (caries, fractura)
  no se planifican aquí: se registran en el odontograma del paciente.
- **He tocado una pieza y el tratamiento no se ha puesto en ella.** Los
  tratamientos de boca completa o de arcada no cuelgan de un diente
  aunque los elijas desde uno; aparecerán en la lista como *Boca
  completa*.
- **Toco el odontograma y en vez de abrirse el panel se me añaden piezas
  a una línea.** Hay una línea en modo edición: el aviso azul de arriba
  dice cuál. Pulsa *Listo* y el odontograma vuelve a añadir tratamientos.
- **No me deja continuar y dice «Indica en qué pieza va».** Una línea de
  diente se ha quedado sin ninguna. Ábrela con el lápiz y dale una pieza,
  o quítala.
- **Desde «Boca completa» no me deja elegir un tratamiento.** Los que van
  por diente están atenuados ahí, porque no habría pieza a la que
  asignarlos. Tócalos desde la pieza.
- **El aviso de piezas no aparece.** Solo puede aparecer después de
  elegir al paciente, y necesita permiso de lectura del odontograma. Sin
  él, el plan se crea igual pero sin comprobación.
- **Selector de profesional vacío.** Si tu rol es admin o recepción y no
  salen profesionales, créalos o actívalos en *Ajustes → Usuarios*.
