# Research: Colaboración entre Usuarios (Incremento 4)

Todas las decisiones parten del código existente (verificado en `src/domain/services.py`, `src/infrastructure/repositories.py`, `src/web/task_routes.py`, `src/web/static/js/tasks.js`, migración 003) y de las aclaraciones del spec. No quedan `NEEDS CLARIFICATION`.

## R-01 — Modelado de la asignación

- **Decision**: Columna `tasks.assignee_id` (nullable, FK a `users`, `ON DELETE SET NULL`); `tasks.user_id` sigue siendo el propietario.
- **Rationale**: Un asignado máximo (D1) se expresa con una columna; el historial ya vive en `audit_logs`. Cumple YAGNI y evita una tabla de asignaciones con vigencia.
- **Alternatives**: Tabla `task_assignments` con histórico (rechazada: duplica la auditoría); relación N:M de colaboradores (fuera de alcance, FR-025).

## R-02 — Autorización por operación sin ampliar `get_task`

- **Decision**: Política pura `permissions.authorize(task, user_id, operation)` + `TaskService._load_for` usado solo por lectura, cambio de estado y reapertura. `get_task` queda solo-propietario.
- **Rationale**: Hoy `get_task` es la única puerta de `update_task`, `update_task_priority`, `update_task_category`, `delete_task`, `update_task_status` y `reopen_task`; abrirla al asignado habilitaría edición y borrado. La política por operación hace explícito qué rol puede qué y se prueba como matriz.
- **Alternatives**: Parámetro `allow_assignee` en `get_task` (rechazada: fácil de olvidar y de abusar); decoradores en rutas (rechazada: la regla pertenece al dominio, Principio I).

## R-03 — Códigos de error y compatibilidad

- **Decision**: Dos subclases de `UnauthorizedError`: `TaskNotAccessibleError` (ajeno → 404) y `OperationNotPermittedError` (asignado sin permiso → 403). Las rutas capturan primero las subclases. `UnauthorizedError` simple (p. ej. categoría ajena) sigue siendo 403.
- **Rationale**: Las pruebas unitarias existentes esperan `UnauthorizedError` (siguen pasando por herencia); el spec exige 404 para ajenos y 403 para asignado. Las rutas JSON de PUT/PATCH sobre tarea ajena pasan de 403 a 404; las comprobaciones existentes aceptan `(403, 404)` o `404`.
- **Alternatives**: Cambiar el tipo de excepción (rompe pruebas); mantener 403 para ajenos (contradice FR-011 y revela existencia).

## R-04 — Atomicidad y concurrencia

- **Decision**: Una transacción de sesión por operación (patrón `try/commit/except rollback` ya usado) y asignación con actualización condicional `WHERE id=:id AND assignee_id IS :old AND is_deleted=0`; `rowcount==0` → 409.
- **Rationale**: Garantiza todo-o-nada entre asignación, auditoría y notificación y evita dos asignados ante carreras; SQLite serializa escrituras.
- **Alternatives**: Bloqueos explícitos o versiones optimistas en la tarea (más complejidad sin necesidad).

## R-05 — Auditoría

- **Decision**: Acciones `assign`, `reassign`, `unassign`; `details` JSON con `old_assignee_id` y `new_assignee_id`; actor = propietario. CHECK ampliado con recreación de la tabla (como 003). Cambios de estado del asignado reutilizan `status_change`/`reopen` con el asignado como actor.
- **Rationale**: Longitud de `action` ≤ 20 (máx. 10 caracteres usados); eventos separados facilitan consultas y pruebas; ids evitan datos personales mutables.
- **Alternatives**: Una única acción `assignment_change` (menos legible en consultas de auditoría).

## R-06 — Destinatario identificado por correo

- **Decision**: La API recibe `assignee_email` (insensible a mayúsculas, recortado), resuelto con `UserRepository.get_by_email`.
- **Rationale**: Es lo asumido en el spec; el usuario no conoce ids internos; el repositorio ya normaliza correos.
- **Alternatives**: Ids (inusable desde UI); buscador de usuarios (fuera de alcance).

## R-07 — Notificaciones: almacenamiento y disponibilidad

- **Decision**: Tabla `notifications` con `message` fijo, `is_read`, `read_at`; disponibilidad derivada en lectura por la relación vigente más la regla "última notificación de (tarea, destinatario)".
- **Rationale**: D4 (se conservan) y la regla de acceso (la notificación nunca otorga acceso): derivar evita sincronizar banderas al reasignar/eliminar desde otros flujos. La regla del máximo cubre el caso de reasignar de nuevo al mismo usuario.
- **Alternatives**: Bandera `available` actualizada al perder acceso (requiere tocar notificaciones desde eliminar/reasignar: más acoplamiento); borrar notificaciones (contradice D4).

## R-08 — Acceso a la tarea desde una notificación

- **Decision**: Nueva vista de solo lectura `GET /tasks/<id>` y `GET /api/tasks/<id>` que autorizan con `VIEW`; las notificaciones disponibles enlazan allí. `/tasks/<id>/edit` sigue solo-propietario.
- **Rationale**: El asignado no puede editar, por lo que el enlace a edición no sirve; una vista de lectura nueva es el mínimo. La autorización nunca consulta notificaciones.
- **Alternatives**: Enlazar al listado con ancla (no prueba acceso individual); reutilizar la edición (viola D2).

## R-09 — Listado único

- **Decision**: `TaskRepository.list_visible` con una consulta, `(user_id = :u OR assignee_id = :u)`, `LEFT JOIN` a alias de `users` para correos, filtro `role` (`all|owned|assigned_to_me|delegated`); filtros de categoría restringidos a tareas propias.
- **Rationale**: Sin duplicados (joins N:1); respeta filtros de estado y orden existentes; categorías son personales.
- **Alternatives**: Dos consultas fusionadas en Python (riesgo de duplicados y de orden inconsistente); `UNION` (innecesario).

## R-10 — Interfaz sin recarga

- **Decision**: `tasks.js` lee `data-viewer-role` del `.task-item` y regenera acciones solo con botones permitidos (el asignado no ve Editar/Eliminar tras completar/reabrir); se conservan la actualización optimista y el rollback. Asignar/desasignar y marcar leída usan `API` con confirmación del servidor y reversión visual en error. El backend sigue siendo la autoridad.
- **Rationale**: Hoy el JS reinyecta Editar/Eliminar tras cada cambio de estado; sin esta adaptación el asignado vería acciones prohibidas. Preserva FR-023.
- **Alternatives**: Recargar tras cambios (rompe el comportamiento existente).

## R-11 — Migración segura sobre SQLite

- **Decision**: `batch_alter_table` para añadir columna/FK/índice y `recreate='always'` para el CHECK de auditoría; pruebas con BD temporal en `tmp_path` llevada a 003, con datos sembrados y comparados fila a fila tras 004.
- **Rationale**: Es el patrón ya validado por 003 y por la prueba de migraciones reproducible.
- **Alternatives**: `ALTER` directo (SQLite no soporta cambiar CHECK/FK).

## R-12 — Estrategia de evidencia TDD

- **Decision**: Guardar salidas reales de `pytest` en `docs/evidencias/inc4/` (RED antes de implementar, GREEN después), sin edición manual, con un commit por fase.
- **Rationale**: Trazabilidad verificable (Principio III) y consistente con `docs/evidencias/base/pytest-corregido.txt`.
- **Alternatives**: Resumen manual (no verificable).
