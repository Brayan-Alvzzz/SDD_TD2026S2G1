# Bitácora

## 2026-10-05 — Fallo de reproducibilidad en `test_migration_preserves_existing_data`

- **Fallo:** `tests/integration/test_migrations.py::test_migration_preserves_existing_data`
  fallaba (suite: 155 passed, 1 failed).
- **Causa:** la prueba copiaba `taskcontrol_backup.db` o `taskcontrol.db`, archivos
  locales que no están versionados y no existen tras clonar el repositorio.
  Fallaba en el `assert os.path.exists(...)`.
- **Corrección:** la prueba ahora crea una base SQLite temporal en `tmp_path`, la
  migra con Alembic hasta la revisión 001, inserta usuarios, tareas y registros de
  auditoría de ejemplo, ejecuta `upgrade` hasta head y verifica que:
  - los registros originales de `users`, `tasks` y `audit_logs` se conservan
    íntegros (comparación fila a fila, no solo conteos);
  - los campos nuevos tienen los valores esperados: `is_deleted=0`,
    `deleted_at=NULL`, `priority='media'`, `category_id=NULL`.
- **Alcance:** solo se modificó esta prueba; no se omitió ni se debilitaron sus
  comprobaciones (son más estrictas que antes).
- **Resultado:** la prueba pasa y la suite completa da 156 passed.

## 2026-10-05 — Incremento 4 (colaboración): especificación, clarificación y plan

Registro de decisiones tomadas en esta sesión. No se ejecutaron pruebas de este incremento ni se implementó código.

### Correcciones previas al plan
- `specs/004-task-collaboration/checklists/requirements.md`: se reemplazó la referencia obsoleta a "valores provisionales D1–D6" por una referencia a la sesión de clarificación del 2026-10-05.
- `specs/004-task-collaboration/spec.md`: FR-005b y FR-006 eran redundantes; se fusionaron en FR-006 (asignar al asignado actual es idempotente sin auditoría ni notificación; autoasignación rechazada con 400). FR-005b no era referenciado por otros requisitos.

### Decisiones de clarificación (D1–D6)
- D1/D2: el propietario conserva el control total y la propiedad no cambia al asignar. El asignado puede ver, cambiar estado y reabrir; no edita, elimina ni asigna/reasigna/desasigna.
- D3: un solo listado con insignia de rol y filtro por rol.
- D6: "usuario activo" = usuario existente; no se añade campo de estado ni migración para ello.
- D4: las notificaciones leídas se conservan.
- Notificación antigua sin acceso: se conserva como historial con mensaje fijo, marcada "ya no disponible", sin enlace ni datos vivos; el acceso a la tarea se autoriza siempre por la relación vigente.
- D5: solo el propietario reasigna o desasigna; reasignar notifica solo al nuevo asignado; desasignar no notifica; asignación repetida idempotente; autoasignación rechazada (400).

### Decisiones de diseño del plan
- Asignado como columna `tasks.assignee_id` distinta de `user_id` (propietario).
- Política de permisos por operación en `permissions.py`; `get_task` no se amplía (sigue solo-propietario) y se añade una carga con autorización por operación solo para lectura, cambio de estado y reapertura.
- Ajeno → 404 y asignado sin permiso → 403, mediante subclases de `UnauthorizedError` para no romper pruebas existentes. Cambia de 403 a 404 la respuesta JSON de PUT/PATCH sobre tareas ajenas; queda marcado para revisión explícita.
- Asignación, auditoría y notificación en una sola transacción, con actualización condicional para concurrencia (409).
- Nuevas acciones de auditoría `assign`, `reassign`, `unassign`; migración 004 con recreación del CHECK de `audit_logs`. Downgrade con chequeo previo (pre-flight) para detener la reversión sin pérdida de datos si existen colaboraciones activas o eventos de auditoría nuevos.
- Distinción estricta de usuarios en la API: el actor y su filtro de notificaciones provienen siempre de la sesión; el destinatario de la asignación y notificación se validan a partir del input, ignorando user_id/actor_id en el cuerpo de la solicitud.
- Disponibilidad de notificaciones derivada de la relación vigente y de la regla "última notificación por (tarea, destinatario)"; nueva vista de solo lectura `GET /tasks/<id>`.
- Listado único con una consulta y filtro de categoría restringido a tareas propias.
- Estrategia TDD: pruebas primero con salidas reales de pytest guardadas en `docs/evidencias/inc4/` (RED y GREEN por fase) y regresión de las 156 pruebas existentes.
- Fuera de alcance: Incremento 5 y drag-and-drop.

