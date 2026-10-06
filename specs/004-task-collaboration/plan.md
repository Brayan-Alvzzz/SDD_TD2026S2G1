# Implementation Plan: Colaboración entre Usuarios (Incremento 4)

**Branch**: `sebastian/incrementos-4-5` (directorio de especificación `004-task-collaboration`) | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-task-collaboration/spec.md` (incluye sesión de clarificación 2026-10-05)

## Summary

Se añade una relación **asignado** (opcional, única) distinta de la de **propietario** sobre cada tarea, un registro persistente de **notificaciones internas** y tres nuevos eventos de auditoría (`assign`, `reassign`, `unassign`). La autorización se centraliza en una política pura de dominio (`permissions.py`) que decide por **operación** y **rol vigente** (propietario / asignado / ajeno); `get_task` **no se amplía**: las operaciones de edición, eliminación y asignación siguen exigiendo propietario, y solo se añaden rutas de lectura, cambio de estado y reapertura que aceptan al asignado vigente. Asignación + auditoría + notificación se confirman en una sola transacción con actualización condicional (compare-and-set). El listado pasa a ser único (propias + asignadas) con filtro por rol y sin duplicados. Las notificaciones guardan un mensaje fijo; su disponibilidad se **deriva** de la relación vigente, nunca la otorga.

## Technical Context

**Language/Version**: Python 3.13 (entorno `.venv`; la constitución exige 3.10+)

**Primary Dependencies**: Flask, Flask-SQLAlchemy / SQLAlchemy 2.x, Flask-Migrate (Alembic), Jinja2, JavaScript ES6 vanilla (sin dependencias nuevas)

**Storage**: SQLite con claves foráneas activas (`PRAGMA foreign_keys = ON`); esquema versionado por Alembic (revisión 004 consecutiva a `a6aa1e24bf8e`)

**Testing**: pytest (suite base: 156 pruebas, evidencia en `docs/evidencias/base/pytest-corregido.txt`); fixtures `app`/`db_session` con migraciones reales sobre BD temporal

**Target Platform**: Servidor web local/desarrollo (macOS/Linux/Windows), navegador moderno

**Project Type**: Aplicación web monolítica modular (dominio / infraestructura / web)

**Performance Goals**: Listado y notificaciones en una consulta indexada sin N+1; contador de no leídas con una consulta agregada indexada

**Constraints**: Backend como única autoridad (Principio II); controladores delgados (I); TDD (III); auditoría inmutable con ISO 8601 UTC (IV); YAGNI (V); sin tiempo real, sin correo, sin drag-and-drop, sin Incremento 5

**Scale/Scope**: Aplicación de equipo pequeño; sin paginación compleja (límite fijo de 50 notificaciones por consulta)

Sin marcadores `NEEDS CLARIFICATION` pendientes; las decisiones técnicas están en [research.md](./research.md).

## Constitution Check

*GATE: evaluada antes de la Fase 0 y re-evaluada tras el diseño de la Fase 1.*

| Principio | Cumplimiento en el plan | Estado |
|-----------|-------------------------|--------|
| I. Modularidad | Reglas de asignación, permisos y notificación en `src/domain` (`permissions.py`, `CollaborationService`); rutas Flask solo parsean, delegan y serializan | ✅ |
| II. Backend autoritativo y contratos | Permisos por operación en backend; contratos JSON en `contracts/`; el cliente ignora ocultar botones como seguridad; rollback visual ante error | ✅ |
| III. Test-first | Pruebas primero con evidencia RED→GREEN por historia; unitarias de dominio + integración HTTP incluyendo denegaciones | ✅ |
| IV. Trazabilidad | Eventos `assign`/`reassign`/`unassign` con actor y timestamp; sin borrado físico de notificaciones ni auditoría | ✅ |
| V. Simplicidad/YAGNI | Un asignado por tarea (columna, no tabla de historial); un tipo de notificación; destinatario por correo; sin colas ni tiempo real | ✅ |
| Seguridad | Sesión validada por petición, 404 para ajenos, validación de entradas, consultas parametrizadas, autoescape de Jinja | ✅ |
| Quality gates | Suite completa limpia, PEP 8, contratos revisados | ✅ (a verificar en implementación) |

**Re-evaluación post-diseño**: sin violaciones; no se requiere Complexity Tracking. Se señala una única decisión de revisión explícita (principio gate 4): el mapeo de acceso de ajenos a **404** en todas las rutas de tarea (ver [research.md](./research.md) R-03).

## Diseño por requisito del usuario

### 1. Propietario y asignado como relaciones distintas
- `tasks.user_id` sigue siendo el propietario (inmutable). Se añade `tasks.assignee_id` nullable (FK a `users`, `ON DELETE SET NULL`). Ver [data-model.md](./data-model.md).
- El dominio `Task` incorpora `assignee_id`, `assignee_email`, `owner_email` y `viewer_role` calculado por consulta (no persistido).

### 2. Permisos por operación en backend (sin ampliar `get_task`)
- `src/domain/permissions.py` define `Operation` (`VIEW`, `CHANGE_STATUS`, `REOPEN`, `EDIT`, `DELETE`, `MANAGE_ASSIGNMENT`) y `authorize(task, user_id, operation) -> Role` implementando la Matriz de Permisos del spec.
- Resultados: propietario → permitido; asignado vigente → permitido solo `VIEW`, `CHANGE_STATUS`, `REOPEN`, si no `OperationNotPermittedError` (403); ajeno → `TaskNotAccessibleError` (404).
- `TaskService.get_task` **permanece solo-propietario** y lo siguen usando `update_task`, `update_task_priority`, `update_task_category`, `delete_task`. Se añade `TaskService._load_for(task_id, user_id, operation)` que usan únicamente `get_task_for_view`, `update_task_status` y `reopen_task`.
- Ambas excepciones nuevas heredan de `UnauthorizedError` para no romper las 4+ pruebas unitarias existentes que esperan `UnauthorizedError`. `UnauthorizedError` simple (p. ej. categoría ajena) conserva su 403 actual.
- Estado de una tarea eliminada: sigue rechazado (404) para todos los roles.

### 3. Migración 004 (conserva datos)
- `tasks`: añade `assignee_id` + índice `idx_tasks_assignee` (`assignee_id`, `is_deleted`, `created_at`) y FK (modo batch de SQLite).
- `notifications`: tabla nueva (ver data-model).
- `audit_logs`: recreación (`recreate='always'`, igual patrón que 003) para ampliar el CHECK de `action` con `assign`, `reassign`, `unassign`; todas las filas se copian.
- Downgrade documentado: comprueba previamente que no existan datos de colaboración (asignaciones activas, notificaciones o eventos de auditoría nuevos). Si existen, detiene el proceso con un error claro para conservar el esquema y los datos sin pérdida. Si está limpio, elimina `notifications` y `assignee_id`. Documentado en la prueba prevista.
- Pruebas de migración con BD temporal en `tmp_path` (sin bases personales), mismo patrón que `test_migration_preserves_existing_data`.

### 4. Transacción única
- `CollaborationService.assign_task(task_id, actor_id, assignee_email)`:
  1. Cargar tarea y `authorize(..., MANAGE_ASSIGNMENT)`; rechazar eliminada (404).
  2. Validar correo y existencia (400); autoasignación (400); mismo asignado → retorno idempotente sin escribir.
  3. `UPDATE tasks SET assignee_id=:new WHERE id=:id AND assignee_id IS :old AND is_deleted=0`; si `rowcount == 0` → `ConflictError` (409) por concurrencia.
  4. `audit_repo.create(action=assign|reassign)`; `notification_repo.create(...)` para el nuevo asignado.
  5. Un único `session.commit()`; cualquier excepción → `session.rollback()` y se propaga (patrón idéntico a `TaskService`).
- `unassign_task` análogo (auditoría `unassign`, sin notificación).
- Las pruebas de rollback inyectan un fallo en `AuditLogRepository.create` y en `NotificationRepository.create` y verifican que ni `assignee_id`, ni auditoría ni notificaciones cambian (patrón de `test_transaction_rollback.py`).

### 5. Contratos JSON, validaciones y errores
Ver [contracts/task-collaboration-api.json](./contracts/task-collaboration-api.json). Convención existente: éxito `{"success": true, "data": …}`, error `{"success": false, "error": "…"}`.

| Endpoint | Éxito | Errores |
|----------|-------|---------|
| `PUT /api/tasks/<id>/assignee` `{assignee_email}` | 200 (`changed` true/false, `action`) | 400 validación/autoasignación/usuario inexistente; 401 sin sesión; 403 asignado sin permiso; 404 ajeno o tarea eliminada/inexistente; 409 conflicto concurrente |
| `DELETE /api/tasks/<id>/assignee` | 200 (idempotente) | 401, 403, 404 |
| `GET /api/tasks/<id>` | 200 con `viewer_role` y permisos | 401, 404 |
| `GET /api/tasks?role=` | 200 | 400 rol inválido |
| `GET /api/notifications` | 200 con `unread_count` | 401 |
| `POST /api/notifications/<id>/read` | 200 idempotente | 401, 404 (ajena o inexistente) |

Diferenciación de roles:
- Actor: usuario autenticado obtenido de la sesión.
- Destinatario de la asignación: usuario existente validado a partir del correo o dato de asignación proporcionado.
- Destinatario de la notificación: el usuario asignado ya validado.
- Consulta y marcado de notificaciones: se procesan exclusivamente las pertenecientes al usuario autenticado.

Cualquier `user_id`, `actor_id` o `recipient_id` en el cuerpo se ignora. Rutas HTML espejo: `GET /tasks/<id>` (detalle de solo lectura), `GET /notifications`, `POST /notifications/<id>/read`, `POST /tasks/<id>/assignee`.

### 6. Listado único sin duplicados
- Nuevo `TaskRepository.list_visible(user_id, role, status, sort, category_id)` con **una sola consulta** sobre `tasks` filtrando `is_deleted = 0` y `(user_id = :u OR assignee_id = :u)`; correo del propietario y del asignado por `LEFT JOIN` a alias de `users` (relaciones N:1, no multiplican filas). `list_by_user` se conserva para compatibilidad.
- `role` ∈ `all` (defecto), `owned`, `assigned_to_me`, `delegated` (propias con asignado). Combinable con `status`, `sort` y `category_id`.
- El filtro por categoría se aplica solo a tareas propias (las categorías son personales); `category_name` de tareas ajenas se muestra como solo lectura y no habilita filtros.
- Como `owner ≠ assignee` (autoasignación prohibida), ninguna tarea puede coincidir en ambas ramas del OR; aun así una prueba verifica ausencia de duplicados con tareas propias, asignadas y delegadas mezcladas y todas las combinaciones de filtros.
- Plantilla `tasks/list.html`: insignia de rol, asignado, filtro por rol; los botones **Editar/Eliminar/Asignar** solo se renderizan para el propietario (la seguridad real sigue en backend).

### 7. Notificaciones persistentes y acceso vigente
- `notifications` conserva todas las filas (leídas y no leídas). `message` es un texto fijo (fecha y correo del asignador) guardado al crear.
- Disponibilidad **derivada** al consultar: `available = tarea no eliminada ∧ tasks.assignee_id = recipient_id ∧ notification.id = MAX(id) de las notificaciones (task, recipient)`. La regla del máximo hace que, si el usuario vuelve a ser asignado, solo la notificación nueva sea navegable (escenario 8 del spec).
- Si `available` es falso: la API devuelve `available=false`, `task=null`, sin enlace ni título; el HTML muestra "ya no disponible".
- El enlace de una notificación disponible apunta a `GET /tasks/<id>`, que **autoriza siempre** con `authorize(VIEW)` sobre la relación vigente; abrir directamente esa URL desde una notificación antigua devuelve 404. Ninguna ruta de tarea consulta notificaciones.
- Marcar leída: `UPDATE … WHERE id=:id AND recipient_id=:session_user`; idempotente; ajena/inexistente → 404 sin distinguir.
- El contador de no leídas se inyecta en la barra de navegación mediante el procesador de contexto existente (una consulta indexada por petición autenticada).

### 8. Estrategia TDD (RED → GREEN → refactor)
Orden por historia; cada tanda: escribir pruebas, ejecutar, **guardar salida RED** en `docs/evidencias/inc4/red-<historia>.txt`, implementar lo mínimo, guardar **GREEN** en `docs/evidencias/inc4/green-<historia>.txt`, commit separado. Las salidas se guardan tal cual las produce `pytest`; no se editan ni se redactan resultados a mano.

| Fase | Pruebas (primero) | Implementación después |
|------|-------------------|------------------------|
| F0 Base | Verificar 156 passed antes de empezar (referencia `pytest-corregido.txt`) | — |
| F1 Migración 004 | `tests/integration/test_migrations.py`: datos 003 preservados, `assignee_id` NULL, tabla `notifications`, nuevas acciones de auditoría, downgrade | Modelos ORM + migración |
| F2 Política de permisos | `tests/unit/test_permissions.py`: matriz completa (3 roles × 6 operaciones) | `permissions.py`, excepciones |
| F3 Asignación (US1) | `tests/unit/test_collaboration_service.py` + `tests/integration/test_assignment_routes.py` | repositorios, `CollaborationService`, rutas |
| F4 Transacción | `tests/integration/test_collaboration_rollback.py` | (ya cubierto; ajustes si falla) |
| F5 Acceso (US3) | Ajeno/asignado/sin sesión/campos manipulados, edición/eliminación negadas al asignado | rutas de lectura/estado/reapertura con `_load_for` |
| F6 Listado | `tests/unit` + `tests/integration/test_task_list_roles.py`: sin duplicados, filtros combinados | `list_visible`, plantilla |
| F7 Notificaciones (US2) | Creación, lista, leer idempotente, ajenas, notificación antigua (reasignada/desasignada/eliminada/reasignada otra vez) | `NotificationRepository`, servicio, rutas, plantilla |
| F8 UI sin recarga (US4) | Contrato de estado/reapertura para asignado; atributos `data-viewer-role` en HTML; revisión manual del flujo JS | `tasks.js` consciente del rol, `notifications.js` |
| F9 Regresión | Suite completa: las **156 existentes** deben seguir pasando sin modificarlas | — |

Las pruebas existentes no se modifican ni se debilitan; si el nuevo mapeo a 404 exigiera cambiar una, se documenta en `docs/bitacora.md` y se somete a revisión antes (hoy las comprobaciones de ajenos aceptan `(403, 404)` o `404`).

## Project Structure

### Documentation (this feature)

```text
specs/004-task-collaboration/
├── spec.md
├── plan.md                                  # Este archivo
├── research.md                              # Fase 0
├── data-model.md                            # Fase 1
├── quickstart.md                            # Fase 1
├── contracts/
│   └── task-collaboration-api.json          # Fase 1
├── checklists/
│   └── requirements.md
└── tasks.md                                 # Fase 2 (/speckit-tasks, NO creado aquí)
```

### Source Code (repository root)

```text
src/
├── domain/
│   ├── permissions.py          # NUEVO: matriz de permisos pura
│   ├── exceptions.py           # + TaskNotAccessibleError, OperationNotPermittedError
│   ├── models.py               # Task + assignee_*, viewer_role; + Notification
│   └── services.py             # TaskService (_load_for) + CollaborationService (nuevo)
├── infrastructure/
│   ├── models.py               # TaskORM.assignee_id; NotificationORM; CHECK de auditoría ampliado
│   └── repositories.py         # list_visible, set_assignee (CAS), NotificationRepository
└── web/
    ├── task_routes.py          # rutas de detalle, asignación, estado/reapertura con rol
    ├── notification_routes.py  # NUEVO: lista y marcar leída (HTML + API)
    ├── app.py                  # registra blueprint; contador no leídas en contexto
    ├── templates/
    │   ├── tasks/list.html     # listado único, insignias, filtro por rol
    │   ├── tasks/detail.html   # NUEVO: lectura (propietario/asignado)
    │   └── notifications/list.html  # NUEVO
    └── static/js/
        ├── tasks.js            # acciones según data-viewer-role
        ├── assignment.js       # NUEVO: asignar/desasignar con rollback
        └── notifications.js    # NUEVO: marcar leída con rollback

