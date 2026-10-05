# Feature Specification: Organización y Priorización de Tareas (Incremento 3)

**Feature Branch**: `003-task-organization-prioritization`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Especifica el tercer incremento funcional de TaskControl: organización y priorización de tareas. Este incremento cubre HU-07, HU-08 y HU-09 del backlog, y asume que los Incrementos 1 y 2 ya están implementados. Alcance funcional: 1. Prioridad de tareas (HU-07): toda tarea tiene una prioridad (alta, media, baja) con un valor por defecto definido explícitamente. El listado de tareas (ya existente desde HU-02) se puede ordenar por prioridad, además de los filtros por estado ya existentes. Un usuario puede cambiar la prioridad de una tarea propia en cualquier momento. 2. Categorías o proyectos (HU-08): un usuario puede crear categorías para agrupar tareas relacionadas. Una tarea pertenece a máximo una categoría (o a ninguna). Eliminar una categoría no elimina las tareas que pertenecían a ella — quedan sin categoría, nunca se eliminan en cascada. 3. Indicación de tareas vencidas (HU-09): el sistema calcula si una tarea está vencida (fecha límite superada y no completada) y lo expone en el listado. Este cálculo se hace exclusivamente en el backend, nunca en JavaScript, para evitar inconsistencias por zona horaria del cliente. Una tarea eliminada o completada nunca se marca como vencida aunque su fecha límite haya pasado. Fuera de alcance explícito de este incremento: asignación y notificaciones (HU-10, HU-11), interacción sin recarga de página y drag-and-drop (HU-15, HU-16). Esta especificación debe ser consistente con la constitución del proyecto: separación de capas al introducir el nuevo concepto de categoría como entidad propia (Principio II), y cálculo de vencimiento resuelto en el backend como parte del contrato de datos que recibe el frontend (Principio III)."

---

## Observaciones de Gobernanza y Alcance

> [!NOTE]
> **Alineación con la Constitución del Proyecto y Alcance Delimitado**:
> 1. **Modularidad y Núcleo de Dominio Independiente (Principio I)**: La nueva entidad `Categoría` y la lógica de validación de prioridades pertenecen al núcleo de dominio, independientes de la capa web y persistencia.
> 2. **Autoridad Estricta del Backend y Contratos Explícitos (Principio II)**: El cálculo del estado de vencimiento (`is_overdue`) y la ordenación por prioridad / filtrado son resueltos exclusivamente por el backend como parte del contrato de datos entregado a la interfaz. No se delega la determinación de vencimiento a la lógica de presentación del cliente para evitar inconsistencias causadas por desfases de reloj o zona horaria local.
> 3. **Definición Estricta de Fecha Límite y Vencimiento**: En la aplicación existente, la fecha límite (`due_date`) es una fecha en formato `YYYY-MM-DD` sin componente de hora. Una tarea se considera vencida si y solo si su `due_date` es estrictamente anterior a la fecha actual del servidor calculada en UTC (`due_date < fecha_actual_utc`). Una tarea cuya fecha límite sea el día de hoy **aún no está vencida**. No se requiere ninguna conversión de datos preexistentes.
> 4. **Trazabilidad, Auditoría e Inmutabilidad del Historial (Principio IV)**: Todo cambio en la prioridad o categoría de una tarea genera un registro inmutable en el historial de auditoría. La eliminación de categorías es segura y no afecta la integridad ni la existencia de las tareas asociadas (desvinculación sin cascada).
> 5. **Simplicidad y YAGNI (Principio V)**: Se implementa estrictamente lo solicitado por el backlog. Quedan explícitamente fuera de alcance:
>    - Renombrar o editar categorías existentes (solo creación, listado y eliminación).
>    - Ordenar tareas por categoría (el ordenamiento aplica exclusivamente sobre prioridad y los filtros existentes).
>    - Asignación multi-usuario y notificaciones internas (HU-10, HU-11).
>    - Interacción sin recarga o arrastrar y soltar (drag-and-drop) (HU-15, HU-16).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prioridad de Tareas y Ordenamiento (HU-07) (Priority: P1)

Como usuario registrado y autenticado, quiero asignar un nivel de prioridad explícito (alta, media, baja) a cada una de mis tareas y ordenar mi listado por dicho criterio, para enfocar mi tiempo y esfuerzo en el trabajo más crítico y urgente.

**Why this priority**: Es la base del valor de priorización en la gestión personal de tareas. Permite al usuario clasificar de inmediato sus pendientes sin requerir configuraciones adicionales y optimizar el orden en que aborda sus actividades cotidianas.

