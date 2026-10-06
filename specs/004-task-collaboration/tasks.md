# Tareas de Implementación: Colaboración entre Usuarios (Incremento 4)

Este documento contiene las tareas organizadas por fases y casos de uso, siguiendo la especificación, el plan y los contratos actuales. Las pruebas se escriben antes de la implementación, garantizando que fallen inicialmente por funcionalidad ausente (RED) antes de pasar (GREEN).

## Phase 1: Setup & Regression Baseline

**Purpose**: Verificación de la base existente antes de comenzar.

- [x] T001 Verificar que las 156 pruebas base pasan correctamente (`docs/evidencias/base/pytest-corregido.txt`).

---

## Phase 2: Foundational (Migración, Permisos y Repositorios Base)

**Purpose**: Infraestructura central necesaria para las historias de usuario (Migración 004, Repositorio de Notificaciones y Matriz de permisos).

### Tests (RED)
- [x] T002 [F1] Escribir prueba de integración `tests/integration/test_migrations.py` para la migración 004 (preservación de datos, `assignee_id` NULL, tabla `notifications`, nuevas acciones de auditoría y *pre-flight check* de bloqueo de downgrade sin pérdida de datos). Guardar salida RED en `docs/evidencias/inc4/red-f1.txt`.
- [x] T003 [F2] Escribir prueba unitaria `tests/unit/test_permissions.py` para la matriz completa (3 roles × 6 operaciones). Guardar salida RED en `docs/evidencias/inc4/permisos-red.txt`.
- [x] T004 [F1] Escribir prueba unitaria en `tests/unit/test_notification_repository.py` para verificar la inserción base y la vista lógica `available`. Guardar salida RED en `docs/evidencias/inc4/red-repo.txt`.

### Implementation
- [x] T005 [F1] Actualizar modelos en `src/domain/models.py` y `src/infrastructure/models.py` (`Task`, `TaskORM`, `Notification`, `NotificationORM`) y restricciones de `AuditLogORM`.
- [x] T006 [F1] Crear la migración `migrations/versions/<rev>_004_task_collaboration.py` con `assignee_id`, tabla `notifications`, ampliación del `CHECK` de auditoría, y el *pre-flight check* para proteger el downgrade.
- [x] T007 [F1] Implementar `NotificationRepository` en `src/infrastructure/repositories.py` para que esté disponible para la transacción del servicio de asignación.
- [x] T008 [F2] Implementar `src/domain/permissions.py` y añadir `TaskNotAccessibleError`, `OperationNotPermittedError` en `src/domain/exceptions.py`.

### Checkpoint (GREEN)
- [x] T009 [F1] Ejecutar pruebas de migración/repositorio y guardar GREEN en `docs/evidencias/inc4/repositorio-green-corregido.txt`.
- [x] T010 [F2] Ejecutar pruebas de permisos y guardar GREEN en `docs/evidencias/inc4/permisos-green.txt` (Regresión corregida confirmada con 174 passed).

---

## Phase 3: User Story 1 - Asignación y Listado (US1) (Priority: P1)

**Goal**: HU-10. Un usuario autenticado puede asignar una tarea propia a otro usuario existente.
**Requirements**: FR-001 al FR-009, FR-013 al FR-016, SC-001 al SC-003.

### Tests (RED)
- [x] T011 [P] [US1] Escribir pruebas unitarias en `tests/unit/test_collaboration_service.py` (RED guardado en `docs/evidencias/inc4/red-us1.txt`) y pruebas de integración en `tests/integration/test_assignment_routes.py` (RED guardado en `docs/evidencias/inc4/rutas-asignacion-red.txt`).
- [x] T012 [P] [US1] Escribir pruebas de rollback transaccional en `tests/integration/test_collaboration_rollback.py` (atomicidad de la asignación+auditoría+notificación).
- [ ] T013 [P] [US1] Escribir pruebas de listado en `tests/integration/test_task_list_roles.py` sin duplicados y con filtros de rol combinados. Guardar salida RED en `docs/evidencias/inc4/red-list.txt`.

### Implementation
- [x] T014 [P] [US1] Implementar en `src/infrastructure/repositories.py` la actualización condicional (CAS) de `assignee_id` con validación de concurrencia (409) (FR-016).
- [x] T015 [US1] Implementar `CollaborationService.assign_task` y `unassign_task` en `src/domain/services.py` asegurando la validación del destinatario y la transacción única (requiere `NotificationRepository` de la Fase 2).
- [x] T016 [US1] Implementar endpoints PUT y DELETE `/api/tasks/<id>/assignee` en `src/web/task_routes.py` según el contrato JSON (FR-022).
- [ ] T017 [US1] Implementar `TaskRepository.list_visible` en `src/infrastructure/repositories.py` (una sola consulta, sin N+1, filtro de roles).
- [ ] T018 [US1] Actualizar `GET /api/tasks` en `src/web/task_routes.py` y la plantilla `src/web/templates/tasks/list.html` con las insignias y filtros correspondientes.

### Checkpoint (GREEN)
- [x] T019 [US1] Ejecutar pruebas de asignación y guardar GREEN en `docs/evidencias/inc4/green-us1.txt`.
- [ ] T020 [US1] Ejecutar pruebas de listado y guardar GREEN en `docs/evidencias/inc4/green-list.txt`.

