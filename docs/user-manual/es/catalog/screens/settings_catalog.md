---
module: catalog
screen: catalog
route: /settings/catalog
related_endpoints:
  - DELETE /api/v1/catalog/categories/{category_id}
  - DELETE /api/v1/catalog/items/{item_id}
  - DELETE /api/v1/catalog/specialties/{specialty_id}
  - DELETE /api/v1/catalog/vat-types/{vat_type_id}
  - GET /api/v1/catalog/categories
  - GET /api/v1/catalog/categories/{category_id}
  - GET /api/v1/catalog/items
  - GET /api/v1/catalog/items/popular
  - GET /api/v1/catalog/items/search
  - GET /api/v1/catalog/items/{item_id}
  - GET /api/v1/catalog/odontogram-treatments
  - GET /api/v1/catalog/odontogram-treatments/by-category
  - GET /api/v1/catalog/specialties
  - GET /api/v1/catalog/specialties/{specialty_id}
  - GET /api/v1/catalog/specialties/suggestions
  - GET /api/v1/catalog/specialties/{specialty_id}/items
  - GET /api/v1/catalog/vat-types
  - GET /api/v1/catalog/vat-types/default
  - GET /api/v1/catalog/vat-types/{vat_type_id}
  - POST /api/v1/catalog/categories
  - POST /api/v1/catalog/items
  - POST /api/v1/catalog/specialties
  - POST /api/v1/catalog/vat-types
  - PUT /api/v1/catalog/categories/{category_id}
  - PUT /api/v1/catalog/items/{item_id}
  - PUT /api/v1/catalog/specialties/{specialty_id}
  - PUT /api/v1/catalog/specialties/{specialty_id}/items
  - PUT /api/v1/catalog/vat-types/{vat_type_id}
related_permissions:
  - catalog.read
  - catalog.write
  - catalog.admin
related_paths:
  - backend/app/modules/catalog/frontend/pages/settings/catalog/index.vue
last_verified_commit: 1facfd7
---

# /settings/catalog

> _Esqueleto generado automáticamente — reemplazar con documentación real cuando se toque este módulo._

_Pantalla `/settings/catalog` del módulo `catalog`._

## Permisos

- `catalog.read`
- `catalog.write`
- `catalog.admin`

## Para qué sirve

_Pendiente de documentar._

## Pestañas

La pantalla tiene dos pestañas:

- **Tipo de Tratamiento**: vista existente, tratamientos agrupados por
  categoría (`TreatmentCategory`).
- **Por Especialidad**: gestión (alta/edición/baja) del catálogo de
  especialidades odontológicas (`Specialty`), independiente de la
  categoría del tratamiento — p. ej. "Cirugía Oral y Maxilofacial",
  y asignación de los tratamientos del catálogo a cada una.

### Asignar tratamientos a una especialidad

Cada especialidad se muestra como un grupo desplegable con los
tratamientos que tiene asignados (código, nombre, categoría y precio).
Un grupo final, **Sin especialidad**, reúne los tratamientos que
todavía no están clasificados, para ver de un vistazo lo que falta.

Con el botón **Asignar tratamientos** (solo administradores) se abre un
listado buscable de todo el catálogo con casillas de selección. Lo que
se guarda es la selección completa: los tratamientos que se desmarcan
pierden la asignación a esa especialidad.

Un tratamiento puede pertenecer a varias especialidades a la vez (una
extracción simple puede ser odontología general y cirugía oral), por lo
que aparecerá en cada uno de los grupos correspondientes.

Los tratamientos inactivos solo aparecen en el listado de asignación si
ya estaban asignados, para poder retirarlos sin reactivarlos.

## Añadir una especialidad

El botón **Nueva Especialidad** ofrece primero las **reconocidas que la clínica
todavía no tiene** —Radiología y Diagnóstico por Imagen, Patología Oral,
Medicina Oral, Dolor Orofacial y ATM, Odontología del Sueño, Prótesis Dental de
laboratorio, Odontogeriatría—. Se añaden de un toque y llegan con su nombre en
los dos idiomas. Debajo sigue el campo de texto libre, para lo que una lista no
puede anticipar.