**Independent Test**: Un usuario puede crear tareas seleccionando su prioridad (o adoptando el valor por defecto "media"), modificar la prioridad de cualquier tarea existente desde el formulario de edición o controles del listado, y ordenar la tabla/vista de tareas por prioridad (mostrando primero las de prioridad alta), comprobando que el orden responde de forma consistente y verificable.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado en el formulario de creación de tarea, **When** no selecciona explícitamente un nivel de prioridad, **Then** el sistema asigna de forma automática y explícita la prioridad predeterminada "media".
2. **Given** un usuario autenticado creando o editando una tarea propia, **When** selecciona explícitamente entre "alta", "media" o "baja", **Then** el sistema almacena la prioridad indicada y la muestra en la vista detallada y en el listado con un distintivo visual correspondiente.
3. **Given** un usuario consultando su listado de tareas sin seleccionar un criterio de ordenamiento explícito, **When** se presenta la vista, **Then** el sistema conserva el orden cronológico por fecha de creación de forma descendente (`created_at DESC`) como comportamiento predeterminado, preservando el comportamiento previo.
4. **Given** un usuario con tareas de diversas prioridades en su listado, **When** selecciona explícitamente la opción de ordenar por prioridad, **Then** el sistema presenta el listado situando en primer lugar las tareas de prioridad "alta", seguidas por "media" y finalizando con "baja" (o en orden inverso si se invierte el criterio).
5. **Given** un usuario que aplica simultáneamente un filtro por estado (ej. "en progreso") y ordenamiento explícito por prioridad, **When** se visualiza el listado, **Then** el sistema respeta ambos criterios simultáneamente, mostrando solo tareas en el estado seleccionado ordenadas por su nivel de prioridad.
6. **Given** un usuario autenticado modificando la prioridad de una tarea propia, **When** guarda el cambio, **Then** el sistema registra un evento en el log de auditoría con la acción `priority_change`, el usuario actor y los detalles del cambio (prioridad anterior y nueva).
7. **Given** un usuario intentando asignar un valor de prioridad no reconocido por el sistema (ej. "urgente" o "ninguna"), **When** envía la solicitud, **Then** el sistema rechaza la operación con un error de validación claro sin modificar los datos existentes.

---

### User Story 2 - Categorías de Tareas sin Eliminación en Cascada (HU-08) (Priority: P2)

Como usuario registrado y autenticado, quiero crear categorías o proyectos personalizados para agrupar tareas relacionadas, y poder eliminar una categoría cuando ya no sea útil sin temor a perder las tareas que contenía, para mantener mi trabajo estructurado de manera flexible y segura.

**Why this priority**: Facilita la organización temático-contextual de tareas personales (trabajo, personal, estudio, proyectos específicos). Garantiza la seguridad de los datos al impedir pérdidas accidentales de tareas cuando una categoría se da de baja.

**Independent Test**: Un usuario crea una categoría "Proyecto Alfa", asigna dos tareas a dicha categoría y comprueba que puede filtrar su listado para ver únicamente las tareas de "Proyecto Alfa". Posteriormente elimina la categoría "Proyecto Alfa": las dos tareas continúan existiendo en el sistema pero ahora figuran "sin categoría", conservando intactos sus estados, prioridades e historial de auditoría.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado en la sección de categorías, **When** ingresa un nombre válido (entre 1 y 50 caracteres) y solicita crear la categoría, **Then** el sistema crea la categoría asociada exclusivamente a dicho usuario y la pone a disposición para clasificar tareas.
2. **Given** un usuario intentando crear una categoría con un nombre que ya posee entre sus categorías activas, **When** envía el formulario, **Then** el sistema rechaza la creación informando que ya posee una categoría con ese nombre.
3. **Given** dos usuarios distintos en el sistema, **When** ambos crean una categoría con el mismo nombre (ej. "Trabajo"), **Then** el sistema permite ambas creaciones de forma aislada, asegurando que ningún usuario pueda ver, asignar ni modificar las categorías del otro.
4. **Given** un usuario creando o editando una tarea propia, **When** selecciona una de sus categorías existentes o la opción "Sin categoría", **Then** el sistema vincula la tarea a dicha categoría (o la desvincula si se selecciona ninguna). Cada tarea pertenece a un máximo de una categoría.
5. **Given** un usuario con tareas asociadas a una categoría determinada, **When** el usuario elimina dicha categoría y confirma la acción, **Then** la categoría se elimina, pero todas las tareas que le pertenecían permanecen intactas en el sistema pasando al estado "Sin categoría" (sin eliminación en cascada).
6. **Given** el listado principal de tareas, **When** el usuario filtra por una categoría específica, **Then** el sistema presenta únicamente las tareas activas pertenecientes a dicha categoría, permitiendo combinar este filtro con el estado y la ordenación por prioridad.

