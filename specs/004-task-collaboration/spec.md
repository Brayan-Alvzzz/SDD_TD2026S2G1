# Feature Specification: Colaboración entre Usuarios (Incremento 4)

**Feature Branch**: `004-task-collaboration`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Especifica el incremento 4 de TaskControl: colaboración entre usuarios, cubriendo HU-10 y HU-11 del backlog. Un usuario autenticado puede asignar una tarea propia a otro usuario existente; el destinatario ve la tarea en su listado; cada cambio de asignación queda auditado con actor y timestamp; el destinatario recibe una notificación interna de asignación, puede consultarla y marcarla como leída. Fuera de alcance: incremento 5 y drag-and-drop. Se preserva el comportamiento existente de completar sin recargar."

> Esta especificación construye sobre los Incrementos 1–3 (autenticación, CRUD de tareas, ciclo de vida con soft delete y reapertura, prioridad, categorías, vencimiento). Respeta la constitución: lógica de asignación en servicios de dominio (I), autorización y validación en backend con contratos JSON explícitos (II), pruebas unitarias y de integración incluyendo accesos denegados (III), auditoría inmutable con actor y timestamp ISO 8601 (IV) y solución mínima (V).

## Clarifications

### Session 2026-10-05

- Q: ¿Qué puede hacer el asignado sobre la tarea? (D1/D2) → A: Ver, cambiar estado (iniciar/completar) y reabrir. No edita campos, no elimina, no asigna/reasigna/desasigna. El propietario conserva control total (editar, eliminar, asignar, reasignar, desasignar, completar, reabrir). La propiedad nunca cambia al asignar.
- Q: ¿Cómo se presentan tareas propias y asignadas? (D3) → A: Un solo listado con insignia de rol ("Propia", "Asignada por X", "Asignada a Y") y filtro por rol (todas / propias / asignadas a mí / delegadas por mí), combinable con los filtros de estado y orden existentes.
- Q: ¿Qué significa "usuario activo"? (D6) → A: Usuario existente: cualquier cuenta registrada. No se añade campo de estado ni migración para ello en este incremento.
- Q: ¿Qué pasa con las notificaciones leídas? (D4) → A: Se conservan con estado leída/no leída, no se borran; no leídas primero; el contador cuenta solo no leídas.
- Q: ¿Qué se muestra de una notificación antigua cuando el destinatario perdió acceso a la tarea (reasignación, desasignación, eliminación)? → A: Se conserva como historial pero solo muestra un mensaje fijo guardado en la propia notificación (fecha y usuario que asignó), marcada "ya no disponible", sin enlace, sin título actual ni datos vivos de la tarea. Todo acceso a la tarea se autoriza siempre con la relación vigente (propietario o asignado actual), nunca por la existencia de una notificación. Si vuelve a ser asignado, recibe una notificación nueva.
- Q: ¿Quién reasigna/desasigna y a quién se notifica? (D5) → A: Solo el propietario. Reasignar notifica únicamente al nuevo asignado; el asignado saliente no recibe notificación. Desasignar no notifica. Ambos se auditan con anterior/nuevo.
- Q: ¿Asignaciones repetidas y autoasignación? (D5) → A: Asignar al asignado actual es idempotente (éxito sin cambios, sin auditoría ni notificación). Autoasignación se rechaza con error de validación (400); para quitar al asignado se usa desasignar.

## Matriz de Permisos

| Operación | Propietario | Asignado vigente | Otro usuario |
|-----------|:-----------:|:----------------:|:------------:|
| Ver tarea | Sí | Sí | No (404) |
| Editar título/descripción/fecha/prioridad/categoría | Sí | No (403) | No (404) |
| Cambiar estado (iniciar/completar) | Sí | Sí | No (404) |
| Reabrir | Sí | Sí | No (404) |
| Eliminar (soft delete) | Sí | No (403) | No (404) |
| Asignar / reasignar / desasignar | Sí | No (403) | No (404) |
| Listar notificaciones propias / marcar leída | Solo las suyas | Solo las suyas | Solo las suyas (ajenas: 404) |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Asignar una tarea propia a otro usuario (HU-10) (Priority: P1)

