# Tasks: Cierre de Gestión de Tareas y Recuperación de Acceso

**Feature**: `002-task-lifecycle-access-recovery`  
**Branch**: `002-task-lifecycle-access-recovery`  
**Specification**: [spec.md](spec.md) | **Implementation Plan**: [plan.md](plan.md)  
**Status**: Ready for Implementation  

---

## Overview & Execution Guidelines

This task list guides the implementation of Increment 2 for TaskControl (HU-05: Soft delete, HU-06: Reopen completed tasks, HU-14: Password recovery via terminal token link).

> [!IMPORTANT]
> **Safety Stop Gate & Zero Data Loss**: Development strictly follows Test-First (TDD). Migrations must be generated against a clean temporary database (`clean_init.db`), upgraded to 001, and revision 002 generated against that same temporary database (never against the unversioned working database `taskcontrol.db`). Migrations must be verified against an empty database and a copy of the existing database before touching `taskcontrol.db`. `taskcontrol.db` must be backed up, stamped **exclusively** with revision 001, and then migrated to revision 002. All 39 Increment 1 tests must remain passing at 100%.

---

## Phase 1: Setup (Shared Infrastructure & Dependencies)

**Purpose**: Update project dependencies and prepare environment for SQLAlchemy ORM and Flask-Migrate.

- [X] T001 Update dependencies in `requirements.txt` adding `Flask-SQLAlchemy>=3.1.0` and `Flask-Migrate>=4.0.0`
- [X] T002 Install updated dependencies in the virtual environment via `pip install -r requirements.txt`

---

## Phase 2: Foundational (Blocking Prerequisites: SQLAlchemy URI, Models, Controlled Migrations & Safety Stop Gate)

**Purpose**: Core ORM models, reproducible migration scripts, migration verification tests, and safe stamping of `taskcontrol.db`.

> [!CRITICAL]
> **No user story work can begin until this phase is complete and the verification stop gate (T014) is satisfied.**