---

### User Story 3 - Indicación Visual Confiable de Tareas Vencidas en el Backend (HU-09) (Priority: P3)

Como usuario registrado y autenticado, quiero que el sistema identifique y resalte de manera inequívoca las tareas cuya fecha límite ha expirado y que aún no han sido completadas, para reaccionar oportunamente ante retrasos sin discrepancias provocadas por la configuración o zona horaria de mi dispositivo.

**Why this priority**: Permite al usuario detectar compromisos incumplidos o en riesgo inminente de forma confiable. Al calcularse estrictamente en el backend en una escala temporal estandarizada, se elimina cualquier riesgo de falsos positivos o falsos negativos derivados del reloj local del navegador.

**Independent Test**: Se crean tareas con distintas combinaciones de fechas límites (`due_date` en formato `YYYY-MM-DD`) y estados. Una tarea con fecha límite de ayer o anterior en estado "pendiente" o "en progreso" se muestra con el indicador destacado de "Vencida". Una tarea cuya fecha límite sea la fecha de hoy se muestra como no vencida. Al cambiar su estado a "completada", el indicador de vencimiento desaparece de inmediato. Una tarea eliminada lógicamente nunca figura como vencida ni aparece en el listado activo. Tareas sin fecha límite jamás se marcan como vencidas.

**Acceptance Scenarios**:

1. **Given** una tarea activa (no eliminada) en estado "pendiente" o "en progreso" cuya fecha límite (`due_date`, formato `YYYY-MM-DD`) es estrictamente anterior a la fecha actual del sistema calculada en UTC, **When** se consulta el listado o detalle de la tarea, **Then** el sistema incluye en su contrato de datos el indicador `is_overdue = true` y la interfaz despliega un distintivo visual destacado de advertencia (ej. etiqueta roja "Vencida").
2. **Given** una tarea activa en estado "pendiente" o "en progreso" cuya fecha límite (`due_date`) coincide con la fecha actual del sistema calculada en UTC (la fecha de hoy), **When** se consulta el listado o detalle, **Then** el sistema computa `is_overdue = false` y la interfaz no despliega advertencia de vencimiento, pues la fecha límite aún no ha sido superada.
3. **Given** una tarea cuya fecha límite ha pasado pero su estado es "completada", **When** se consulta el listado o detalle, **Then** el sistema computa `is_overdue = false` y la interfaz no muestra advertencia de vencimiento.
4. **Given** una tarea cuya fecha límite ha pasado pero ha sido eliminada lógicamente (soft deleted), **When** se evalúa el estado del sistema, **Then** no se considera vencida ni se expone en los listados regulares de trabajo.
5. **Given** una tarea que no tiene fecha límite asignada (`due_date` nula o vacía), **When** se consulta en el listado, **Then** el sistema computa `is_overdue = false` y se presenta sin indicador de vencimiento.
6. **Given** una tarea actualmente vencida con advertencia visual, **When** el usuario actualiza su estado a "completada", **Then** el sistema recalcula en el backend su condición y la respuesta refleja inmediatamente que la tarea ha dejado de estar vencida.
7. **Given** una consulta al servicio o endpoint del listado de tareas, **When** se entregan los datos de cada tarea, **Then** la condición de vencimiento es entregada ya calculada por el backend como un atributo booleano explícito del contrato (`is_overdue`), sin requerir comparaciones de fechas en el cliente.

---

### Edge Cases

