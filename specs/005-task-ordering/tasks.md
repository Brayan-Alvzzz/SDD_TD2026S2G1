# Tasks: 005-task-ordering

**Input**: Design documents from `/specs/005-task-ordering/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/task-ordering-contract.md

**Organization**: Las tareas están agrupadas en bloques funcionales según las instrucciones de planificación. Las pruebas RED se ejecutan siempre antes de la implementación GREEN.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)

---

## Phase A: Modelo, migración y servicio de ordenamiento

**Purpose**: Persistencia y lógica de negocio (HU-16).

- [ ] T001 [US16] **RED**: Escribir prueba de migración y servicio en `tests/integration/test_task_ordering_service.py` comprobando inicialización determinista (sin huecos), inserción al final, conservación del orden relativo al borrar y actualización concurrente ("last write wins" con 409 verificado aislando sesiones de engine). Ejecutar y guardar salida como `docs/evidencias/inc5/red-service-ordering.txt`.
- [ ] T002 [US16] **GREEN**: Agregar columna `position` en `src/domain/models.py` (`Task`) y `src/infrastructure/models.py` (`TaskORM`).
- [ ] T003 [US16] **GREEN**: Generar script de migración en `migrations/versions/` (vía `flask db migrate -m "005_task_ordering"`) e inyectar en Python la inicialización determinista de las tareas previas usando actualización programática en lote por usuario.
- [ ] T004 [US16] **GREEN**: Implementar método `update_task_order(user_id, task_ids)` en `src/domain/services.py` (`TaskService`). Debe extraer los vivos (`is_deleted=False`), validar duplicados, pertenencia e igualdad de sets, emitiendo un commit atómico y bloqueando/leyendo el estado previo con exactitud para detectar inconsistencias. Se probará superando el test de T001 y se guardará `docs/evidencias/inc5/green-service-ordering.txt`.

---

## Phase B: Ruta HTTP y consulta del listado

**Purpose**: Contrato REST y lectura ordenada (HU-16).

- [ ] T005 [US16] **RED**: Escribir pruebas en `tests/integration/test_task_routes_ordering.py` verificando el contrato `PATCH /api/tasks/order`. Incluir 401 (sin sesión), 400 (malformado, duplicados), 403 (ajenos/asignados), 404 (inexistentes) y 409 (desactualizado). Verificar respuesta `changed` y que `GET /api/tasks` (o `list_visible`) ordene por `position ASC, id ASC`. Ejecutar y guardar salida como `docs/evidencias/inc5/red-routes-ordering.txt`.
- [ ] T006 [US16] **GREEN**: Modificar `src/infrastructure/repositories.py` (`TaskRepository`) para que `list_by_user` y `list_visible` ordenen por `position ASC, id ASC`.
- [ ] T007 [US16] **GREEN**: Implementar ruta `PATCH /api/tasks/order` en `src/web/task_routes.py` utilizando `TaskService.update_task_order` según contrato. Ejecutar suite de rutas y servicio, guardando `docs/evidencias/inc5/green-routes-ordering.txt`.

---

## Phase C: Arrastre en interfaz y verificación de HU-15

**Purpose**: UI, Drag and drop nativo, y control asíncrono.

- [ ] T008 [US16] **RED**: Escribir regresión E2E asíncrona en `tests/integration/test_task_ordering_ui.py` (usando Playwright). Verificar que el arrastre funciona sin recarga, persistencia al recargar (F5), bloqueo de D&D en vistas filtradas o con asignadas, recuperación visual ante fallos y comprobación de la funcionalidad previa (completar sin recarga, HU-15). Ejecutar y guardar como `docs/evidencias/inc5/red-ui-ordering.txt`.
- [ ] T009 [US16] **GREEN**: Actualizar `src/web/templates/tasks/index.html` para incluir `draggable="true"` en los `li` sólo cuando sea vista principal `Mis Tareas` y no tenga otros filtros de orden o estado activos.
- [ ] T010 [US16] **GREEN**: Añadir cliente `PATCH /order` a `src/web/static/js/api.js`.
- [ ] T011 [US16] **GREEN**: Implementar la lógica HTML5 de Drag & Drop (`dragstart`, `dragover`, `drop`) en `src/web/static/js/tasks.js`. Recopilar los `data-task-id` al soltar, invocar a `api.js` y hacer rollback visual si el código es 5xx, o un alert de recarga forzosa si el código es 409. Comprobar superación con T008 guardando evidencia en `docs/evidencias/inc5/green-ui-ordering.txt`.

---

## Final Phase: Regresión final

- [ ] T012 Ejecutar suite general de pruebas (unitarias, integración, E2E HTML/JS de Incrementos 1, 2, 3, 4 y 5) certificando regresión cero (`pytest`). Guardar salida completa en `docs/evidencias/inc5/regresion-final-inc5.txt`.

## Dependencies & Execution Order

- **Phase A**: No dependencies - can start immediately
- **Phase B**: Depends on Phase A (Servicio y modelo listos).
- **Phase C**: Depends on Phase B (Ruta lista para el JS).
- **Final Phase**: Solo al completar las anteriores.

## Implementation Strategy

1. Modelo y Servicio primero (Backend puro y robustez).
2. Endpoint HTTP sobre base sólida.
3. Consumo UI conservando estabilidad.