No vienen sembradas a propósito: ninguna clínica las usa todas, y meterlas en
todos los selectores sería el mismo estorbo que un catálogo lleno de
tratamientos que no se ofrecen.

**La misma especialidad no se puede tener dos veces.** Si escribes un nombre que
ya existe, el formulario lo dice antes de enviar nada y no deja guardar. No es
una manía de orden: al profesional se le etiqueta con una fila y a los
tratamientos con la otra, y entonces el filtro *Solo lo que mi equipo realiza*
deja de encontrarlos sin que nada explique por qué. Los acentos y las
mayúsculas no hacen una especialidad distinta, ni tampoco el idioma:
«Endodontics» es la misma que «Endodoncia».

Si la que choca está **desactivada**, el aviso lo dice y ofrece **reactivarla**.
Ese caso importa: desactivar esconde la fila, no sus tratamientos asignados, así
que crear otra con el mismo nombre dejaría la mitad viva vacía y las
asignaciones varadas en una fila que no se ve.

## Especialidades sembradas

La clínica arranca con diez especialidades base: Odontología General, Higiene
Dental, Endodoncia, Periodoncia, Cirugía Oral y Maxilofacial, Implantología,
Ortodoncia, Odontopediatría, Estética Dental y Rehabilitación Oral. Se pueden
renombrar, desactivar o ampliar (Radiología, Patología Oral, Odontología del
Sueño, ...) sin romper nada: la siembra las reconoce por una clave interna, no
por el nombre visible.

Los tratamientos del catálogo llegan ya clasificados. La asignación parte de la
categoría y se afina por tratamiento donde la categoría se queda corta: la
Implantología reúne el implante (Cirugía), su corona (Restauradora) y la
sobredentadura (Prótesis) — tres categorías, una disciplina. Las carillas son
Restauradora pero además Estética. Los mantenimientos periodontales suman
Higiene Dental.

Volver a sembrar solo rellena huecos: nunca borra las asignaciones que hayas
hecho a mano.

## El listado está entero

La pestaña **Tipo de Tratamiento** carga el catálogo completo y lo agrupa por
categoría. Ya no pagina: una agrupación solo se puede leer sobre la lista
entera, y el buscador y el filtro de categoría recortan lo cargado al
instante, sin volver a preguntar al servidor.

El número junto al título cuenta **las filas que hay debajo**. Con un filtro
puesto dice *«12 de 136»*.

Esto ha sido un fallo dos veces. La primera, el paginador ignoraba los clics y
solo se veía la primera página. La segunda fue peor porque no se notaba: la
pantalla pedía «500 tratamientos» a un listado que sirve como mucho 100, así
que dibujaba 100 de los 136 de la clínica —Diagnóstico, Periodoncia y Estética
enteras sin aparecer, Endodoncia con 6 de sus 10— y los encabezaba con el
número 136. Qué categorías faltaban dependía del orden interno de sus
identificadores, así que no seguía ningún patrón reconocible, y la vista
agrupada no tiene paginador con el que llegar a lo que faltaba.

Por eso el listado ya no pide «todo» en una página: lo recorre hasta agotarlo,
y el contador cuenta lo que llegó, nunca lo que debería haber llegado.

## «La realiza»: una o varias

Un tratamiento pertenece a **todas las disciplinas que lo realizan**, no a una.
Una corona sobre implante es Implantología y Rehabilitación Oral; una carilla
es Restauradora por dónde se archiva y Estética por para qué se hace. 48 de los
136 tratamientos sembrados llevan más de una especialidad.

El campo del formulario es de selección múltiple y **guarda el conjunto
completo**. Antes era un desplegable simple, y eso borraba datos sin avisar: al
abrir la ficha se quedaba con la primera especialidad y al guardar mandaba solo
esa, de modo que abrir una corona para cambiarle el precio la dejaba con una de
sus tres. La superviviente era siempre la más genérica —la lista llega por
antigüedad—, así que retocar precios iba vaciando Implantología dentro de
Odontología General, y con ella la pestaña *Por Especialidad* y el filtro
*Solo lo que mi equipo realiza*.