- [X] T003 Configure SQLAlchemy URI resolution in `src/web/app.py`: resolve `DATABASE_PATH` to an absolute SQLite URI (`sqlite:///{os.path.abspath(db_path)}`), configure `SQLALCHEMY_TRACK_MODIFICATIONS = False`, initialize `SQLAlchemy` and `Flask-Migrate`, and implement a diagnostic startup log displaying the exact resolved database file path Flask will open
- [X] T004 Create database and migration extensions instance in `src/infrastructure/database.py` to expose `db = SQLAlchemy()` and integration helpers compatible with existing `get_db_connection`
- [X] T005 [P] Implement base ORM models in `src/infrastructure/models.py` reproducing all Increment 1 tables, constraints, and indexes verbatim: `UserORM` (`email TEXT NOT NULL UNIQUE COLLATE NOCASE`, `password_hash TEXT NOT NULL`, `created_at TEXT NOT NULL`, index `idx_users_email`), `TaskORM` (`user_id INTEGER NOT NULL` FK CASCADE, `title VARCHAR(150) NOT NULL`, `description VARCHAR(1000) NULL`, `due_date VARCHAR(30) NULL`, `status VARCHAR(20) NOT NULL DEFAULT 'pendiente'` with `CHECK (status IN ('pendiente', 'en_progreso', 'completada'))`, indexes `idx_tasks_user_id`, `idx_tasks_user_status`, `idx_tasks_user_created`), and `AuditLogORM` (`task_id INTEGER NOT NULL` FK CASCADE, `actor_id INTEGER NOT NULL` FK to users, `action VARCHAR(20) NOT NULL` with `CHECK (action IN ('create', 'update', 'status_change'))`, `details TEXT NOT NULL`, `created_at TEXT NOT NULL`, indexes `idx_audit_logs_task`, `idx_audit_logs_actor`)
- [X] T006 [Test-First] Write automated migration integration tests in `tests/integration/test_migrations.py` covering: (1) `test_clean_database_upgrade_from_scratch` verifying full DDL creation on an empty DB, (2) `test_migration_preserves_existing_data` verifying zero data loss (1 user, 4 tasks, 7 audit logs) after stamping 001 and upgrading to 002 on a populated DB copy, and (3) `test_audit_logs_check_constraint_allows_new_actions` verifying that `audit_logs` accepts `action='delete'` and `action='reopen'` and rejects invalid action values
- [X] T007 Initialize migration environment and generate clean revision 001 via `flask --app src.web.app:create_app db init` and `flask --app src.web.app:create_app db migrate -m "001_initial_schema"` pointing to temporary clean database `clean_init.db` (with `$env:DATABASE_PATH = "clean_init.db"`) to guarantee non-empty DDL
- [X] T008 Verify and validate generated initial migration in `migrations/versions/*_001_initial_schema.py` ensuring it creates all 3 tables with real constraints (`COLLATE NOCASE`, `UNIQUE`, `CHECK` on status, `CHECK` on action, `ON DELETE CASCADE`) and all 6 indexes (`idx_users_email`, `idx_tasks_user_id`, `idx_tasks_user_status`, `idx_tasks_user_created`, `idx_audit_logs_task`, `idx_audit_logs_actor`)
- [X] T009 Apply revision 001 to temporary database `clean_init.db` via `flask --app src.web.app:create_app db upgrade <rev_001_id>`, keeping `clean_init.db` active at schema version 001
- [X] T010 Extend ORM models in `src/infrastructure/models.py` with Increment 2 schema: add `is_deleted` (`BOOLEAN NOT NULL DEFAULT 0`) and `deleted_at` (`VARCHAR(35) NULL`) with index `idx_tasks_user_active` to `TaskORM`; expand check constraint in `AuditLogORM` to `CHECK (action IN ('create', 'update', 'status_change', 'delete', 'reopen'))`; and add `PasswordResetTokenORM` (`id INTEGER PRIMARY KEY AUTOINCREMENT`, `user_id INTEGER NOT NULL` FK CASCADE, `token_hash VARCHAR(64) NOT NULL` SHA-256 index `idx_reset_token_hash`, `expires_at VARCHAR(35) NOT NULL`, `used BOOLEAN NOT NULL DEFAULT 0`, `created_at VARCHAR(35) NOT NULL`)
- [X] T011 Generate incremental revision 002 pointing STILL to `clean_init.db` (already upgraded to version 001) via `flask --app src.web.app:create_app db migrate -m "002_task_lifecycle_recovery"` (NEVER generate revision 002 against the unversioned working database `taskcontrol.db`)
- [X] T012 Manually review and edit `migrations/versions/*_002_task_lifecycle_recovery.py` to incorporate the `CHECK` constraint expansion on `audit_logs` (`action IN ('create', 'update', 'status_change', 'delete', 'reopen')`) using Alembic batch mode (`op.batch_alter_table("audit_logs", recreate="always")`) since Alembic autogenerate does not detect SQLite check constraints; then clean up `clean_init.db` and unset `DATABASE_PATH`
- [X] T013 Execute migration automated test suite with `pytest tests/integration/test_migrations.py` to verify that both revisions 001 and 002 execute cleanly from an empty database and that revision 002 preserves data and allows `delete` and `reopen` on a copy of `taskcontrol.db`
- [X] T014 **MANDATORY VERIFICATION STOP GATE**: Inspect results of `pytest tests/integration/test_migrations.py`. If any migration test fails, STOP and fix. Do NOT proceed to touch `taskcontrol.db` until all migration tests pass cleanly

