# Tasks: Organización y Priorización de Tareas (Incremento 3)

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Branch**: `003-task-organization-prioritization`

---

## Phase 1: Setup & Baseline Verification

**Purpose**: Verify repository health and ensure all 97 existing tests from Increment 2 pass cleanly before introducing schema changes or feature code.

- [X] T001 Run existing automated test suite (`pytest -v`) to confirm 97/97 passing baseline tests prior to Increment 3 changes

---

## Phase 2: Foundational Migrations & ORM Schema (Revision 003)

**Purpose**: Core database schema evolution using Alembic batch mode for SQLite, adding categories, task priority, category foreign key, and safely expanding audit logs action check constraint.

> [!CRITICAL]
> **STOP GATE**: No user story implementation may begin until migration revision 003 is tested and verified on isolated temporary databases. Real databases (`taskcontrol.db` and `taskcontrol_backup.db`) must remain completely untouched and unmodified throughout implementation and validation.

- [X] T002 [P] Update domain entities in `src/domain/models.py` (add `Category` dataclass, add `priority`, `category_id`, `category_name`, `is_overdue` to `Task`) and ORM models in `src/infrastructure/models.py` (create `CategoryORM` with unique constraint `uq_categories_user_name`, update `TaskORM` with `priority` default 'media', `category_id` FK `SET NULL`, `chk_tasks_priority`, and update `AuditLogORM` with expanded `chk_audit_logs_action`)
- [X] T003 Write migration integration tests FIRST in `tests/integration/test_migrations.py` validating upgrade to revision 003 from scratch, preservation of existing rows comparing dynamic pre/post migration counts on test fixture data (and/or on an ephemeral temporary copy of `taskcontrol.db` without modifying the original), verifying all pre-existing tasks receive `priority='media'` and `category_id=None`, and `test_migration_003_audit_logs_check_constraint_allows_new_actions` verifying `priority_change` and `category_change` are accepted post-migration
- [X] T004 Generate Alembic migration revision 003 against isolated test database (`clean_init.db`) using `flask --app src.web.app:create_app db migrate -m "003_task_organization"` (generated `migrations/versions/a6aa1e24bf8e_003_task_organization.py`)
- [X] T005 Refine `migrations/versions/a6aa1e24bf8e_003_task_organization.py` using Alembic batch mode (`recreate="always"` for SQLite) to create `categories`, alter `tasks` (`priority` default 'media', `category_id` FK `SET NULL`), and recreate `audit_logs` expanding `chk_audit_logs_action` to `('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change')` preserving all pre-existing audit log rows
- [X] T006 Execute migration test suite (`pytest tests/integration/test_migrations.py`) on isolated temporary databases and confirm 100% pass
- [X] T007 **MANDATORY STOP GATE**: Verify migration revision 003 on an isolated temporary database (and on an ephemeral temporary copy if validating pre-existing rows), confirming counts before and after match dynamically with `priority='media'` and `category_id=None`; ensure `taskcontrol.db` and `taskcontrol_backup.db` remain completely untouched and unmodified

**Checkpoint**: Foundational migration complete and verified. User stories can now be implemented.

---

## Phase 3: User Story 1 - Prioridad de Tareas y Ordenamiento (HU-07) (Priority: P1) 🎯 MVP

**Goal**: Asignar nivel de prioridad (`alta`, `media`, `baja`; valor por defecto `media`) a cada tarea, permitir su modificación en cualquier momento con registro inmutable en auditoría (`priority_change`), y ordenar el listado de tareas por prioridad conservando el orden cronológico descendente (`created_at DESC`) cuando no se selecciona orden.

**Independent Test**: Crear tareas con diferentes prioridades verificando que el formulario asigna "media" por defecto; cambiar la prioridad de una tarea y verificar el registro en auditoría; comprobar que el listado se ordena por fecha de creación por defecto y se ordena alta → media → baja al seleccionar explícitamente ordenar por prioridad.

### Tests for User Story 1 (TDD - Write FIRST)