---

## Phase 4: User Story 3 - Acceso restringido (US3) (Priority: P1)

**Goal**: Solo quienes correspondan pueden consultar/modificar tareas y la autorización es siempre en backend por la relación vigente.
**Requirements**: FR-010 al FR-012, SC-004.

### Tests (RED)
- [ ] T021 [US3] Escribir pruebas de integración sobre lectura, cambio de estado, edición y eliminación para validar respuestas 403 y 404 a usuarios ajenos o asignados sin permiso completo. Guardar salida RED en `docs/evidencias/inc4/red-us3.txt`.

### Implementation
- [ ] T022 [US3] Añadir `TaskService._load_for` en `src/domain/services.py` delegando la autorización en `permissions.py`.
- [ ] T023 [US3] Actualizar rutas de detalle, cambio de estado y reapertura en `src/web/task_routes.py` para usar `_load_for` en vez de `get_task`.
- [ ] T024 [US3] Crear la vista HTML de solo lectura `src/web/templates/tasks/detail.html`.

### Checkpoint (GREEN)
- [ ] T025 [US3] Ejecutar pruebas de acceso y guardar GREEN en `docs/evidencias/inc4/green-us3.txt`.

---

## Phase 5: User Story 2 - Notificaciones internas (US2) (Priority: P2)

**Goal**: HU-11. Notificaciones persistentes con mensaje fijo y acceso derivado.
**Requirements**: FR-017 al FR-021, SC-005, SC-008.

### Tests (RED)
- [ ] T026 [US2] Escribir pruebas en `tests/integration/test_notification_routes.py` (idempotencia de lectura, acceso denegado a ajenas, y disponibilidad derivada). Guardar RED en `docs/evidencias/inc4/red-us2.txt`.

### Implementation
- [ ] T027 [P] [US2] Actualizar el procesador de contexto en `src/web/app.py` para inyectar el contador de no leídas en la barra superior (requiere que el `NotificationRepository` de la Fase 2 esté terminado).
- [ ] T028 [US2] Implementar rutas `GET /api/notifications` y `POST /api/notifications/<id>/read` en `src/web/notification_routes.py` (HTML y API).
- [ ] T029 [US2] Crear la plantilla `src/web/templates/notifications/list.html` manejando el estado "ya no disponible" sin enlaces a tareas perdidas.

### Checkpoint (GREEN)
- [ ] T030 [US2] Ejecutar pruebas de notificaciones y guardar GREEN en `docs/evidencias/inc4/green-us2.txt`.

---

## Phase 6: User Story 4 - UI sin recarga (US4) (Priority: P3)

**Goal**: Experiencia fluida asíncrona; recuperación ante error y visibilidad según `data-viewer-role`.
**Requirements**: FR-023, SC-006.

### Tests (Manual & JS Verification)
- [ ] T031 [US4] Actualizar `src/web/static/js/tasks.js` para extraer `data-viewer-role` del DOM e inyectar dinámicamente solo los botones permitidos (propietario vs asignado).
- [ ] T032 [P] [US4] Implementar `src/web/static/js/assignment.js` para gestionar modal de asignación y llamadas PUT/DELETE a la API de US1 con rollback visual ante fallo.
- [ ] T033 [P] [US4] Implementar `src/web/static/js/notifications.js` para marcar notificaciones como leídas de forma asíncrona.
- [ ] T034 [US4] Verificación manual: completar y reabrir una tarea ajena desde el listado sin recargar la página. Si la red falla, la UI debe revertir el checkbox y mostrar alerta.

---

## Final Phase: Polish & Regression

**Purpose**: Verificación de toda la base y de los nuevos compromisos juntos.

- [ ] T035 Revisión final del contrato JSON con las rutas implementadas (todos los endpoints responden a la misma semántica de error).
- [ ] T036 Ejecutar toda la suite combinada (deben pasar la 156 existentes más las nuevas), verificando que ninguna de las viejas fue debilitada o borrada.
- [ ] T037 Guardar salida final GREEN consolidada en `docs/evidencias/inc4/green-final.txt`.

---

## Dependencies & Execution Order

- **Foundational (Phase 2)** bloquea el avance hacia las historias. Migración, Repositorio de Notificaciones y base de permisos son obligatorios antes que las rutas o servicios.
- **US1 (Asignación/Listado)** depende de **Phase 2**, ya que inyecta la auditoría y notificación empleando el repositorio. Bloquea las pruebas de integración natural de **US2**.
- **US3 (Acceso Restringido)** puede hacerse en paralelo a **US2** (rutas diferentes), pero depende de **US1** para tener datos de contexto y la columna de asignación poblada.
- **US4 (JS)** depende de que el HTML y la API de US1, US2 y US3 estén completamente implementados, por lo que va al final, previo a la regresión.

### Resumen de Alcance del Incremento y MVP
**Atención:** Ninguna entrega del incremento 4 se considera completa ni MVP válido sin abarcar HU-10 y HU-11 integradas. Es decir, las fases 3, 4 y 5 son obligatorias para cumplir la especificación del incremento (Asignaciones, Permisos y Notificaciones respectivamente). Las etapas individuales son únicamente hitos de desarrollo progresivos.