migrations/versions/<rev>_004_task_collaboration.py   # NUEVO

tests/
├── unit/        test_permissions.py, test_collaboration_service.py
└── integration/ test_assignment_routes.py, test_collaboration_rollback.py,
                 test_task_list_roles.py, test_notification_routes.py,
                 test_migrations.py (ampliado)

docs/evidencias/inc4/          # salidas RED/GREEN reales de pytest
```

**Structure Decision**: Se mantiene el monolito modular existente (dominio → infraestructura → web). No se introducen paquetes ni dependencias; el único módulo de dominio nuevo (`permissions.py`) existe porque la matriz por operación debe probarse aislada del transporte (Principio I).

## Complexity Tracking

Sin violaciones de la constitución; no se requiere justificación.

## Riesgos y puntos a revisar

- **Enumeración de usuarios**: rechazar correos inexistentes con 400 (requisito del spec) revela si un correo está registrado a usuarios autenticados. Aceptado por el spec; mitigación futura: límite de intentos.
- **Mapeo 404 para ajenos** en rutas JSON que hoy devuelven 403 (PUT/PATCH de tarea ajena): alineado con FR-011; revisión explícita requerida (gate 4).
- **Downgrade**: El downgrade se bloquea antes de cualquier cambio de esquema si existen asignaciones, notificaciones o nuevos eventos de auditoría. Conserva los datos, el esquema y la revisión Alembic. Solo permite revertir cuando no se pierde información.
- **Concurrencia**: resuelta con actualización condicional; sin bloqueos adicionales.
- **CSRF**: se sigue el mecanismo vigente del proyecto; este incremento no lo modifica.