- [X] T015 Create backup of working database `taskcontrol.db` to `taskcontrol_backup.db` and record control row counts (`users: 1`, `tasks: 4`, `audit_logs: 7`)
- [X] T016 Stamp working database `taskcontrol.db` exclusively with revision 001 ID via `flask --app src.web.app:create_app db stamp <rev_001_id>` (do NOT use `stamp head`)
- [X] T017 Apply revision 002 to working database `taskcontrol.db` via `flask --app src.web.app:create_app db upgrade` and verify post-migration row counts (`users: 1`, `tasks: 4` with `is_deleted=0`, `audit_logs: 7`) and presence of new columns
- [X] T018 Run regression test suite `pytest tests/` to confirm that all 39 Increment 1 tests remain 100% passing

**Checkpoint**: Database infrastructure and migrations complete and verified.

---

## Phase 2.5: Foundational ORM Architecture (Repositories, Shared Session/Transaction & Test Harness Migration) (Priority: P0 - Blocking Prerequisite)

**Purpose**: Transition persistence layer from raw `sqlite3` to real SQLAlchemy ORM models (`UserORM`, `TaskORM`, `AuditLogORM`), unify session and transactional boundaries between task operations and audit logging, update Flask factory and route handlers, and refactor the test harness to run versioned Alembic migrations on isolated temporary databases (strictly avoiding `db.create_all()`).

> [!CRITICAL]
> **Blocking Gate**: All 42 existing tests must continue passing 100% and a new atomic transaction rollback test must pass before starting User Story 1 (HU-05). Working database `taskcontrol.db` and backup `taskcontrol_backup.db` must remain untouched.

- [X] T018A [P] [Test-First] Implement automated integration test in `tests/integration/test_transaction_rollback.py` verifying that task mutations and audit log creation share an atomic transaction: assert that when an audit log write or task operation fails mid-transaction, `session.rollback()` is executed and neither the task state change nor the audit log record is committed.
- [X] T018B Refactor test harness in `tests/conftest.py` to create isolated temporary SQLite database files for test runs, execute versioned Alembic migrations (`flask db upgrade` / Alembic runner to revision `3acae1929949`), provide a scoped `db_session` fixture, and inject it into repositories without using `db.create_all()`, preserving `taskcontrol.db` and `taskcontrol_backup.db`.
- [X] T018C Adapt application factory and database integration in `src/web/app.py` and `src/infrastructure/database.py` to manage request-scoped SQLAlchemy sessions (`db.session`), deprecate raw `sqlite3.Connection` factory, and handle proper request teardown.
- [X] T018D Refactor `UserRepository` in `src/infrastructure/repositories.py` to execute queries and persistence against `UserORM` using the shared SQLAlchemy session without individual commit, converting between `UserORM` and domain `User` dataclass to preserve domain interfaces.
- [X] T018E Refactor `AuditLogRepository` in `src/infrastructure/repositories.py` to execute queries and persistence against `AuditLogORM` using the shared SQLAlchemy session without individual commit, converting between `AuditLogORM` and domain `AuditLog` dataclass.
- [X] T018F Refactor `TaskRepository` in `src/infrastructure/repositories.py` to execute queries and persistence against `TaskORM` using the shared SQLAlchemy session without individual commit (using `session.flush()` when generating IDs for new tasks), converting between `TaskORM` and domain `Task` dataclass, and sharing transaction context with `AuditLogRepository`.
- [X] T018G Adapt `TaskService` and `UserService` in `src/domain/services.py` to manage atomic unit of work: coordinate task creation, update, and status change so that task mutation and audit logging are committed together in a single `session.commit()` and both rolled back via `session.rollback()` upon any failure; ensure user registration in `UserService` preserves its commit.
- [X] T018H Update Flask route controllers and dependency helpers in `src/web/task_routes.py` and `src/web/auth_routes.py` to instantiate `TaskRepository`, `UserRepository`, and `AuditLogRepository` with the active `db.session`.
- [X] T018I **MANDATORY VERIFICATION STOP GATE (42 Regression Tests + 2 Rollback Tests + 4 Foreign Key Tests)**: Execute full automated test suite `pytest tests/` ensuring all 42 previous tests, the 2 atomic rollback tests, and the 4 foreign key enforcement tests pass cleanly (48/48 tests passing) on the real SQLAlchemy ORM persistence layer before proceeding to HU-05.