Como usuario autenticado y propietario de una tarea, quiero asignarla a otro usuario existente del sistema para delegar el trabajo, y que el destinatario la vea en su listado.

**Why this priority**: Es el núcleo de la colaboración; HU-11 depende de ella.

**Independent Test**: Con dos usuarios A y B, A crea una tarea y la asigna a B; B inicia sesión y la ve en su listado; el historial de auditoría contiene el evento con actor A y timestamp.

**Acceptance Scenarios**:

1. **Given** A es propietario de una tarea activa sin asignado y B es un usuario existente distinto de A, **When** A asigna la tarea a B, **Then** el sistema guarda la asignación, responde con éxito y la tarea aparece en el listado de B.
2. **Given** la tarea fue asignada a B, **When** A consulta su propio listado, **Then** la tarea sigue apareciendo en el listado de A y muestra que está asignada a B.
3. **Given** la asignación a B se realizó, **When** se consulta la auditoría de la tarea, **Then** existe un registro de asignación con actor A, asignado anterior (ninguno), asignado nuevo B y timestamp ISO 8601 UTC.
4. **Given** A intenta asignar a un identificador/correo de usuario inexistente, **When** envía la solicitud, **Then** se rechaza con error de validación, la tarea no cambia y no se audita ni notifica.
5. **Given** A intenta asignarse la tarea a sí mismo, **When** envía la solicitud, **Then** se rechaza con error de validación sin cambios.
6. **Given** la tarea ya está asignada a B, **When** A la reasigna a C, **Then** el asignado pasa a C, desaparece del listado de B, aparece en el de C y se audita (anterior B, nuevo C).
7. **Given** la tarea está asignada a B, **When** A la desasigna, **Then** la tarea deja de aparecer en el listado de B, permanece en el de A y se audita (anterior B, nuevo ninguno).
8. **Given** la tarea ya está asignada a B, **When** A vuelve a asignarla a B, **Then** la operación no produce cambios, ni nuevo registro de auditoría, ni nueva notificación.

---

### User Story 2 - Notificación interna de asignación (HU-11) (Priority: P2)

Como usuario asignado, quiero recibir una notificación dentro de la aplicación cuando me asignan una tarea, poder consultarla y marcarla como leída, para enterarme sin revisar manualmente.

**Why this priority**: Mejora la experiencia de la delegación pero la asignación funciona sin ella (HU-11 es *Could*).

**Independent Test**: Tras asignar una tarea a B, B consulta sus notificaciones y encuentra una no leída con quién asignó y qué tarea; la marca como leída y el contador de no leídas baja en uno.

**Acceptance Scenarios**:

1. **Given** A asigna una tarea a B, **When** la asignación se confirma, **Then** se crea exactamente una notificación no leída para B con referencia a la tarea, al usuario que asignó y al momento de la asignación.
2. **Given** B tiene notificaciones, **When** consulta su lista, **Then** ve solo las suyas, las no leídas primero y el contador de no leídas.
3. **Given** B tiene una notificación no leída, **When** la marca como leída, **Then** pasa a leída, el contador disminuye en uno y la notificación sigue consultable.
4. **Given** una notificación ya leída, **When** B la marca de nuevo como leída, **Then** la operación es idempotente y no falla.
5. **Given** una asignación revertida o rechazada por validación, **When** se consultan las notificaciones, **Then** no existe notificación para ella (la notificación y la asignación se confirman o fallan juntas).
6. **Given** B perdió acceso a la tarea (reasignada a C, desasignada o eliminada lógicamente), **When** B consulta sus notificaciones, **Then** la notificación antigua sigue en su historial con el mensaje fijo almacenado (fecha y usuario que asignó), marcada "ya no disponible", sin enlace, sin título actual ni datos vivos de la tarea.
7. **Given** B tiene una notificación "ya no disponible", **When** intenta acceder directamente a la tarea (por identificador), **Then** se rechaza con 404 porque la autorización depende de la relación vigente y no de la notificación; aun así puede marcar la notificación como leída.
8. **Given** B perdió acceso y luego A vuelve a asignarle la tarea, **When** B consulta sus notificaciones, **Then** existe una notificación nueva con acceso vigente, y la antigua permanece "ya no disponible".

