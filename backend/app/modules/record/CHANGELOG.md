# Changelog — record module

## Unreleased

- feat(expediente): nace el módulo **`record`**, instalable desde
  *Configuración → Módulos*. Compone el expediente clínico de un paciente a
  partir de lo que guardan los módulos instalados: cabecera y secciones
  ordenadas de entradas fechadas y atribuidas.

  **No posee ningún dato clínico**, y eso es el diseño, no una carencia. Lo
  dice la especificación: *«el expediente no es un sitio nuevo donde guardar
  datos clínicos; es una vista de datos que ya poseen siete módulos, y en el
  momento en que se vuelve copia empieza a separarse del original y hay dos
  verdades sobre las alergias de un paciente»*. Por eso no tiene modelos ni
  migraciones, como `reports`.

- feat(core): contrato `get_record_sections()` en `BaseModule`, con el
  vocabulario (`RecordSection`, `RecordEntry`, `SectionCategory`) en
  `app.core.record`. Vive en el core por la misma razón que
  `SubjectContributor`: si viviera en este módulo, los módulos que aportan
  tendrían que importarlo y declararlo en `depends`, lo que invertiría la
  dependencia y haría obligatorio un módulo opcional para `patients_clinical`,
  que no es desinstalable.

  Es un contrato **distinto** del de derechos del sujeto, no una
  reutilización: responden preguntas distintas para lectores distintos, y la
  diferencia que más importa es que `billing`, `payments`, `verifactu` y
  `accounting_export` aportan **cero** aquí. Una divulgación clínica que lleve
  datos de facturación es un defecto de privacidad, no una función.

- feat(expediente): `GET /api/v1/record/patients/{id}` devuelve la composición.
  Las secciones vuelven **aunque estén vacías** —«este módulo no guarda nada de
  este paciente» es una respuesta, y una sección ausente deja al lector sin
  saber si se preguntó—. Las entradas retractadas se omiten salvo que se pidan
  explícitamente: nunca se borran, pero una entrada que no debió existir no es
  lo que se le entrega a un colega.

  Si la sección de un módulo falla, se registra y vuelve vacía en lugar de
  negar el resto del expediente a quien lo está leyendo.

- feat(antecedentes): `patients_clinical` es el primer módulo que aporta —
  alergias, medicación, enfermedades sistémicas e historia quirúrgica, cuatro
  secciones porque así se leen—. Cada entrada lleva tiempo **clínico** (una
  cirugía de 2019 anotada hoy ordena en 2019), el estado del ciclo de vida y el
  profesional responsable, todo leído de lo que las filas ya dicen desde la
  fase 0.