**Checkpoint**: Persistence layer is 100% migrated to SQLAlchemy ORM, shared session/transaction atomic boundaries are verified with rollback test, SQLite foreign key enforcement is verified on all connections (including post-migration recovery with try/finally), test harness runs versioned Alembic migrations, and 48 tests pass cleanly.

---

## Phase 3: User Story 1 - Eliminación Lógica de Tareas (HU-05) (Priority: P1) 🎯 MVP

**Goal**: Permitir a los usuarios eliminar tareas de su lista de forma lógica (*soft delete*), ocultándolas del listado ordinario pero preservando la integridad histórica y registrando el evento en el log de auditoría con `action='delete'`.

**Independent Test**: Eliminar una tarea propia mediante confirmación de interfaz; verificar que desaparece de `/tasks`, que una re-eliminación devuelve error `404`, que el registro en `tasks` mantiene `is_deleted=1` con timestamp `deleted_at`, y que se generó un log de auditoría con `action='delete'`.

### Tests for User Story 1 (Test-First) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [X] T019 [P] [US1] Unit tests for soft delete in `tests/unit/test_task_service.py` (verify `delete_task` sets `is_deleted=True` and `deleted_at`, excludes deleted tasks from `list_tasks()`, raises error on duplicate delete attempt, prevents update/advance on deleted tasks, and creates audit log with `action='delete'`)
- [X] T020 [P] [US1] Integration tests for soft delete HTTP endpoints in `tests/integration/test_task_routes.py` (verify `POST /tasks/<id>/delete` redirects to `/tasks` with success flash, `DELETE /api/tasks/<id>` returns 200 JSON with `is_deleted=True`, returns 401 for unauthenticated requests, and returns 404 for nonexistent, already deleted, or alien tasks)

### Implementation for User Story 1

- [X] T021 [P] [US1] Update domain model `Task` dataclass in `src/domain/models.py` adding `is_deleted: bool = False` and `deleted_at: Optional[str] = None`
- [X] T022 [US1] Update `TaskRepository` in `src/infrastructure/repositories.py` to filter `TaskORM.is_deleted == False` by default in `list_by_user()`, implement `soft_delete(task_id, user_id, deleted_at)` on `TaskORM` using the shared session, and update `get_by_id()` to return `is_deleted` and `deleted_at` fields
- [X] T023 [US1] Implement `delete_task(task_id, user_id)` in `src/domain/services.py` with ownership check, double-deletion prevention, and audit log recording with `action='delete'` via `AuditLogRepository` in atomic transaction with rollback on failure
- [X] T024 [US1] Protect task modification in `TaskService.update_task` and `TaskService.advance_task_status` in `src/domain/services.py` to reject operations on tasks where `is_deleted == True` with `ValidationError`
- [X] T025 [US1] Implement HTTP routes `POST /tasks/<id>/delete` and `DELETE /api/tasks/<id>` in `src/web/task_routes.py` conforming to `specs/002-task-lifecycle-access-recovery/contracts/task-lifecycle-api.json`
- [X] T026 [US1] Update list view template in `src/web/templates/tasks/list.html` to include the "Eliminar" form button and wire native browser confirmation `confirm("¿Está seguro de que desea eliminar esta tarea?")` in `src/web/static/js/tasks.js`

**Checkpoint**: User Story 1 fully functional and testable independently. All US1 unit and integration tests pass.

---

## Phase 4: User Story 2 - Reapertura de Tareas Completadas (HU-06) (Priority: P1)

**Goal**: Permitir reabrir tareas completadas devolviéndolas al estado activo `pendiente` con tipificación diferenciada en el registro de auditoría (`action='reopen'`).

**Independent Test**: Marcar una tarea como completada, pulsar "Reabrir", verificar que su estado cambia a `pendiente`, que el log de auditoría registra `action='reopen'` con detalle del estado previo, y verificar que no se pueden reabrir tareas en `pendiente` o `en_progreso`.