---

### User Story 3 - Acceso restringido a la colaboración (Priority: P1)

Como usuario, quiero que solo quienes corresponden puedan asignar, ver o modificar tareas y notificaciones, para que la colaboración no exponga datos ajenos.

**Why this priority**: Es un requisito de seguridad transversal a US1 y US2.

**Independent Test**: Con usuarios A (propietario), B (asignado) y C (ajeno), se verifica que cada acción no permitida es rechazada y no altera datos.

**Acceptance Scenarios**:

1. **Given** una petición sin sesión, **When** intenta asignar, listar o marcar notificaciones, **Then** se deniega con respuesta no autenticada y sin cambios.
2. **Given** C no es propietario ni asignado, **When** intenta asignar, reasignar, desasignar o consultar una tarea de A, **Then** se rechaza sin revelar si la tarea existe.
3. **Given** B es asignado (no propietario), **When** intenta asignar, reasignar, desasignar, editar campos o eliminar la tarea, **Then** se rechaza con 403 y sin cambios (ver Matriz de Permisos); en cambio puede cambiar su estado y reabrirla.
4. **Given** una notificación de B, **When** A o C intenta consultarla o marcarla como leída, **Then** se rechaza sin cambios.
5. **Given** una tarea eliminada lógicamente, **When** su propietario intenta asignarla, **Then** se rechaza y no se asigna.
6. **Given** un cuerpo de solicitud que intenta fijar propietario, actor o destinatario de notificación, **When** se procesa, **Then** el servidor ignora esos valores y usa la sesión autenticada.

---

### User Story 4 - Asignado trabaja la tarea sin recargar (Priority: P3)

Como usuario asignado, quiero cambiar el estado de una tarea asignada (completarla, reabrirla) con la misma experiencia sin recarga de página que ya existe.

**Why this priority**: Protege el comportamiento existente al ampliar el listado con tareas ajenas.

**Independent Test**: B marca como completada una tarea asignada desde su listado; la fila se actualiza sin recargar; si el servidor falla, la interfaz revierte el cambio y muestra el error.

**Acceptance Scenarios**:

1. **Given** B ve una tarea asignada pendiente, **When** la completa desde el listado, **Then** la interfaz se actualiza de inmediato sin recargar y el servidor confirma el estado.
2. **Given** la petición de cambio de estado falla, **When** la interfaz recibe el error, **Then** revierte el cambio visual y muestra un mensaje claro (comportamiento existente preservado).
3. **Given** B completa la tarea, **When** A consulta su listado, **Then** A ve el estado actualizado y el cambio queda auditado con B como actor.
4. **Given** tareas propias existentes, **When** el usuario completa una, **Then** el comportamiento es idéntico al de los incrementos anteriores.

---

### Edge Cases