- [X] T008 [P] [US1] Unit tests for task priority in `tests/unit/test_task_service.py` verifying default 'media' assignment, validation of allowed values (`alta`, `media`, `baja`), rejection of invalid values, audit log creation with action `priority_change`, default `created_at DESC` ordering when sort is omitted or 'created_desc', priority ordering (`alta` → `media` → `baja`) when `sort='priority_desc'`, and tie-breaking by `created_at DESC`
- [X] T009 [P] [US1] Integration tests for task priority and sorting routes in `tests/integration/test_task_routes.py` verifying `PATCH /api/tasks/<id>/priority`, `POST /tasks/<id>/edit` with priority, `GET /tasks` and `GET /api/tasks` with `sort=priority_desc` combined with `status` filter, and unauthorized access rejection

### Implementation for User Story 1

- [X] T010 [US1] Update `TaskRepository` in `src/infrastructure/repositories.py` to persist `priority` in `create_task` and `update_task`, and extend `list_tasks` to accept `sort: str = "created_desc"` applying SQL `ORDER BY CASE tasks.priority WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baja' THEN 3 ELSE 4 END ASC, tasks.created_at DESC` when `sort='priority_desc'`
- [X] T011 [US1] Update `TaskService` in `src/domain/services.py` with priority validation (default 'media'), implement `update_task_priority(task_id, user_id, priority)` recording `AuditLog` with `action='priority_change'` within atomic transaction commit/rollback boundary, and extend `list_tasks` with `sort` parameter
- [X] T012 [US1] Update task route controllers in `src/web/task_routes.py` to handle `sort` query parameter in `GET /tasks` and `GET /api/tasks`, add `PATCH /api/tasks/<int:task_id>/priority`, and accept priority in `create_task` and `edit_task` POST handlers
- [X] T013 [US1] Update Jinja2 templates in `src/web/templates/tasks/list.html`, `create.html`, `edit.html` and styles in `src/web/static/css/style.css` adding priority select dropdowns, priority sort dropdown in list view, and visual badges (`badge-priority-alta`, `badge-priority-media`, `badge-priority-baja`)
- [X] T014 [US1] Execute unit and integration tests for US1 (`pytest tests/unit/test_task_service.py tests/integration/test_task_routes.py`) and confirm 100% pass

**Checkpoint**: User Story 1 is functional, tested, and delivers independent MVP value.

---

## Phase 4: User Story 2 - Categorías de Tareas sin Eliminación en Cascada (HU-08) (Priority: P2)

**Goal**: Permitir a los usuarios crear, listar y eliminar categorías personales (máximo 1 categoría por tarea o ninguna). Al eliminar una categoría, sus tareas se desvinculan automáticamente (`category_id = NULL`) sin eliminarse en cascada. Permitir filtrar el listado de tareas por categoría.

**Independent Test**: Crear una categoría, asociar tareas a ella, filtrar por la categoría en el listado, y posteriormente eliminar la categoría comprobando que las tareas continúan existiendo activas con `category_id = None` y conservando sus estados e historial de auditoría.

### Tests for User Story 2 (TDD - Write FIRST)

- [X] T015 [P] [US2] Unit tests for category service in `tests/unit/test_category_service.py` verifying category creation with trimmed name (1-50 chars), uniqueness per user, multi-user isolation, listing user categories with active task count, and deleting category triggering task unlinking without deleting tasks
- [X] T016 [P] [US2] Unit tests for task category assignment in `tests/unit/test_task_service.py` verifying task creation with category, updating category with `category_change` audit log, unlinking category (`category_id = None`), rejecting alien categories from other users, and filtering task list by `category_id` (including `'none'`)
- [X] T017 [P] [US2] Integration tests for category routes in `tests/integration/test_category_routes.py` and `tests/integration/test_task_routes.py` verifying `GET /categories`, `POST /categories`, `DELETE /api/categories/<id>`, `POST /categories/<id>/delete`, multi-user isolation, and combined query filtering (`status` + `category_id` + `sort`) in `GET /tasks` and `GET /api/tasks`

### Implementation for User Story 2