### Tests for User Story 2 (Test-First) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [ ] T027 [P] [US2] Unit tests for state machine reopen validation in `tests/unit/test_state_machine.py` (verify `validate_reopen("completada")` returns `"pendiente"`, and raises `InvalidStateTransitionError` when current status is `"pendiente"` or `"en_progreso"`)
- [ ] T028 [P] [US2] Unit tests for reopen service in `tests/unit/test_task_service.py` (verify `reopen_task(task_id, user_id)` sets status to `"pendiente"`, updates `updated_at`, and creates an immutable audit log entry with `action='reopen'` and details JSON `{"from": "completada", "to": "pendiente", "reason": "reopen_by_user"}`)
- [ ] T029 [P] [US2] Integration tests for reopen HTTP endpoints in `tests/integration/test_task_routes.py` (verify `POST /tasks/<id>/reopen` redirects to `/tasks`, `POST /api/tasks/<id>/reopen` returns 200 JSON with `status="pendiente"`, returns 400 for tasks not in `"completada"`, returns 401 for unauthenticated, and returns 404 for nonexistent or alien tasks)

### Implementation for User Story 2

- [ ] T030 [P] [US2] Implement deterministic reopen transition `TaskStateMachine.validate_reopen(current_status)` in `src/domain/state_machine.py` returning `"pendiente"` only if `current_status == "completada"`
- [ ] T031 [US2] Implement `TaskService.reopen_task(task_id, user_id)` in `src/domain/services.py` validating task state via `TaskStateMachine.validate_reopen` and recording audit entry with `action='reopen'`
- [ ] T032 [US2] Implement HTTP routes `POST /tasks/<id>/reopen` and `POST /api/tasks/<id>/reopen` in `src/web/task_routes.py` conforming to `specs/002-task-lifecycle-access-recovery/contracts/task-lifecycle-api.json`
- [ ] T033 [US2] Update `src/web/templates/tasks/list.html` to conditionally render the "Reabrir" button exclusively for tasks with `status == 'completada'`, and update `src/web/static/js/tasks.js` to handle asynchronous reopen requests

**Checkpoint**: User Stories 1 and 2 fully functional and testable independently.

---

## Phase 5: User Story 3 - Recuperación de Contraseña y Restablecimiento Seguro de Acceso (HU-14) (Priority: P2)

**Goal**: Permitir a los usuarios que olvidaron su contraseña solicitar un enlace de restablecimiento seguro por correo (simulado en consola de servidor para desarrollo local) con un token de 30 minutos de vida útil, de un solo uso, revocación de tokens anteriores y mitigación de enumeración de usuarios.

**Independent Test**: Solicitar restablecimiento en `/forgot-password` con correo registrado y no registrado (ambos reciben respuesta idéntica 200 OK); extraer el token impreso en consola; acceder a `/reset-password/<token>`, ingresar nueva contraseña válida (mínimo 8 caracteres); verificar inicio de sesión exitoso con la nueva clave en `/login` y comprobar que el token queda invalidado para futuros usos o tras 30 minutos.

### Tests for User Story 3 (Test-First) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [ ] T034 [P] [US3] Unit tests for password reset token lifecycle and security in `tests/unit/test_user_service.py` (test neutral response for nonexistent email, secure token generation with SHA-256 hash storage, 30-minute expiration enforcement, single-use `used=1` invalidation, proactive revocation of unconsumed tokens upon new request, and rejection of passwords shorter than 8 characters)
- [ ] T035 [P] [US3] Integration tests for password recovery HTTP endpoints in `tests/integration/test_auth_routes.py` (test `GET /forgot-password` renders 200, `POST /forgot-password` returns 200 with identical neutral message for registered and unregistered emails, `GET /reset-password/<valid_token>` renders 200 form, `GET /reset-password/<expired_or_used_token>` redirects to `/login` with flash error, `POST /reset-password/<token>` updates password and redirects to `/login`, and returns 400 for password mismatch or length < 8)

