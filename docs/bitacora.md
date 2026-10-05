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