- **Tarea con fecha límite para el día de hoy**: Dado que `due_date` es una fecha `YYYY-MM-DD` sin componente horario, el sistema evalúa estrictamente `due_date < fecha_actual_utc`. Si `due_date` es igual a la fecha de hoy en UTC, la tarea todavía no está vencida. Pasa a considerarse vencida únicamente al día siguiente.
- **Categoría eliminada mientras un formulario de tarea está abierto**: Si un usuario intenta asociar una categoría que acaba de ser eliminada, el sistema rechaza la asociación con un mensaje claro y la tarea queda sin categoría.
- **Intento de asociar una categoría ajena**: Si mediante manipulación de datos se envía un identificador de categoría perteneciente a otro usuario, el sistema rechaza la operación con error de autorización o validación y no efectúa la asociación.
- **Cambio de prioridad concurrente con cambio de estado**: El sistema procesa la modificación atómicamente, validando ambos campos y registrando los eventos de auditoría correspondientes sin dejar estados intermedios inconsistentes.
- **Listado con tareas sin categoría y con categoría**: Al aplicar filtros por categoría en el listado, se debe permitir seleccionar específicamente "Sin categoría" para consultar las tareas no agrupadas sin que queden ocultas.
- **Reapertura de una tarea completada cuya fecha límite ya pasó**: Al reabrirse (volviendo a estado "pendiente" conforme a HU-06), el backend recalcula inmediatamente su vencimiento y la tarea pasa a mostrarse como "Vencida".

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Toda tarea en el sistema DEBE poseer un nivel de prioridad obligatorio restringido a tres valores válidos: "alta", "media" y "baja".
- **FR-002**: Al crearse una tarea sin especificar prioridad, el sistema DEBE asignar automáticamente y de forma explícita el valor predeterminado "media".
- **FR-003**: El usuario propietario de una tarea DEBE poder modificar su nivel de prioridad en cualquier momento, ya sea durante la edición integral de la tarea o mediante acciones en la interfaz.
- **FR-004**: Toda modificación en el nivel de prioridad de una tarea DEBE generar un registro en el log de auditoría persistente con acción `priority_change`, registrando el actor, la tarea y los valores anterior y nuevo.
- **FR-005**: El listado de tareas DEBE conservar de forma predeterminada el orden cronológico descendente por fecha de creación (`created_at DESC`), y DEBE permitir al usuario seleccionar explícitamente ordenar sus tareas activas por nivel de prioridad, situando en tal caso las tareas de prioridad alta en primer lugar ("alta" > "media" > "baja", o en orden inverso si se invierte el criterio).
- **FR-006**: La opción de ordenamiento por prioridad DEBE ser combinable con los filtros de estado existentes ("todas", "pendiente", "en_progreso", "completada") sin anularse mutuamente.
- **FR-007**: El sistema DEBE permitir a los usuarios autenticados crear, consultar y eliminar categorías personales para la organización de sus tareas.
- **FR-008**: Cada categoría DEBE poseer un nombre obligatorio no vacío (máximo 50 caracteres) y pertenecer de forma aislada al usuario creador. No se permiten nombres de categoría duplicados para un mismo usuario.
- **FR-009**: Cada tarea DEBE poder asociarse a lo sumo a una categoría activa perteneciente al mismo usuario propietario, o permanecer sin categoría asignada (`category_id = NULL`).
- **FR-010**: La eliminación de una categoría DEBE desvincular automáticamente todas las tareas asociadas a ella, dejándolas en estado "Sin categoría" (`category_id = NULL`), garantizando que ninguna tarea se elimine en cascada.
- **FR-011**: El listado de tareas DEBE ofrecer un mecanismo de filtrado por categoría, permitiendo al usuario ver tareas de una categoría específica, ver todas o ver aquellas que no tienen categoría asignada.
- **FR-012**: El sistema DEBE calcular el estado de vencimiento (`is_overdue`) exclusivamente en la capa de backend para toda tarea activa.
- **FR-013**: Una tarea DEBE considerarse vencida (`is_overdue = true`) si y solo si cumple simultáneamente las siguientes condiciones evaluadas en el backend:
  1. Posee una fecha límite asignada (`due_date` no nula, formato `YYYY-MM-DD`).
  2. La fecha límite es estrictamente anterior a la fecha actual del sistema calculada en UTC (`due_date < fecha_actual_utc`). Una tarea cuya fecha límite sea la fecha de hoy en UTC NO se considera vencida.
  3. Su estado no es "completada".
  4. No ha sido eliminada lógicamente (`is_deleted = false`).
- **FR-014**: El backend DEBE exponer el resultado del cálculo de vencimiento (`is_overdue`) como parte del contrato de datos de la tarea tanto en vistas web renderizadas como en respuestas JSON.
- **FR-015**: La interfaz de usuario DEBE resaltar visualmente las tareas vencidas mediante una advertencia o distintivo visual claro y perceptible, basado directamente en el valor computado por el backend.
- **FR-016**: Si una tarea vencida es completada por el usuario, el sistema DEBE actualizar su condición de forma inmediata para que no figure como vencida.
- **FR-017**: Si una tarea completada cuya fecha límite ha expirado es reabierta (HU-06), el sistema DEBE reevaluarla automáticamente y presentarla como vencida.
- **FR-018**: El sistema DEBE validar rigurosamente la autorización multi-usuario: un usuario no puede consultar, asignar ni eliminar categorías o tareas pertenecientes a otros usuarios.
- **FR-019**: Toda asignación o cambio explícito de categoría en una tarea DEBE registrarse en el log de auditoría persistente con la acción `category_change`.

