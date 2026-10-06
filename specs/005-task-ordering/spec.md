# Feature Specification: task-ordering

**Feature Branch**: `005-task-ordering`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Especifica el incremento 5 de TaskControl: HU-15 (completar tareas sin recargar) y HU-16 (reordenar tareas mediante drag and drop con persistencia en backend)."

## Clarifications

### Session 2026-10-06

- Q: Alcance de tareas a ordenar (FR-007) → A: Solo se reordenan tareas cuyo propietario es el usuario autenticado (incluidas las delegadas). Las tareas asignadas por otro propietario no se reordenan.
- Q: Convivencia con filtros y ordenamientos (FR-008) → A: Drag and drop exclusivo en la vista "Mis tareas" (`role=owned`) sin filtros de estado o categoría. En otras vistas se deshabilita y explica cómo activarlo. Tareas nuevas van al final; tareas eliminadas reducen el orden relativo.
- Q: Concurrencia de sesiones (FR-009) → A: "Last write wins", pero con validación estricta de IDs completos. Se rechazan transacciones con IDs faltantes (por creaciones/eliminaciones recientes), ajenos, duplicados o eliminados.
- Q: Endpoint de persistencia de orden → A: Se adopta `PATCH /api/tasks/order` para resolver explícitamente la contradicción de la guía.
- Q: Implementación de HU-15 → A: Se conserva mediante pruebas existentes, sin reimplementación.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Completar sin recargar (HU-15) (Priority: P1)

Como usuario, quiero marcar una tarea como completada sin recargar la página, para una experiencia fluida.

**Why this priority**: Mejora inmediata en la usabilidad y reduce latencia percibida al interactuar con el sistema, alineado con el núcleo de TaskControl.

**Independent Test**: Can be fully tested by marking a task complete directly on the list and verifying the visual update and backend persistence without a full page reload.

**Acceptance Scenarios**:

1. **Given** el usuario está viendo su lista de tareas y la tarea está "pendiente", **When** marca la tarea como completada, **Then** la tarea se muestra visualmente completada de inmediato, y se envía la actualización al backend en segundo plano.
2. **Given** la actualización en segundo plano falla (por fallo de red o error HTTP), **When** el usuario intenta completar la tarea, **Then** el estado visual se revierte al anterior ("pendiente") y se muestra un mensaje de error claro, permitiendo reintentar.
3. **Given** el usuario es el propietario o el asignado de la tarea, **When** solicita completar la tarea sin recargar, **Then** se aplican las mismas reglas de permisos que existían (ambos pueden completarla y auditarla correctamente).

### User Story 2 - Reordenar tareas con Drag and Drop (HU-16) (Priority: P1)

Como usuario, quiero reordenar tareas arrastrándolas (drag and drop), para ajustar la prioridad y el orden visualmente según mis necesidades.

**Why this priority**: Introduce la capacidad organizativa visual que otorga flexibilidad al listado principal.

**Independent Test**: Can be fully tested by dragging a task to a new position, refreshing the page, and seeing the order persist.

**Acceptance Scenarios**:

1. **Given** un listado de tareas propias sin filtros adicionales (`role=owned`), **When** el usuario arrastra y suelta una tarea en una nueva posición, **Then** el orden visual se actualiza inmediatamente y se envía la solicitud de persistencia al backend de forma atómica.
2. **Given** un fallo de red durante el guardado del nuevo orden, **When** el usuario suelta la tarea, **Then** el orden visual se revierte al estado anterior (seguro) y se notifica del error al usuario.
3. **Given** un intento de reordenamiento sobre tareas que no pertenecen al usuario (asignadas) o han sido eliminadas, **When** el frontend envía la orden al backend, **Then** el backend rechaza la solicitud (aislamiento de seguridad) y el frontend revierte el cambio.

### Edge Cases

- **Nuevas tareas**: Al crear una tarea nueva, esta recibe automáticamente la última posición en el orden manual.
- **Eliminación de tareas**: Al borrar una tarea, el orden relativo de las tareas restantes se mantiene inalterado sin dejar huecos funcionales.
- **Concurrencia con tareas alteradas**: Si el usuario intenta guardar un nuevo orden pero otra sesión eliminó o creó una tarea recientemente (los IDs enviados no coinciden con los IDs vivos del servidor), la operación se rechaza por estar desactualizada (409 Conflict) para obligar a recargar la vista y no guardar cambios parciales.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir completar tareas de forma asíncrona usando la API existente y manejando respuestas de error revirtiendo el DOM.
- **FR-002**: El sistema DEBE exponer una interfaz drag-and-drop (nativa o ligera) para reordenar las tareas visualmente, sin requerir re-renderizados completos (SPA frameworks).
- **FR-003**: El sistema DEBE actualizar el orden de visualización de las tareas inmediatamente en el frontend de forma optimista (optimistic UI).
- **FR-004**: El sistema DEBE persistir atómicamente el orden manual modificado en el backend de forma segura y eficiente.
- **FR-005**: El sistema DEBE validar estrictamente en el backend que el reordenamiento es solicitado por un usuario con permisos válidos y excluye tareas eliminadas o inválidas.
- **FR-006**: El sistema DEBE revertir de forma fiable el orden en el DOM y mostrar una alerta al usuario si la persistencia en el backend falla (HTTP error o desconexión).
- **FR-007**: El sistema DEBE restringir el ordenamiento manual exclusivamente a tareas cuyo propietario es el usuario autenticado (incluyendo aquellas delegadas a otra persona). Las tareas asignadas por otro propietario no se reordenan.
- **FR-008**: El sistema DEBE habilitar Drag and Drop exclusivamente en la vista "Mis tareas" (`role=owned`), ordenadas manualmente y sin filtros activos (como estado o categoría). En vistas mixtas, asignadas, filtradas o con orden por prioridad, el arrastre DEBE estar deshabilitado, mostrando un breve mensaje indicando cómo activar el orden manual. El orden persistido se conserva al cambiar de vista.
- **FR-009**: El sistema DEBE resolver conflictos de sesiones concurrentes aplicando que "gana la última transacción confirmada". La transacción DEBE validarse de forma estricta (todo o nada), rechazándose si incluye IDs ajenos, eliminados, duplicados o un conjunto desactualizado (omite tareas recién creadas).

### Key Entities

- **Task**: Requiere persistencia del criterio de ordenación manual de forma estructural (ej: nuevo atributo `display_order` o índice específico).
- **Endpoint de Orden**: Se adopta un endpoint específico `PATCH /api/tasks/order` como ampliación mínima necesaria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los reordenamientos persistidos con éxito sobreviven recargas de página completas y cambios de sesión.
- **SC-002**: Ante caídas de conexión, el sistema revierte el cambio visual (drag & drop) al instante, sin falsas confirmaciones y con notificación clara de fallo.
- **SC-003**: Se mantiene el asilamiento de usuario absoluto (0% de tareas ajenas, eliminadas o compartidas sin permiso pueden ser manipuladas u ordenadas de forma espuria).

## Assumptions

- HU-15 (Completar sin recargar) ya está cubierta en el Incremento 4. Se conserva mediante las pruebas existentes y no requiere una implementación nueva.
- Contradicción en guías ("no introducir endpoints" vs "nuevo o extendido"): Documentado y resuelto adoptando un endpoint específico `PATCH /api/tasks/order` como ampliación mínima necesaria. El contrato detallado se definirá en el plan.