### Implementation for User Story 3

- [ ] T036 [P] [US3] Define `PasswordResetToken` domain entity dataclass in `src/domain/models.py` (`id: Optional[int]`, `user_id: int`, `token_hash: str`, `expires_at: str`, `used: bool = False`, `created_at: str = ""`)
- [ ] T037 [P] [US3] Implement `PasswordResetTokenRepository` in `src/infrastructure/repositories.py` (`create_token`, `find_active_by_hash`, `mark_as_used`, `revoke_all_for_user`)
- [ ] T038 [P] [US3] Implement `ConsoleNotificationService` in `src/infrastructure/notifications.py` to print recovery link securely to server terminal during local development without persisting plain tokens to disk
- [ ] T039 [US3] Implement `UserService.request_password_reset(email)` and `UserService.reset_password(token, new_password, new_password_confirm)` in `src/domain/services.py` with timing-neutral handling for nonexistent emails, SHA-256 token hashing, 30-minute expiration check, single-use consumption in transaction with password update, and min 8 chars validation
- [ ] T040 [US3] Implement aligned authentication routes `GET /forgot-password`, `POST /forgot-password`, `GET /reset-password/<token>`, and `POST /reset-password/<token>` in `src/web/auth_routes.py` conforming to `specs/002-task-lifecycle-access-recovery/contracts/password-recovery-api.json`
- [ ] T041 [US3] Create Jinja2 templates `src/web/templates/auth/forgot_password.html` and `src/web/templates/auth/reset_password.html` and add "¿Olvidó su contraseña?" recovery link in `src/web/templates/auth/login.html`

**Checkpoint**: All three user stories are functional and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full regression testing, quality gates, and end-to-end verification.

- [ ] T042 Run entire automated test suite (`pytest -v --cov=src`) to ensure all 39 Increment 1 tests and all new Increment 2 unit, integration, and migration tests pass cleanly with 100% success
- [ ] T043 [P] Run manual end-to-end walkthrough following `specs/002-task-lifecycle-access-recovery/quickstart.md` validating soft delete confirmation, reopen completed task, password recovery via console link, and login verification
- [ ] T044 [P] Verify code quality, PEP 8 styling compliance, and security hygiene (no plain tokens or passwords logged or written to persistent files) across all modified files in `src/` and `tests/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — executes first.
- **Foundational Migrations (Phase 2)**: Depends on Phase 1 completion.
  - T003 – T005 establish ORM setup and base schema.
  - T006 writes migration tests first (Red).
  - T007 – T009 generate revision 001 against `clean_init.db` and upgrade `clean_init.db` to 001.
  - T010 – T012 expand models, generate revision 002 against `clean_init.db`, and manually incorporate `audit_logs` CHECK.
  - T013 tests both revisions from scratch and on copy of `taskcontrol.db`.
  - T014 is the **MANDATORY STOP GATE**: No touching `taskcontrol.db` unless T013 passes 100%.
  - T015 – T017 safely backup, stamp 001, and upgrade `taskcontrol.db`.
  - T018 confirms all 39 regression tests pass.
- **Foundational ORM Architecture (Phase 2.5)**: Depends on Phase 2 completion. **BLOCKS all user stories (Phase 3, 4, 5)**.
  - T018A implements the atomic transaction rollback test first (Red).
  - T018B adapts test harness in `tests/conftest.py` with versioned Alembic migrations on temp databases (no `db.create_all()`).
  - T018C adapts Flask app factory and request-scoped session management.
  - T018D, T018E, T018F refactor `UserRepository`, `AuditLogRepository`, and `TaskRepository` to use `UserORM`, `AuditLogORM`, and `TaskORM` sharing the same session without individual commits (using `flush` for IDs).
  - T018G adapts `TaskService` and `UserService` in `src/domain/services.py` to manage atomic unit of work with single commit/rollback.
  - T018H updates route controllers.
  - T018I is the **MANDATORY VERIFICATION STOP GATE**: All 42 previous tests, the 2 atomic rollback tests, and the 4 foreign key enforcement tests must pass (48/48) on the ORM layer before starting HU-05.
- **User Story 1 (Phase 3)**: Depends on Phase 2.5 completion.
- **User Story 2 (Phase 4)**: Depends on Phase 2.5 and US1 completion.
- **User Story 3 (Phase 5)**: Depends on Phase 2.5 completion.
- **Polish (Phase 6)**: Depends on all desired user stories being implemented.

### Within Each User Story

1. Tests MUST be written FIRST and fail before implementation.
2. Domain entities and repository methods before service logic.
3. Service logic before web routes and controllers.
4. Controllers before Jinja2 templates and client-side JavaScript.
5. Verification check before moving to the next story.

---

## Parallel Execution Opportunities

### Phase 2.5 (Foundational ORM Architecture)
*Note: Repositories in `src/infrastructure/repositories.py` are refactored sequentially (T018D, T018E, T018F) to avoid concurrent edit conflicts on the same file.*


### User Story 1 (P1)
```bash
# Tests in parallel:
Task: T019 "Unit tests for soft delete in tests/unit/test_task_service.py"
Task: T020 "Integration tests for soft delete in tests/integration/test_task_routes.py"