---

### Key Entities *(include if feature involves data)*

- **Task (Tarea)**:
  - Entidad central de trabajo que mantiene su campo `due_date` existente en formato de fecha `YYYY-MM-DD` (sin hora) y evoluciona con dos nuevos atributos:
    - `priority`: Nivel de prioridad ("alta", "media", "baja"), obligatorio, por defecto "media".
    - `category_id`: Identificador de la categoría a la que pertenece la tarea (opcional / nullable).
    - `is_overdue`: Propiedad computada en el backend (booleana), no persistida directamente como columna fija, evaluada dinámicamente comparando si `due_date < fecha_actual_utc`, siempre que el estado no sea "completada" y la tarea no esté eliminada.
- **Category (Categoría)**:
  - Nueva entidad de dominio independiente que representa una agrupación temática o proyecto:
    - `id`: Identificador único numérico.
    - `user_id`: Identificador del usuario propietario (garantiza aislamiento multi-usuario).
    - `name`: Nombre descriptivo de la categoría (1 a 50 caracteres, único por usuario).
    - `created_at`: Marca temporal de creación en formato estándar ISO 8601 en UTC.
- **AuditLog (Registro de Auditoría)**:
  - Entidad de auditoría inmutable que registra eventos de ciclo de vida. La restricción de acciones permitidas se amplía de forma segura en la base de datos para admitir `priority_change` y `category_change`, conservando íntegramente las acciones previas (`create`, `update`, `status_change`, `delete`, `reopen`).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las tareas creadas sin selección explícita de prioridad se almacenan y muestran con la prioridad predeterminada "media".
- **SC-002**: Cuando el usuario no selecciona un ordenamiento explícito, el 100% de las tareas se presentan ordenadas cronológicamente por fecha de creación descendente (`created_at DESC`); únicamente al seleccionar explícitamente ordenar por prioridad, el 100% de las tareas se presentan respetando estrictamente la jerarquía ("alta" primero, "media" en segundo término y "baja" al final, o viceversa si se solicita orden inverso).
- **SC-003**: Al eliminar una categoría con tareas asignadas, el 100% de dichas tareas permanecen activas en el sistema con su categoría desvinculada (`category_id = NULL`) sin pérdida de información de las tareas ni eliminación en cascada.
- **SC-004**: El 100% de los cálculos de vencimiento se resuelven en el backend comparando la fecha límite contra la fecha actual en UTC; ninguna verificación en el cliente genera discrepancias por diferencias de huso horario local o desfases del reloj del navegador.
- **SC-005**: Las tareas cuya fecha límite sea la fecha de hoy en UTC registran un 0% de clasificaciones erróneas como vencidas.
- **SC-006**: Las tareas completadas o eliminadas lógicamente registran una tasa del 0% de falsos positivos en la condición de vencidas, independientemente de cuándo haya expirado su fecha límite original.
- **SC-007**: La navegación, ordenamiento por prioridad y filtrado por estado o categoría en el listado de tareas responde de forma ágil, completando la presentación de resultados en menos de 1 segundo para un volumen habitual de tareas personales.

---

## Assumptions

- **Formato existente de fecha límite**: El campo `due_date` ya existe en la aplicación almacenado como fecha en formato textual `YYYY-MM-DD` sin componente de hora. No requiere migración ni conversión de datos históricos.
- **Compatibilidad con tareas existentes (Incrementos 1 y 2)**: Todas las tareas preexistentes recibirán el valor de prioridad por defecto "media" y permanecerán sin categoría asignada (`category_id = NULL`), preservando la continuidad operativa del sistema sin necesidad de intervención manual del usuario.
- **Relación 1 a N**: Una tarea solo puede pertenecer a una categoría a la vez. No se contemplan etiquetas múltiples ni jerarquías de categorías (conforme al Principio V: Simplicidad y YAGNI).
- **Límites de alcance explícitos**: No se contemplan funciones accesorias no requeridas en el backlog, tales como renombrar categorías o reordenar el listado por categoría.