Artefactos: `specs/004-task-collaboration/{spec.md, plan.md, research.md, data-model.md, quickstart.md, contracts/task-collaboration-api.json}`.

### Correcciones post-análisis (speckit-analyze)
- **C1 (Dependencias):** Se adelantó la creación y prueba de `NotificationRepository` a la Fase 2 (Fundacional) para que esté disponible antes de implementar el servicio de asignación en la Fase 3, resolviendo la dependencia cruzada en la transacción atómica. La tarea duplicada en US2 fue eliminada.
- **C2 (Alcance MVP):** Se corrigió la sugerencia de MVP en `tasks.md`, aclarando que ninguna entrega del Incremento 4 se considera completa sin las historias HU-10 y HU-11 integradas; las etapas intermedias son hitos de desarrollo progresivos, no entregables funcionales finales.
- **C3 (Dependencia temporal):** Se explicitó en la Fase 5 que la inyección del contador de notificaciones no leídas en el procesador de contexto de Flask (`app.py`) requiere estrictamente que el repositorio de notificaciones esté finalizado.

## 2026-10-05 — Implementación Incremento 4: Fase 1 y 2 (Pruebas RED)

- Se completaron las tareas **T001** y **T002** según `tasks.md`.
- **T001:** Se tomó como base el resultado previo de 156 pruebas exitosas en `docs/evidencias/base/pytest-corregido.txt` sin requerir re-ejecución, puesto que no hubo cambios en el código de producción.
- **T002:** Se escribió la prueba de integración `test_migration_004_task_collaboration` en `tests/integration/test_migrations.py`.
  - Configura una base temporal, migra hasta la revisión 003, e inserta datos sintéticos de usuarios y tareas.
  - Simula la ejecución hasta `head` y verifica: existencia de `assignee_id` (NULL por defecto), creación de tabla `notifications`, y validación del nuevo `CHECK` de auditoría (`assign`, `unassign`, `reassign`).
  - También incluye la comprobación de error (`Exception`) en downgrade si hay asignaciones activas.
- **Resultado RED:** La ejecución intencionalmente falló en el primer assert que busca la columna `assignee_id` en `tasks`, debido a que la migración real aún no ha sido implementada. La evidencia RED se guardó en `docs/evidencias/inc4/fundacional-red.txt`.
- No se introdujeron fallos artificiales; el fallo `assert 'assignee_id' in task_cols` es producto genuino de la funcionalidad ausente (TDD puro). No se modificó el código de producción.

## 2026-10-05 — Implementación Incremento 4: Fase 2 (Migración GREEN - Incompleta)

- Se separaron las comprobaciones de T002 en 5 pruebas independientes dentro de `test_migrations.py`.
- Se implementó la tarea **T006**: creación de la migración en `migrations/versions/4cee1aa5ad3f_004_task_collaboration.py`.
- Las pruebas pasaron a GREEN, sin embargo, una revisión posterior indicó **cobertura incompleta** (incumplimientos frente a `data-model.md`).

## 2026-10-05 — Corrección TDD de Migración 004 (Contrato Completo)

- **Corrección de Pruebas (RED):** Se actualizaron las 5 pruebas de integración para ser exhaustivas frente a `data-model.md`.
  - Se verificaron las columnas correctas en `notifications` (`recipient_id`, `actor_id`, `read_at`).
  - Se validaron longitudes y la restricción `CHECK` sobre `type`.
  - Se exigió la existencia de los 3 índices de rendimiento (`idx_tasks_assignee`, `idx_notifications_recipient`, `idx_notifications_task_recipient`).
  - Se validó que el downgrade bloqueado mantenga la versión de Alembic intacta y que el downgrade permitido revierta el CHECK y elimine índices/tablas.
  - **Resultado:** Fallo real documentado en `docs/evidencias/inc4/migracion-contrato-red.txt`.
