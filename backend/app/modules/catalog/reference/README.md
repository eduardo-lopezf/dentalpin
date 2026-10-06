# Catálogo de referencia

Un archivo por especialidad. Cada archivo es lo que revisa un especialista:
el nombre de la disciplina, sus subáreas y sus tratamientos.

Es una **referencia**, no una tarifa: al habilitar una especialidad, sus
tratamientos se copian al catálogo de la clínica, y desde ahí la clínica
los edita. Los precios son un punto de partida.

## Formato

```json
{
  "key": "ortodoncia",
  "names": { "es": "Ortodoncia", "en": "Orthodontics" },
  "baseline": true,
  "subareas": [
    { "key": "retencion", "names": { "es": "Retención", "en": "Retention" } }
  ],
  "treatments": [
    {
      "code": "ORTO-RET-ESSIX",
      "names": { "es": "Retenedor termoformado (Essix)", "en": "Vacuum-formed retainer (Essix)" },
      "category": "ortodoncia",
      "subarea": "retencion",
      "specialties": ["ortodoncia"],
      "phase": "mantenimiento",
      "scope": "global_arch",
      "price": "110.00",
      "minutes": 30
    }
  ]
}
```

| Campo | Qué es |
|---|---|
| `baseline` | `true`: toda clínica nueva empieza con esta especialidad. `false`: se habilita cuando se quiera. |
| `subareas` | Las subáreas de la disciplina, en el orden en que se leen. |
| `code` | Código interno, único en todo el catálogo. **No se cambia**: es por lo que una clínica reconoce el tratamiento que ya tiene. |
| `category` | Dónde se encuentra al navegar el catálogo: `diagnostico`, `preventivo`, `restauradora`, `endodoncia`, `periodoncia`, `cirugia`, `ortodoncia`, `estetica`, `protesis`, `pediatrica`. |
| `subarea` | Una de las `subareas` de este mismo archivo. |
| `specialties` | Todas las disciplinas que lo reclaman. La de este archivo va primero. |
| `phase` | Etapa del plan en que cae por defecto: `urgencia`, `diagnostico`, `preventivo`, `estabilizacion`, `rehabilitacion`, `estetica`, `mantenimiento`. |
| `scope` | Sobre qué actúa: `tooth`, `multi_tooth`, `global_arch`, `global_mouth`. |
| `price` | Precio de referencia, como texto con dos decimales. |
| `minutes` | Duración por defecto de la cita. |

Campos opcionales: `descriptions`, `cost_price`, `vat_type` (por defecto
`exempt`), `pricing_strategy` (por defecto `flat`) y `pricing_config`,
`surface_prices`, `requires_surfaces`, `is_diagnostic`, `material_notes`,
`sessions` (cobro por sesiones) y los tres de dibujo en el odontograma:
`odontogram_treatment_type`, `visualization_rules`, `visualization_config`.

## Reglas

- **Un tratamiento se escribe una sola vez**, en el archivo de la
  disciplina a la que pertenece primero, y lista en `specialties` las
  demás. La panorámica está en `general.json` y nombra también a
  `radiologia`.
- **Nada se deduce del código.** Antes, la especialidad y la etapa salían
  de reglas por prefijo (`ORTO-RET-` → mantenimiento). Ahora cada
  tratamiento lo dice.
- **Añadir un tratamiento**: código nuevo, nunca reutilizado. Las clínicas
  que ya tienen la especialidad lo verán como "nuevo" y podrán añadirlo.
- **Quitar un tratamiento** de aquí no lo quita de ninguna clínica.
- **Cambiar un tratamiento** (nombre, precio) solo llega a una clínica
  cuando ésta restaura la especialidad.

## Validación

Los archivos se validan al arrancar la aplicación (`reference.py`): un
campo desconocido, un código repetido, o una disciplina, categoría o
subárea que no existe impiden que arranque. `tests/test_catalog_reference.py`
lo comprueba también.

Las plantillas de plan de cada especialidad no están aquí: son del módulo
de planes (`treatment_plan/templates_seed.py`).