# Domain model update in parallel with repository:
Task: T021 "Update Task dataclass in src/domain/models.py"
```

### User Story 2 (P1)
```bash
# Tests in parallel:
Task: T027 "Unit tests for state machine in tests/unit/test_state_machine.py"
Task: T028 "Unit tests for reopen service in tests/unit/test_task_service.py"
Task: T029 "Integration tests for reopen in tests/integration/test_task_routes.py"

# Domain model logic in parallel:
Task: T030 "Implement deterministic reopen transition in src/domain/state_machine.py"
```

### User Story 3 (P2)
```bash
# Tests in parallel:
Task: T034 "Unit tests for password reset in tests/unit/test_user_service.py"
Task: T035 "Integration tests for password recovery in tests/integration/test_auth_routes.py"

# Infrastructure & domain components in parallel:
Task: T036 "Define PasswordResetToken in src/domain/models.py"
Task: T037 "Implement PasswordResetTokenRepository in src/infrastructure/repositories.py"
Task: T038 "Implement ConsoleNotificationService in src/infrastructure/notifications.py"
```

---

## Implementation Strategy & MVP Scope

1. **Phase 1 + Phase 2 (Foundational & Safe Migrations)**:
   - Sets up SQLAlchemy, validates migrations on test databases, satisfies the Stop Gate (T014), backs up `taskcontrol.db`, stamps 001, applies 002, and verifies 39 existing tests.
2. **Phase 2.5 (Foundational ORM Architecture & Unit of Work)**:
   - Migrates `UserRepository`, `TaskRepository`, and `AuditLogRepository` to SQLAlchemy ORM models with shared session/transaction atomic boundary.
   - Refactors test harness to run versioned Alembic migrations on isolated temporary databases (strictly avoiding `db.create_all()`).
   - Verifies all 42 regression tests + 2 rollback tests + 4 foreign key tests (48/48) before touching any user story.
3. **Phase 3 (User Story 1 - Soft Delete)**:
   - Delivers the core **MVP** increment. Tasks can be deleted safely without data loss, operating on `TaskORM`.
4. **Phase 4 (User Story 2 - Reopen)**:
   - Completes task lifecycle closure, distinguishing `reopen` from ordinary changes in audit logs.
5. **Phase 5 (User Story 3 - Password Recovery)**:
   - Delivers autonomous user access recovery with secure token lifecycle and dev console output.
6. **Phase 6 (Polish & Verification)**:
   - Validates all 47 previous tests + new test suite and runs end-to-end quickstart scenario.