En el **alta**, el tipo de tratamiento propone la especialidad, la fase y el
ámbito, y se cambian si en tu clínica lo hace otra. En un tratamiento **ya
guardado**, cambiar el tipo no toca ninguna de las tres: eso ya lo decidiste tú.

## Editar tratamientos

Los tratamientos que vienen con el sistema son **editables**: precio, nombre,
duración, IVA, categoría, especialidades y fase. Y también se pueden
**borrar**, no solo desactivar: una clínica no ofrece todo lo que trae el
catálogo de partida.

La papelera está en la fila, también en los tratamientos marcados como
**Sistema**. Durante un tiempo no estuvo: la API ya aceptaba borrarlos y el
botón seguía escondido justo en ellos, y como en una clínica recién creada
*todo* el catálogo es de sistema, no aparecía ni una vez.

La baja es lógica: la ficha no se destruye, porque los tratamientos ya
ejecutados, las líneas de presupuesto y las plantillas de plan la referencian.
Lo que hace es desaparecer de todos los selectores — buscador del catálogo,
barra del odontograma, presupuestos.

**Y se puede deshacer.** El interruptor **«Mostrar inactivos y eliminados»**,
junto al buscador, trae de vuelta a la lista lo que ya no se ofrece: lo
eliminado sale marcado *Eliminado* y con un botón **Restaurar**; lo
desactivado, marcado *Inactivo*. Sin ese interruptor las dos cosas eran
inalcanzables desde la única pantalla que puede editarlas — y un tratamiento
eliminado **conserva su código interno ocupado**, así que tampoco se podía
volver a crear con el mismo código.

Volver a sembrar el catálogo tampoco lo resucita: la siembra reconoce que la
ficha sigue ahí y no la toca.

*Desactivar* sigue siendo la opción intermedia: el tratamiento deja de
ofrecerse, pero conserva su precio y su configuración para cuando vuelva.

Crear, editar y borrar tratamientos requiere el permiso `catalog.write`, y
gestionar categorías, tipos de IVA y especialidades requiere `catalog.admin`.
**Por defecto solo el perfil administrador tiene ninguno de los dos**, así que
en la práctica es el único que puede modificar el catálogo. Los demás
perfiles ven el catálogo en modo lectura.

El único campo bloqueado en un tratamiento del sistema es el **código interno**:
es la clave por la que la siembra reconoce el tratamiento, y cambiarlo haría que
la siguiente siembra recreara el original como duplicado.

## Poner tus precios

El precio se cambia **en la propia tabla**: pulsa la cifra, escribe la tuya y
Enter. La fila se actualiza sola, así que se puede bajar por la columna sin que
la lista se mueva bajo el cursor.

Es el primer trabajo de una clínica que empieza —el catálogo de partida trae
136 tratamientos con precios de ejemplo— y hasta ahora era un formulario por
tratamiento: abrir, buscar el campo, guardar, esperar al listado, buscar la
siguiente fila.

Escapar (`Esc`) cancela, y dejar la casilla vacía no pone el precio a cero: un
tratamiento sin precio no es lo mismo que uno gratis, y el plan de tratamiento
distingue las dos cosas.

Los tratamientos **cobrados por sesiones** llevan un icono de capas y no se
editan ahí: su total es la suma de sus sesiones, y eso se cambia desde la
ficha. En el catálogo de partida son siete.

## Columna "Visible"

Cada tratamiento tiene una casilla **Visible** que decide si aparece en el
menú **Tratamientos**. Es la misma casilla en las dos pestañas: si la marcas
en "Tipo de Tratamiento", aparece marcada en "Por Especialidad".

**No confundir con activo/inactivo.** Ocultar un tratamiento solo lo quita de
esa lista de consulta; sigue activo y facturable, y sigue funcionando en
presupuestos, odontograma e histórico. Para dejar de ofrecerlo de verdad,
desactívalo.

Todos los tratamientos nacen visibles. Solo el administrador puede cambiar la
casilla.