- Asignación concurrente de la misma tarea a dos usuarios distintos: gana una sola, la otra queda como reasignación auditada o es rechazada; nunca existen dos asignados.
- Asignar mientras el destinatario ha sido eliminado/inexistente: rechazo por validación sin cambios parciales.
- Fallo al registrar la auditoría o la notificación: toda la operación se revierte (consistente con el patrón transaccional existente).
- Migración sobre datos existentes: las tareas previas quedan sin asignado y sin notificaciones, sin perder datos.
- Tarea completada asignada: puede reasignarse por el propietario; el asignado puede reabrirla.
- Notificación antigua tras perder acceso: se conserva como historial sin enlace ni datos vivos (ver FR-020b/FR-020c).
- El propietario asignado a otro sigue pudiendo editar, completar y eliminar la tarea (la eliminación la quita también del listado del asignado).
- Una categoría y prioridad pertenecen al propietario; el asignado las ve pero no las modifica ni usa sus categorías para filtrar tareas ajenas.
- Notificaciones acumuladas: la lista debe seguir siendo utilizable con muchas notificaciones leídas (orden y límite razonable de visualización).

## Requirements *(mandatory)*

### Functional Requirements

**Asignación (HU-10)**

- **FR-001**: Un usuario autenticado DEBE poder asignar una tarea activa de su propiedad a otro usuario existente.
- **FR-002**: Una tarea DEBE tener como máximo un asignado a la vez; el propietario nunca cambia por asignar.
- **FR-003**: El sistema DEBE rechazar la asignación a usuarios inexistentes y a sí mismo, sin cambios parciales.
- **FR-004**: “Usuario activo” DEBE interpretarse como usuario existente (cuenta registrada); no se añade campo de estado a las cuentas. El sistema DEBE rechazar destinatarios que no existan.
- **FR-005**: Solo el propietario DEBE poder reasignar la tarea a otro usuario existente y desasignarla. Reasignar notifica solo al nuevo asignado; desasignar y el asignado saliente no generan notificación.
- **FR-006**: Asignar a un usuario que ya es el asignado actual DEBE responder éxito sin cambios (idempotente) y NO DEBE producir auditoría ni notificación; la autoasignación (propietario a sí mismo) DEBE rechazarse con error de validación (400).
- **FR-007**: El listado de tareas del asignado DEBE incluir las tareas asignadas a él, activas, respetando filtros por estado y ordenamiento existentes.
- **FR-008**: El listado del propietario DEBE seguir incluyendo sus tareas asignadas a otros e indicar el asignado actual.
- **FR-009**: El listado DEBE distinguir visualmente tareas propias de asignadas y permitir filtrar por rol (propias, asignadas a mí, asignadas a otros).
- **FR-010**: El asignado vigente DEBE poder ver la tarea, cambiar su estado y reabrirla; NO DEBE poder editar campos, eliminarla ni asignar/reasignar/desasignar (403). El propietario conserva todos los permisos. Ver Matriz de Permisos.
- **FR-011**: Solo propietario y asignado DEBEN poder consultar la tarea; cualquier otro usuario DEBE recibir rechazo que no revele su existencia.
- **FR-012**: Una tarea eliminada lógicamente DEBE dejar de aparecer en el listado del asignado y NO DEBE poder asignarse.

**Auditoría**

- **FR-013**: Toda asignación, reasignación y desasignación DEBE registrarse en la auditoría con acción dedicada, actor, asignado anterior, asignado nuevo y timestamp ISO 8601 UTC.
- **FR-014**: Los registros de auditoría existentes DEBEN conservarse íntegros y los nuevos son inmutables.
- **FR-015**: Los cambios de estado realizados por el asignado DEBEN auditarse con el asignado como actor.
- **FR-016**: Asignación, auditoría y notificación DEBEN confirmarse o revertirse como una sola operación.

**Notificaciones (HU-11)**