- **Corrección de Implementación (GREEN):** Se reescribió `upgrade()` en `migrations/versions/4cee1aa5ad3f_004_task_collaboration.py` para construir el esquema idéntico a `data-model.md`. Se ajustó el `downgrade()` para limpiar correctamente los índices de `tasks`.
  - **Resultado:** Ejecución exitosa documentada en `docs/evidencias/inc4/migracion-contrato-green.txt`.
- **Regresión Final:** Se corrió la suite global tras las correcciones, alcanzando 161/161 sin afectaciones, documentada en `docs/evidencias/inc4/regresion-migracion-corregida.txt`.
- Esto completa definitiva y exhaustivamente las tareas T002, T006 y el subconjunto migratorio de T009.

## 2026-10-05 — Implementación Incremento 4: Fase 2 (Pruebas RED de Permisos)

- Se completó la tarea **T003** según `tasks.md`.
- **T003:** Se escribieron las pruebas unitarias para la política de permisos en `tests/unit/test_permissions.py`.
  - Se probaron 5 escenarios principales cubriendo la matriz:
    1. Propietario: Acceso total a las 6 operaciones (`VIEW`, `CHANGE_STATUS`, `REOPEN`, `EDIT`, `DELETE`, `MANAGE_ASSIGNMENT`).
    2. Asignado actual: Acceso solo a `VIEW`, `CHANGE_STATUS`, `REOPEN`. Recibe excepción (403) `OperationNotPermittedError` para el resto.
    3. Ajeno: Ningún acceso (404) `TaskNotAccessibleError` a cualquier operación.
    4. Asignado anterior (desasignado): Ningún acceso (404), vuelve a ser ajeno.
    5. Tarea eliminada: Nadie tiene acceso (404), ni propietario ni asignado.
- Adicionalmente, se integró el escenario para validar la pérdida de acceso de un asignado cuando la tarea es reasignada a otro (`test_reassigned_user_no_access`), elevando a 6 los escenarios totales.
- **Resultado RED:** Las pruebas fallan por funcionalidad ausente pura (`ImportError` de `TaskNotAccessibleError`, `OperationNotPermittedError` y `authorize` desde `src.domain.permissions`). La salida real se guardó en `docs/evidencias/inc4/permisos-red.txt`.
- Solo se escribieron las pruebas para verificar el comportamiento descrito; la funcionalidad no está verificada porque la implementación todavía no existe. No se modificó código de producción.

## 2026-10-05 — Implementación Incremento 4: Fase 2 (Permisos GREEN)

- Se completaron las tareas **T005** (parcialmente, solo dominio), **T008** y **T010** según `tasks.md`.
- **T005 (Parcial):** Se añadió el campo `assignee_id` como `Optional[int] = None` al modelo de dominio `Task` en `src/domain/models.py`, preservando compatibilidad con los usos anteriores.
- **T008:** Se implementó `src/domain/permissions.py` puro, completamente independiente de Flask/HTTP.
  - Se introdujeron las excepciones `TaskNotAccessibleError` y `OperationNotPermittedError` en `src/domain/exceptions.py`, ambas derivando de `UnauthorizedError`.
  - Se definió el enum `Operation` y la función `authorize(task, user_id, operation)` que encapsula la política restrictiva estricta en función de rol y si la tarea ha sido borrada o el asignado cambiado.
- **T010:** Se comprobó exitosamente que las 6 pruebas de roles y accesos pasaron (100% GREEN), y se registró la salida en `docs/evidencias/inc4/permisos-green.txt`.
- La regresión completa (167/167 tests aprobados) demostró que introducir el nuevo campo en `Task` no corrompió las funcionalidades preexistentes. Salida en `docs/evidencias/inc4/regresion-permisos.txt`.