- [X] T018 [US2] Implement `CategoryRepository` in `src/infrastructure/repositories.py` providing `create_category`, `list_by_user` with task counts, `get_by_id`, `get_by_user_and_name`, and `delete_category` relying on SQLite `ON DELETE SET NULL`
- [X] T019 [US2] Update `TaskRepository` in `src/infrastructure/repositories.py` to persist `category_id` in `create_task` and `update_task`, query joined `category_name`, and support filtering by `category_id` (integer ID or `'none'` for `category_id IS NULL`) in `list_tasks`
- [X] T020 [US2] Implement `CategoryService` in `src/domain/services.py` with validation (non-empty, trimmed, <= 50 chars, unique per user), `create_category`, `list_categories`, and `delete_category` within atomic transaction commit/rollback boundary
- [X] T021 [US2] Update `TaskService` in `src/domain/services.py` validating category ownership when assigning/updating task category, implementing `update_task_category(task_id, user_id, category_id)` recording `AuditLog` with `action='category_change'`, and supporting `category_id` filter in `list_tasks`
- [X] T022 [US2] Create category route blueprint and controllers in `src/web/category_routes.py` (`GET /categories`, `POST /categories`, `POST /categories/<id>/delete`, `GET /api/categories`, `POST /api/categories`, `DELETE /api/categories/<id>`) and register blueprint in `src/web/app.py`
- [X] T023 [US2] Update task route controllers in `src/web/task_routes.py` to accept `category_id` in create/edit POST handlers, add `PATCH /api/tasks/<int:task_id>/category`, handle `category_id` query parameter in `GET /tasks` and `GET /api/tasks`, and inject user categories into create/edit views
- [X] T024 [US2] Create category template `src/web/templates/categories/list.html` and update task templates `src/web/templates/tasks/list.html`, `create.html`, `edit.html` with category filter dropdown (including "Todas las categorías" y "Sin categoría"), category assignment dropdown, and category badges
- [X] T025 [US2] Execute unit and integration tests for US2 (`pytest tests/unit/test_category_service.py tests/integration/test_category_routes.py`) and confirm 100% pass

**Checkpoint**: User Stories 1 and 2 are functional, integrated, and independently testable.

---

## Phase 5: User Story 3 - Indicación Confiable de Tareas Vencidas en Backend (HU-09) (Priority: P3)

**Goal**: Calcular en backend (`due_date < fecha_actual_utc`) si una tarea está vencida y exponerlo en el contrato de datos (`is_overdue: bool`), garantizando que tareas completadas, eliminadas o con fecha límite de hoy nunca se marquen como vencidas, y resaltar visualmente las vencidas en la interfaz.

**Independent Test**: Crear tareas con fecha límite de ayer, de hoy, a futuro, sin fecha, y tareas completadas con fecha de ayer. Comprobar que solo la tarea activa de ayer se marca como `is_overdue = True` con insignia roja "Vencida", mientras que las tareas de hoy, futuras, sin fecha o completadas evalúan estrictamente a `is_overdue = False`.

### Tests for User Story 3 (TDD - Write FIRST)

- [X] T026 [P] [US3] Unit tests for overdue calculation in `tests/unit/test_task_service.py` verifying `is_overdue = True` for past due dates on pending/in_progress tasks, `is_overdue = False` for today's due date (`due_date == today_utc`), `is_overdue = False` for future due dates, `is_overdue = False` for completed tasks even if past due, `is_overdue = False` for soft-deleted tasks, `is_overdue = False` for tasks with null/empty due date, and transition to overdue upon reopening a past-due completed task
- [X] T027 [P] [US3] Integration tests for overdue contract and view rendering in `tests/integration/test_task_routes.py` verifying `is_overdue` boolean in `GET /api/tasks` JSON response, visual badge rendering in `GET /tasks`, and immediate removal of the overdue badge when a past-due task is completed

### Implementation for User Story 3

- [X] T028 [US3] Implement dynamic `is_overdue` calculation in `TaskService` in `src/domain/services.py` comparing `due_date < today_utc` (where `today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")`), strictly returning `False` for completed tasks (`status == 'completada'`), deleted tasks (`is_deleted == True`), tasks with no due date, or tasks where `due_date >= today_utc`, injecting `is_overdue` into returned `Task` domain objects
- [X] T029 [US3] Update `src/web/templates/tasks/list.html` and `src/web/static/css/style.css` to render prominent visual badge `<span class="badge badge-overdue">Vencida</span>` next to the due date when `task.is_overdue` is true
- [X] T030 [US3] Execute overdue test suite (`pytest -k "overdue"`) and confirm 100% pass

**Checkpoint**: All three user stories are functional, integrated, and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full regression testing, quality gates, styling, and end-to-end walkthrough in an isolated environment.