- **FR-017**: Cada asignación o reasignación efectiva DEBE crear exactamente una notificación interna no leída para el nuevo asignado, con tarea, usuario que asignó y momento.
- **FR-018**: El usuario DEBE poder consultar sus notificaciones (solo las suyas), con las no leídas primero, y ver el número de no leídas.
- **FR-019**: El usuario DEBE poder marcar una notificación propia como leída; la operación es idempotente.
- **FR-020**: Las notificaciones leídas DEBEN conservarse y seguir consultables (D4).
- **FR-020b**: Cada notificación DEBE almacenar un mensaje fijo propio (fecha y usuario que asignó). Cuando el destinatario ya no es el asignado vigente o la tarea fue eliminada lógicamente, la notificación DEBE mostrarse como “ya no disponible”, sin enlace, título actual ni datos de la tarea.
- **FR-020c**: El acceso a una tarea DEBE autorizarse siempre por la relación vigente (propietario o asignado actual); la existencia, lectura o conservación de una notificación NUNCA DEBE otorgar acceso.
- **FR-021**: Ningún usuario DEBE poder ver ni modificar notificaciones ajenas.

**Transversales**

- **FR-022**: Todas las operaciones nuevas DEBEN validar sesión y autorización en backend y exponer contratos JSON con códigos HTTP semánticos (400 validación, 401 sin sesión, 403 sin permiso, 404 no encontrado).
- **FR-023**: El comportamiento existente de completar tareas sin recargar, con actualización optimista y rollback ante error, DEBE preservarse para tareas propias y asignadas.
- **FR-024**: La migración DEBE conservar todos los datos existentes; las tareas previas quedan sin asignado.
- **FR-025**: Quedan fuera de alcance: Incremento 5, drag-and-drop, notificaciones por correo/push, múltiples asignados, transferencia de propiedad, comentarios y equipos/grupos.

### Key Entities

- **Usuario**: cuenta existente; puede ser propietario de tareas, asignado y destinatario de notificaciones. Sin estado de actividad propio (ver FR-004).
- **Tarea**: conserva su propietario; gana un asignado opcional (referencia a otro usuario).
- **Registro de Auditoría de Asignación**: evento inmutable con tarea, actor, asignado anterior y nuevo, timestamp.
- **Notificación**: mensaje interno para un usuario destinatario con referencia a la tarea, usuario que asignó, momento, mensaje fijo almacenado y estado leída/no leída; su disponibilidad (con enlace o “ya no disponible”) se deriva de la relación vigente del destinatario con la tarea.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las tareas asignadas aparece en el listado del asignado en su siguiente consulta, sin acción adicional.
- **SC-002**: El 100% de los cambios de asignación genera exactamente un registro de auditoría con actor y timestamp, y las asignaciones inválidas generan cero.
- **SC-003**: El 100% de las asignaciones efectivas genera exactamente una notificación; las repetidas o inválidas generan cero.
- **SC-004**: En las pruebas de acceso con tres usuarios (propietario, asignado, ajeno), el 100% de las acciones no autorizadas es rechazado sin alterar datos.
- **SC-005**: Un usuario puede asignar una tarea y el destinatario puede consultar y marcar como leída su notificación, cada flujo en menos de 1 minuto de interacción.
- **SC-006**: La suite existente (156 pruebas) sigue pasando completa y completar tareas sigue actualizándose sin recargar la página.
- **SC-007**: Tras la migración, el 100% de los usuarios, tareas y registros de auditoría previos se conserva idéntico.
- **SC-008**: En el 100% de los casos en que un destinatario perdió acceso (reasignación, desasignación, eliminación), su notificación antigua no muestra enlace ni datos vivos de la tarea, y cualquier acceso directo a la tarea es rechazado.

## Assumptions

- Los incrementos 1–3 están implementados; se reutilizan autenticación por sesión, auditoría y soft delete.
- Las decisiones D1–D6 quedaron resueltas en la sesión de clarificación del 2026-10-05.
- Los usuarios se identifican al asignar por correo registrado; no se implementa directorio o búsqueda avanzada de usuarios.
- Las notificaciones son internas y se consultan al cargar la aplicación; no hay entrega en tiempo real ni correo.
- Las prioridades, categorías y fecha límite siguen siendo atributos exclusivos del propietario.
- Esquema nuevo mediante migración Alembic consecutiva a la 003, con datos previos preservados.