- [X] T031 Run entire automated test suite (`pytest -v --cov=src`) to ensure all 97 Increment 2 tests and all new Increment 3 unit, integration, and migration tests pass cleanly with 100% success
- [X] T032 [P] Run manual end-to-end walkthrough following `specs/003-task-organization-prioritization/quickstart.md` validating priority ordering, category lifecycle without cascading, and overdue calculation on isolated temporary database (`quickstart_inc3_temp.db`)
- [X] T033 [P] Verify code quality, PEP 8 styling compliance, and security hygiene (strict multi-user isolation on categories/tasks, no sensitive data leaked) across all modified files in `src/` and `tests/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — executes first to establish baseline.
- **Foundational Migrations (Phase 2)**: Depends on Phase 1 completion. **BLOCKS all user stories (Phase 3, 4, 5)**.
  - T002 establishes ORM models and schema.
  - T003 writes migration tests first (Red).
  - T004 generates revision 003 against `clean_init.db`.
  - T005 refines revision 003 using Alembic batch mode for categories, tasks, and audit_logs check constraint expansion.
  - T006 tests revision 003 on isolated temporary databases.
  - T007 is the **MANDATORY STOP GATE**: Verifies revision 003 on isolated temporary databases with dynamic count matching, ensuring `taskcontrol.db` and `taskcontrol_backup.db` remain strictly untouched.
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion. Delivers MVP (HU-07).
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion. Delivers categories without cascade (HU-08). Can integrate with US1.
- **User Story 3 (Phase 5)**: Depends on Phase 2 completion. Delivers backend overdue calculation (HU-09). Can integrate with US1/US2.
- **Polish (Phase 6)**: Depends on all user stories being implemented.

### Within Each User Story

1. Tests MUST be written FIRST and fail before implementation (TDD).
2. Domain and repository methods before service logic.
3. Service logic before web routes and controllers.
4. Controllers before Jinja2 templates and client-side presentation.
5. Verification check before moving to the next story.

---

## Parallel Execution Opportunities

### Phase 2 (Foundational Migrations)
```bash
# Models in parallel with test scaffolding:
Task: T002 "Update domain entities in src/domain/models.py and ORM models in src/infrastructure/models.py"
```

### User Story 1 (P1)
```bash
# Tests in parallel:
Task: T008 "Unit tests for task priority in tests/unit/test_task_service.py"
Task: T009 "Integration tests for task priority and sorting routes in tests/integration/test_task_routes.py"
```

### User Story 2 (P2)
```bash
# Tests in parallel:
Task: T015 "Unit tests for category service in tests/unit/test_category_service.py"
Task: T016 "Unit tests for task category assignment in tests/unit/test_task_service.py"
Task: T017 "Integration tests for category routes in tests/integration/test_category_routes.py"
```

### User Story 3 (P3)
```bash
# Tests in parallel:
Task: T026 "Unit tests for overdue calculation in tests/unit/test_task_service.py"
Task: T027 "Integration tests for overdue contract and view rendering in tests/integration/test_task_routes.py"
```

---

## Implementation Strategy & MVP Scope

1. **Baseline + Foundational (Phase 1 & Phase 2)**:
   - Verifies 97 existing tests.
   - Implements Alembic revision 003 (`categories`, `tasks.priority`, `tasks.category_id`, expanded `chk_audit_logs_action`).
   - Satisfies mandatory Stop Gate (T007) verifying migration 003 on isolated temporary databases with dynamic count matching, ensuring real databases remain untouched.
2. **MVP Scope (Phase 3 - User Story 1)**:
   - Implements priority assignment (default 'media') and ordering (alta → media → baja).
   - Preserves default chronological order (`created_at DESC`) when no sort option is chosen.
   - Verifies independent value delivery with tests.
3. **Incremental Delivery (Phase 4 & Phase 5)**:
   - Adds User Story 2 (categories CRUD, unlinking `category_id = NULL` without cascading deletion, category filtering).
   - Adds User Story 3 (backend dynamic overdue calculation comparing `due_date < fecha_actual_utc`, excluding today, completed and deleted tasks).
4. **Final Quality Gate (Phase 6)**:
   - Full regression suite with 100% pass and coverage report.
   - Walkthrough on isolated temporary database following `quickstart.md`.
