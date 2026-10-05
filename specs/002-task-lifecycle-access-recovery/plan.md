# Implementation Plan: Cierre de Gestión de Tareas y Recuperación de Acceso

**Branch**: `002-task-lifecycle-access-recovery` | **Date**: 2026-10-04 (Actualizado) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-task-lifecycle-access-recovery/spec.md`

---

## Summary

Implementación técnica del **Incremento 2** de TaskControl que concluye la gestión básica de tareas y proporciona recuperación autónoma de acceso, cubriendo las historias del backlog:
- **HU-05 (Should / P1)**: Eliminación lógica de tareas (*soft delete*) preservando registros y logs de auditoría sin alteración física.
- **HU-06 (Should / P1)**: Reapertura explícita de tareas completadas hacia el estado activo `pendiente` con tipificación diferenciada en auditoría (`action='reopen'`).
- **HU-14 (Should / P2)**: Recuperación segura de contraseña mediante tokens temporales (vida útil de 30 min) de un solo uso, con mitigación de enumeración de usuarios y entrega en consola para entorno de desarrollo.

Adicionalmente, se diseña la adopción de **SQLAlchemy como ORM** y **Flask-Migrate (Alembic) para migraciones versionadas**:
1. **Generación reproducible**: La migración inicial `001_initial_schema` se genera contra una base limpia de prueba `clean_init.db`. Dicha base se mantiene activa y se le aplica `db upgrade <rev_001_id>`. Sobre esa base temporal ya en revisión 001 (y nunca contra la base de trabajo sin versionar) se genera la revisión incremental 002 tras ampliar los modelos.
2. **Preservación comprobada y parada de verificación**: Las revisiones se prueban automatizadamente desde cero y sobre una copia de `taskcontrol.db`. Únicamente tras superar la parada de verificación se respalda `taskcontrol.db` (1 usuario, 4 tareas, 7 logs de auditoría), se estampa **exclusivamente** la revisión 001 (`flask --app src.web.app:create_app db stamp <rev_001_id>`) y se aplica la revisión 002 con verificación posterior de conteos.
3. **Evolución de restricciones en SQLite**: La ampliación de la restricción `CHECK` de `audit_logs.action` (para incluir `'delete'` y `'reopen'`) se incorpora manualmente en la revisión 002 mediante el modo batch de Alembic (`recreate="always"`), ya que no debe darse por autogenerada, preservando filas, claves foráneas e índices.
4. **Alineación de rutas**: Todas las rutas de autenticación se alinean con las existentes en el blueprint `auth` (sin prefijo `/auth`, tales como `/login`, `/register`, `/forgot-password` y `/reset-password/<token>`).
5. **Comandos explícitos y sin atajos**: Se utilizan comandos explícitos de Flask con `--app src.web.app:create_app` y se descarta el uso de `db.create_all()` como sustituto de migraciones.

---

## Technical Context

**Language/Version**: Python 3.14 (compatible con Python 3.10+)

**Primary Dependencies**: 
- `Flask>=3.0.0`
- `Flask-SQLAlchemy>=3.1.0` (adopción ORM)
- `Flask-Migrate>=4.0.0` (gestión de migraciones Alembic)
- `Werkzeug>=3.0.0` (hashing criptográfico seguro con sal)
- `pytest>=8.0.0` y `pytest-cov>=4.0.0`

**Storage**: SQLite 3 (`taskcontrol.db` para desarrollo local; base de datos SQLite en memoria o temporal para pruebas) gestionado mediante SQLAlchemy ORM e integridad referencial (`PRAGMA foreign_keys = ON;`).

**Testing**: `pytest`, cliente de pruebas de Flask (`test_client()`), con cobertura unitaria de dominio, integración de rutas HTTP y pruebas de migración de esquema.

**Target Platform**: Multiplataforma (Windows 10/11, Linux, macOS).

**Project Type**: Monolito Modular Web (Flask + Jinja2 + Vanilla JavaScript ES6 modular).

**Performance Goals**: Tiempo de respuesta en vistas web < 1s (SC-006); procesamiento de lógica de dominio y verificación de tokens en < 50ms.

**Constraints**:
- Cumplimiento irrestricto de la [Constitución v1.0.0](file:///.specify/memory/constitution.md) de TaskControl.
- Desacoplamiento estricto del núcleo de dominio (`src/domain/`) respecto al framework web y detalles de persistencia.
- Preservación comprobada de los datos creados en el Incremento 1 mediante respaldo, estampado exclusivo y re-verificación de conteos.
- Cero almacenamiento de contraseñas ni tokens en texto plano.
- Respuestas HTTP idénticas en solicitud de recuperación para prevenir ataques de enumeración de cuentas.

---

## Constitution Check

*GATE: Evaluación previa a la implementación técnica.*

| Principio Constitucional | Estado | Justificación y Mecanismo de Cumplimiento |
|---|---|---|
| **I. Modularidad y Núcleo de Dominio Independiente** | **PASS** | Los modelos de dominio (`Task`, `User`, `AuditLog`, `PasswordResetToken`) continúan residiendo en `src/domain/models.py` como clases limpias desacopladas del framework. Los modelos ORM de SQLAlchemy se confinan exclusivamente a la capa de infraestructura (`src/infrastructure/models.py`), actuando los repositorios (`UserRepository`, `TaskRepository`, `AuditLogRepository`) como traductores que operan mediante una sesión activa compartida de SQLAlchemy (`db.session` / `Session`), garantizando atomicidad transaccional entre mutaciones de tareas y registros de auditoría. |
| **II. Autoridad Estricta del Backend y Contratos Explícitos** | **PASS** | Todas las validaciones (verificación de propietario, estado previo al reabrir, validez y vigencia de tokens, longitud mínima de 8 caracteres para contraseñas) son gobernadas por el backend. Los contratos en [`contracts/`](contracts/) definen con exactitud las cargas y códigos de respuesta. |
| **III. Enfoque Test-First y Verificación Automatizada** | **PASS** | Se definen pruebas unitarias, de integración y de migración bloqueantes antes de la codificación. Las 39 pruebas del Incremento 1 deben mantenerse al 100% en verde, sumando las pruebas del Incremento 2. |
| **IV. Trazabilidad, Auditoría e Inmutabilidad del Historial** | **PASS** | Cumplimiento pleno: La eliminación de tareas es puramente lógica (`is_deleted=1`, `deleted_at=ISO 8601`) y genera un registro de auditoría (`action='delete'`). La reapertura de tareas completadas se registra con una acción específica (`action='reopen'`), garantizando trazabilidad completa. |
| **V. Simplicidad, YAGNI y Entrega Incremental** | **PASS** | La entrega de enlaces de correo en desarrollo se resuelve mediante impresión en la terminal/consola del servidor Flask, evitando la complejidad innecesaria y el riesgo de seguridad de integrar pasarelas SMTP externas en un proyecto evaluado localmente. La incorporación de SQLAlchemy y Flask-Migrate responde a un requerimiento explícito del profesor/cliente (ver tabla de complejidad). |
| **Estándares de Seguridad** | **PASS** | Las nuevas contraseñas se almacenan mediante hash criptográfico con sal (`generate_password_hash`). Los tokens de restablecimiento se almacenan en base de datos como hashes SHA-256 (nunca en texto plano). El endpoint de recuperación previene la enumeración de usuarios respondiendo con mensajes y estados HTTP neutros. |

---

## Project Structure

### Documentation (Artifacts for Feature 002)

```text
specs/002-task-lifecycle-access-recovery/
├── spec.md                              # Especificación funcional con 5 clarificaciones
├── plan.md                              # Este plan técnico de implementación
├── research.md                          # Fase 0: Decisiones, justificaciones y procedimiento de migración
├── data-model.md                        # Fase 1: Diagramas ER, máquina de estados, modelos ORM y DDL
├── quickstart.md                        # Fase 1: Guía de ejecución con comandos explícitos de Flask
├── checklists/
│   └── requirements.md                  # Checklist de calidad de requisitos (16/16 pass)
└── contracts/
    ├── task-lifecycle-api.json          # Contrato API para eliminación lógica y reapertura
    └── password-recovery-api.json       # Contrato API para restablecimiento de contraseña
```

### Source Code Layout (Repository Root)

```text
src/
├── domain/                              # Núcleo de negocio independiente (Clean Monolith)
│   ├── __init__.py
│   ├── exceptions.py                    # ValidationError, NotFoundError, UnauthorizedError, InvalidStateTransitionError
│   ├── models.py                        # User, Task (con is_deleted/deleted_at), AuditLog, PasswordResetToken (Dataclasses)
│   ├── services.py                      # TaskService (soft delete, reopen), UserService (forgot_password, reset_password)
│   └── state_machine.py                 # TaskStateMachine (validación determinista de avance y reapertura a pendiente)
├── infrastructure/                      # Adaptadores de persistencia, ORM y servicios
│   ├── __init__.py
│   ├── database.py                      # Instancia db de Flask-SQLAlchemy, gestión de sesión y configuración
│   ├── models.py                        # Modelos SQLAlchemy: UserORM, TaskORM, PasswordResetTokenORM, AuditLogORM
│   ├── repositories.py                  # Repositorios ORM (TaskRepository, UserRepository, AuditLogRepository) con sesión y transacción compartida
│   ├── notifications.py                 # ConsoleNotificationService (impresión segura de enlaces en terminal)
│   ├── security.py                      # Hashing de contraseñas (Werkzeug) y tokens SHA-256
│   └── seed.py                          # Semilla de datos para pruebas locales
└── web/                                 # Controladores delgados y presentación (Flask)
    ├── __init__.py
    ├── app.py                           # Application Factory con Flask-SQLAlchemy, Flask-Migrate y db.session
    ├── auth_routes.py                   # /forgot-password y /reset-password/<token> (alineados con /login y /register)
    ├── task_routes.py                   # /tasks/<id>/delete, /tasks/<id>/reopen, /api/tasks/...
    ├── static/
    │   └── js/
    │       └── tasks.js                 # Confirmación nativa confirm() para eliminación
    └── templates/
        ├── auth/
        │   ├── forgot_password.html     # Formulario de solicitud de recuperación
        │   └── reset_password.html      # Formulario para definir nueva contraseña (mín 8 caracteres)
        └── tasks/
            └── list.html                # Listado con botones de "Eliminar" (con confirm) y "Reabrir" (para completadas)

migrations/                              # Control de versiones de esquema con Alembic
├── env.py
├── script.py.mako
└── versions/
    ├── xxxx_001_initial_schema.py       # Migración inicial base (estampada)
    └── yyyy_002_task_lifecycle_recovery.py # Migración incremental (soft delete, CHECK audit_logs, tokens)

tests/
├── conftest.py                          # Fixtures de Flask y bases temporales migradas con Alembic (sin db.create_all())
├── unit/
│   ├── test_state_machine.py            # Pruebas de máquina de estados (reapertura a pendiente, transiciones inválidas)
│   ├── test_task_service.py             # Pruebas de servicio: soft delete, exclusión en listado, no doble borrado
│   └── test_user_service.py             # Pruebas de tokens: expiración a 30m, un solo uso, revocación previa
└── integration/
    ├── test_auth_routes.py              # Pruebas HTTP: forgot-password neutro, reset-password flujo completo
    ├── test_task_routes.py              # Pruebas HTTP: delete y reopen con sesiones activas y denegaciones
    ├── test_migrations.py               # Pruebas de migración limpia, conservación de datos y ampliación de CHECK
    └── test_transaction_rollback.py     # Prueba de rollback atómico entre mutación de tarea y registro de auditoría
```

---

## Detailed Technical Design (7 Key Aspects)

### 1. Extensión del Modelo `Task` para Soft Delete sin Romper Incremento 1

- **Modificación del Dataclass de Dominio (`src/domain/models.py`)**:
  ```python
  @dataclass
  class Task:
      id: Optional[int]
      user_id: int
      title: str
      description: Optional[str] = None
      due_date: Optional[str] = None
      status: str = "pendiente"
      is_deleted: bool = False             # Nuevo campo con valor por defecto
      deleted_at: Optional[str] = None     # Timestamp ISO 8601 UTC opcional
      created_at: str = ""
      updated_at: str = ""
  ```
- **Persistencia en `TaskRepository` con SQLAlchemy ORM (`src/infrastructure/repositories.py`)**:
  - `TaskRepository` se inicializa con la sesión activa compartida de SQLAlchemy (`session`).
  - En `list_by_user(user_id, status=None)`: Ejecuta una consulta tipificada sobre `TaskORM`:
    `select(TaskORM).where(TaskORM.user_id == user_id, TaskORM.is_deleted == False)`. De esta forma, el listado general y los filtros por estado del Incremento 1 (HU-02) continúan excluyendo de forma automática y transparente las tareas eliminadas, mapeando cada entidad `TaskORM` a un objeto limpio de dominio `Task`.
  - En `get_by_id(task_id)`: Recupera la entidad `TaskORM` por clave primaria, retornando la entidad de dominio `Task` incluyendo sus banderas `is_deleted` y `deleted_at`.
  - En `soft_delete(task_id, user_id, deleted_at)`: Recupera la entidad `TaskORM`, actualiza `task_orm.is_deleted = True`, `task_orm.deleted_at = deleted_at`, `task_orm.updated_at = deleted_at` dentro de la sesión compartida, coordinando la confirmación atómica con `AuditLogRepository`.
- **Regla de Dominio en `TaskService.delete_task`**:
  - Si la tarea no existe o no pertenece al usuario: lanza `NotFoundError` / `UnauthorizedError`.
  - Si `task.is_deleted` ya es `True`: lanza `NotFoundError` o `ValidationError("La tarea ya se encuentra eliminada.")`, impidiendo la doble eliminación.
  - Operaciones sobre tareas eliminadas: Si un usuario intenta editar (`update_task`) o avanzar de estado (`advance_task_status`) una tarea con `is_deleted == True`, el servicio rechaza la operación informando que la tarea no está disponible.
  - Transaccionalidad atómica: La mutación de la tarea y el registro del log de auditoría (`action='delete'`) comparten la misma transacción; ante cualquier error de validación o fallo de persistencia, se invoca `session.rollback()` impidiendo estados parciales.

---

### 2. Distinción de Reapertura en Auditoría y Ampliación de Restricción CHECK en SQLite

- **Máquina de Estados (`src/domain/state_machine.py`)**:
  - Se mantiene la restricción de que una tarea en estado `"completada"` no puede avanzar por el método ordinario `validate_transition`.
  - Se implementa el método específico de reapertura:
    ```python
    @staticmethod
    def validate_reopen(current_status: str) -> str:
        if current_status != "completada":
            raise InvalidStateTransitionError(
                f"Solo las tareas completadas pueden ser reabiertas; el estado actual es '{current_status}'."
            )
        return "pendiente"  # Destino determinista según Clarification Q3
    ```
- **Evolución del CHECK en `audit_logs.action` (SQLite)**:
  - En el Incremento 1, SQLite aplica: `CHECK (action IN ('create', 'update', 'status_change'))`.
  - Dado que SQLite no permite alterar restricciones en línea, la revisión 002 de Alembic emplea el modo batch (`op.batch_alter_table("audit_logs", recreate="always")`) para reconstruir la tabla con:
    `CHECK (action IN ('create', 'update', 'status_change', 'delete', 'reopen'))`
    copiando todos los datos históricos y restableciendo claves foráneas e índices.
- **Log de Auditoría Inmutable (`audit_logs`)**:
  - Al reabrir una tarea en `TaskService.reopen_task(task_id, user_id)`:
    - Estado de la tarea pasa a `"pendiente"`.
    - Se registra en `AuditLogRepository`:
      `action = "reopen"`
      `details = json.dumps({"from": "completada", "to": "pendiente", "reason": "reopen_by_user"})`
  - Esto garantiza que en cualquier consulta o reporte de auditoría se distinga de forma inequívoca el evento de reapertura de un cambio ordinario de avance (`status_change`) o de creación (`create`).

---

### 3. Contratos de los Nuevos Endpoints HTTP y Alineación de Rutas

Consolidados en [`contracts/task-lifecycle-api.json`](contracts/task-lifecycle-api.json) y [`contracts/password-recovery-api.json`](contracts/password-recovery-api.json). Todas las rutas de autenticación se alinean con las rutas reales del blueprint existente (sin prefijo `/auth`, coincidiendo con `/login`, `/register`, `/logout`):

1. **Eliminar Tarea**:
   - `POST /tasks/<id>/delete` (Web Form con confirmación `confirm()`) → Redirección `302` a `/tasks` con flash de éxito.
   - `DELETE /api/tasks/<id>` (API REST) → `200 OK` con `{"status": "success", "message": "Tarea eliminada exitosamente", "data": {"id": id, "is_deleted": true}}`.
   - Códigos de error: `401 Unauthorized` (redirige a `/login` o JSON 401), `404 Not Found` (tarea inexistente, ajena o ya eliminada).
2. **Reabrir Tarea**:
   - `POST /tasks/<id>/reopen` (Web Form) → Redirección `302` a `/tasks`.
   - `POST /api/tasks/<id>/reopen` (API REST) → `200 OK` con `{"status": "success", "message": "Tarea reabierta exitosamente", "data": {"id": id, "status": "pendiente"}}`.
   - Códigos de error: `400 Bad Request` (si no estaba en `"completada"`), `401 Unauthorized`, `404 Not Found`.
3. **Solicitar Restablecimiento de Contraseña (HU-14)**:
   - `GET /forgot-password` → Renderiza `auth/forgot_password.html`.
   - `POST /forgot-password` → Payload: `{"email": "usuario@ejemplo.com"}` (o Form data `email`).
   - Respuesta: `200 OK` uniforme: `{"status": "success", "message": "Si la dirección de correo electrónico está registrada en el sistema, se ha enviado un enlace para restablecer la contraseña."}` tanto para correos registrados como no registrados.
   - Error: `400 Bad Request` ante formato de correo inválido sintácticamente.
4. **Confirmar Restablecimiento de Contraseña (HU-14)**:
   - `GET /reset-password/<token>` → Si el token es válido y vigente, renderiza `auth/reset_password.html`. Si expiró o ya fue usado, redirige a `/login` con mensaje flash explicativo.
   - `POST /reset-password/<token>` → Payload: `{"password": "...", "password_confirm": "..."}`.
   - Respuesta: `200 OK` / `302` a `/login` con flash: `"Contraseña actualizada exitosamente. Ya puede iniciar sesión."`.
   - Errores: `400 Bad Request` si el token es inválido/expirado/reutilizado, si la contraseña tiene menos de 8 caracteres o si las contraseñas no coinciden.

---

### 4. Modelo de Datos y Estrategia de Tokens de Restablecimiento

- **Entidad de Persistencia (`password_reset_tokens`)**:
  - `id`: Entero autoincremental (PK).
  - `user_id`: Entero (FK a `users.id` con `ON DELETE CASCADE`).
  - `token_hash`: String de 64 caracteres (hexadecimal SHA-256). Protege el token en caso de fuga de la base de datos.
  - `expires_at`: String ISO 8601 UTC (`creacion + 30 minutos`).
  - `used`: Booleano (0 por defecto, 1 al ser consumido).
  - `created_at`: String ISO 8601 UTC.
- **Ciclo de Vida y Expiración**:
  - **Vida útil**: 30 minutos estrictos.
  - **Un solo uso**: Al procesar el cambio de contraseña, se verifica `used == 0` y `now <= expires_at`. Inmediatamente se marca `used = 1` dentro de la misma transacción en que se actualiza el hash de la contraseña en `users`.
  - **Revocación Proactiva de Enlaces Anteriores (Clarification Q4)**: Al generar una nueva solicitud de recuperación para un usuario, se invalidan de inmediato todos los tokens previos no utilizados de dicho usuario (`UPDATE password_reset_tokens SET used = 1 WHERE user_id = :uid AND used = 0`), garantizando que solo el enlace más reciente sea admitido.
- **Mitigación de Enumeración de Usuarios**:
  - Si el correo **existe**: se genera el token, se persiste su hash y se imprime el enlace en la terminal.
  - Si el correo **no existe**: el servicio ejecuta una operación simulada (cálculo de hash de retardo sintético) y retorna el mismo resultado.
  - En ambos casos el controlador web devuelve exactamente el mismo mensaje neutro y código `200 OK`.

---

### 5. Entrega del Correo en Entorno de Desarrollo (Justificación Académica)

- **Mecanismo Adoptado**:
  - Se implementa `ConsoleNotificationService` (interfaz desacoplada `NotificationService`).
  - Al procesar una solicitud válida, emite el enlace en la consola estándar del servidor:
    ```text
    ================================================================================
    [DEV NOTIFICATION] Solicitud de restablecimiento de contraseña para: {email}
    Enlace generado: http://localhost:5000/reset-password/{raw_token}
    Válido durante: 30 minutos
    ================================================================================
    ```
- **Justificación**:
  1. *Alineación con el Principio V (YAGNI y Simplicidad)*: En un entorno académico y de evaluación local, integrar un proveedor SMTP real o dependencias de red introduce riesgos de credenciales expuestas en Git, bloqueos por firewalls universitarios y puntos únicos de fallo que no aportan al aprendizaje central del dominio.
  2. *Seguridad de Desarrollo*: No se almacenan los enlaces en archivos de texto persistentes en disco ni en base de datos en claro.
  3. *Arquitectura Limpia (Principio I)*: El uso del patrón Adaptador permite que en un futuro entorno de producción baste con inyectar un `SmtpNotificationService` sin alterar una sola línea de lógica en `UserService`.

---

### 6. Procedimiento Reproducible de Migraciones y Preservación Comprobada de Datos

> [!WARNING]
> **No autogenerar contra la base poblada sin versionar**: Queda estrictamente prohibido generar la revisión 002 contra la base de trabajo `taskcontrol.db` sin versionar. Si se ejecuta `flask db migrate` directamente sobre una base ya poblada, Alembic omitirá sentencias y generará revisiones vacías o inconsistentes.
> **Prohibido el uso de `db.create_all()`**: Las migraciones versionadas de Flask-Migrate deben ser el único mecanismo de evolución de la base de datos.
> **El cambio de CHECK en SQLite no es autogenerado**: Alembic no detecta modificaciones de `CheckConstraint` en SQLite; la revisión 002 debe incorporar manualmente la recreación en modo batch (`recreate="always"`).

#### Procedimiento de Ejecución en Windows PowerShell

```powershell
# ==============================================================================
# FASE 1: GENERACIÓN Y APLICACIÓN DE LA REVISIÓN INICIAL 001 EN BASE LIMPIA
# ==============================================================================
# 1. Configurar base de datos temporal limpia
$env:DATABASE_PATH = "clean_init.db"

# 2. Inicializar repositorio de migraciones (si no existe migrations/)
flask --app src.web.app:create_app db init

# 3. Generar la revisión inicial 001 a partir de los modelos base (Inc 1)
flask --app src.web.app:create_app db migrate -m "001_initial_schema"

# 4. Inspeccionar manualmente migrations/versions/*001_initial_schema.py y verificar
#    que cree 'users', 'tasks', 'audit_logs' con restricciones (NOCASE, CHECKs) e índices.

# 5. Aplicar la revisión 001 sobre clean_init.db para dejarla en versión 001
flask --app src.web.app:create_app db upgrade <rev_001_id>

# ==============================================================================
# FASE 2: GENERACIÓN DE LA REVISIÓN 002 SOBRE clean_init.db Y REVISIÓN MANUAL
# ==============================================================================
# 6. Ampliar los modelos ORM en src/infrastructure/models.py con los cambios de Inc 2
#    (TaskORM: is_deleted, deleted_at; PasswordResetTokenORM; AuditLogORM ampliado).

# 7. Generar la revisión 002 apuntando TODAVÍA a clean_init.db (ya en versión 001)
#    ¡NUNCA generar la revisión 002 contra la base de trabajo sin versionar!
flask --app src.web.app:create_app db migrate -m "002_task_lifecycle_recovery"

# 8. Revisión manual obligatoria de migrations/versions/*002_task_lifecycle_recovery.py:
#    Incorporar la reconstrucción batch de audit_logs con recreate="always" para el
#    nuevo CHECK: action IN ('create', 'update', 'status_change', 'delete', 'reopen')
#    (Alembic no autogenera modificaciones de CHECK en SQLite).

# 9. Limpiar entorno temporal una vez generadas y ajustadas las dos migraciones
Remove-Item env:DATABASE_PATH
if (Test-Path "clean_init.db") { Remove-Item "clean_init.db" }

# ==============================================================================
# FASE 3: PRUEBAS AUTOMATIZADAS DE MIGRACIONES Y PARADA DE VERIFICACIÓN
# ==============================================================================
# 10. Ejecutar la suite de pruebas de migración en tests/integration/test_migrations.py:
#     - test_clean_database_upgrade_from_scratch (upgrade 001 y 002 en base vacía)
#     - test_migration_preserves_existing_data (estampado 001 y upgrade 002 en copia)
#     - test_audit_logs_check_constraint_allows_new_actions (inserciones 'delete' y 'reopen')
pytest tests/integration/test_migrations.py -v

# 11. [PARADA DE VERIFICACIÓN]: Si alguna prueba falla, DETENERSE y corregir.
#     NO tocar ni estampar taskcontrol.db hasta que las pruebas pasen al 100%.

# ==============================================================================
# FASE 4: RESPALDO, ESTAMPADO Y MIGRACIÓN SEGURA DE LA BASE DE TRABAJO (taskcontrol.db)
# ==============================================================================
# 12. Respaldo obligatorio previo de taskcontrol.db
Copy-Item taskcontrol.db taskcontrol_backup.db

# 13. Registrar conteos de control previos a la migración
python -c "import sqlite3; conn = sqlite3.connect('taskcontrol.db'); cur = conn.cursor(); print('users:', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]); print('tasks:', cur.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]); print('audit_logs:', cur.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0])"
# Conteos de control esperados: users: 1, tasks: 4, audit_logs: 7

# 14. Estampado EXCLUSIVO de la revisión 001 (reemplazar <rev_001_id> con el ID real)
#     ¡NUNCA usar 'stamp head' si existe la 002! Estampar únicamente la revisión 001
flask --app src.web.app:create_app db stamp <rev_001_id>

# 15. Aplicar la migración 002 sobre taskcontrol.db
flask --app src.web.app:create_app db upgrade

# 16. Comprobación posterior de conservación de datos
python -c "import sqlite3; conn = sqlite3.connect('taskcontrol.db'); cur = conn.cursor(); print('users post:', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]); print('tasks post:', cur.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]); print('audit_logs post:', cur.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]); cur.execute('SELECT id, is_deleted, deleted_at FROM tasks'); print('tasks:', cur.fetchall())"
# Comprobar que users=1, tasks=4, audit_logs=7 y que is_deleted=0 para las 4 tareas previas.
```

---

### 7. Pruebas Automatizadas Bloqueantes

| Prueba Bloqueante | Capa / Módulo | Comportamiento Verificado |
|---|---|---|
| `test_clean_database_upgrade_from_scratch` | `integration/test_migrations.py` | Ejecuta `upgrade()` desde una base vacía y verifica que el esquema completo (001 y 002) se cree de cero. |
| `test_migration_preserves_existing_data` | `integration/test_migrations.py` | Carga una copia de la base con datos reales de muestra, aplica estampado 001 y upgrade 002, comprobando que los datos no se pierdan. |
| `test_audit_logs_check_constraint_allows_new_actions` | `integration/test_migrations.py` | Inserta registros con `action='delete'` y `action='reopen'`, comprobando que el `CHECK` ampliado los acepta y rechaza valores inválidos. |
| `test_task_and_audit_shared_transaction_rollback` | `integration/test_transaction_rollback.py` | Verifica que un fallo al registrar auditoría revierte atómicamente la mutación de la tarea (rollback conjunto), impidiendo estados parciales. |
| `test_soft_delete_marks_task_deleted` | `unit/test_task_service.py` | `delete_task()` establece `is_deleted=True` y `deleted_at` con timestamp válido. |
| `test_list_tasks_excludes_deleted_tasks` | `unit/test_task_service.py` | `list_tasks()` no retorna tareas con `is_deleted=True`. |
| `test_cannot_delete_already_deleted_task` | `unit/test_task_service.py` | Intentar eliminar una tarea ya eliminada lanza excepción de no encontrada / conflicto. |
| `test_cannot_edit_or_advance_deleted_task`| `unit/test_task_service.py` | Intentar modificar o avanzar de estado una tarea eliminada es rechazado. |
| `test_soft_delete_creates_audit_log` | `unit/test_task_service.py` | Se inserta un evento inmutable con `action='delete'` y actor correspondiente. |
| `test_reopen_task_transitions_to_pending` | `unit/test_state_machine.py` | Una tarea completada transiciona determinísticamente a `"pendiente"`. |
| `test_reopen_fails_if_not_completed` | `unit/test_state_machine.py` | Tareas en estado `"pendiente"` o `"en_progreso"` no admiten reapertura. |
| `test_reopen_creates_distinct_audit_action`| `unit/test_task_service.py` | La acción registrada en `audit_logs` es formalmente `'reopen'` (no `'status_change'`). |
| `test_request_reset_nonexistent_email` | `unit/test_user_service.py` | Correo inexistente no lanza excepción y responde de forma neutral sin fuga de datos. |
| `test_reset_password_with_valid_token` | `unit/test_user_service.py` | Actualiza contraseña con hash y marca `used=True` atómicamente. |
| `test_reset_password_rejects_expired_token`| `unit/test_user_service.py` | Tokens con antigüedad > 30 minutos son rechazados con error de expiración. |
| `test_reset_password_rejects_used_token` | `unit/test_user_service.py` | Tokens con `used=True` son rechazados impidiendo cualquier reutilización. |
| `test_new_request_revokes_previous_tokens` | `unit/test_user_service.py` | Solicitar un nuevo enlace invalida proactivamente cualquier token previo no consumido. |
| `test_reset_password_rejects_short_password`| `unit/test_user_service.py` | Contraseñas menores a 8 caracteres son rechazadas por el validador de dominio. |

---

### 8. Arquitectura de Repositorios ORM, Transaccionalidad Atómica Compartida y Aislamiento de Pruebas con Migraciones

#### A. Repositorios sobre Modelos ORM (SQLAlchemy)
- **Desacoplamiento Estricto (Principio I)**: Los modelos de dominio en `src/domain/models.py` (`User`, `Task`, `AuditLog`, `PasswordResetToken`) continúan siendo dataclasses puras.
- **Traducción en Repositorios**: Cada repositorio (`UserRepository`, `TaskRepository`, `AuditLogRepository`) en `src/infrastructure/repositories.py` se instancia con una sesión activa de SQLAlchemy (`session: Session`) y realiza la traducción bidireccional entre las entidades de dominio y los modelos ORM (`UserORM`, `TaskORM`, `AuditLogORM`):
  - `UserRepository`: Búsquedas por email/id e inserciones operando sobre `UserORM`.
  - `TaskRepository`: Consultas (`select(TaskORM)...`), creación, actualización y marcado de borrado lógico (`is_deleted=True`, `deleted_at=...`) operando sobre `TaskORM`.
  - `AuditLogRepository`: Inserción de eventos históricos y consultas cronológicas operando sobre `AuditLogORM`.

#### B. Unidad de Trabajo y Transaccionalidad Atómica Compartida
- **Consistencia y Prevención de Bloqueos en SQLite**: En operaciones compuestas de ciclo de vida (como `create_task`, `update_task`, `advance_task_status`, `delete_task`, `reopen_task`), `TaskService` interactúa tanto con `TaskRepository` como con `AuditLogRepository`. Ambos repositorios comparten obligatoriamente la misma instancia de `session` y **no realizan commits individuales**.
- **Uso de `session.flush()` para Claves Primarias**: Cuando se crea una tarea nueva (`create_task`), el repositorio invoca `session.flush()` (en lugar de `commit`) para forzar la asignación del `id` autogenerado por SQLite sin cerrar la transacción, permitiendo que `audit_repo.create` use de inmediato `task_id` dentro del mismo bloque transaccional.
- **Límite Transaccional Único en Servicios (`src/domain/services.py`)**:
  - `TaskService` gobierna el ciclo transaccional: ejecuta las mutaciones de tarea y auditoría sobre la sesión compartida y realiza un único `session.commit()` al finalizar exitosamente la operación.
  - Ante cualquier excepción en la mutación o en la auditoría, se invoca `session.rollback()`, garantizando que ninguna tabla quede con cambios huérfanos o inconsistentes.
  - `UserService` conserva igualmente la confirmación atómica al registrar nuevos usuarios (`register_user`) mediante `session.commit()`.
- **Prueba de Rollback Atómico**: Se implementa `tests/integration/test_transaction_rollback.py` para forzar un fallo en la persistencia de la auditoría tras una mutación de tarea y comprobar que el rollback revierte el cambio de estado de la tarea y no deja registros en auditoría.

#### C. Aislamiento de Pruebas con Migraciones Versionadas (Sin `db.create_all()`)
- **Prohibición de `db.create_all()` en Pruebas**: Los fixtures de pruebas (`tests/conftest.py`) crearán bases de datos SQLite temporales aisladas aplicando las revisiones versionadas de Alembic (`flask db upgrade` / `command.upgrade(alembic_cfg, 'head')`) hasta la revisión `3acae1929949`.
- **Protección de la Base de Trabajo**: `taskcontrol.db` y `taskcontrol_backup.db` permanecen estrictamente intactas en su versión actual `3acae1929949`; las pruebas nunca ejecutarán `stamp` ni `upgrade` sobre la base de trabajo ni su respaldo.

---

## Complexity Tracking

| Decisión Arquitectónica | Justificación Técnica | Alternativa Más Simple Descartada |
|---|---|---|
| **Adopción de SQLAlchemy y Flask-Migrate** | Requerimiento normativo del cliente/profesor para estandarizar el ORM y habilitar evolución controlada de esquemas en equipo. | Mantener consultas crudas `sqlite3` y script DDL manual. Descartada por mandato de la cátedra para este incremento. |
| **Generación limpia de 001 + Estampado exclusivo** | Evita revisiones iniciales vacías y permite adoptar Alembic sobre la base poblada preservando con verificación comprobada los datos del Incremento 1. | Autogenerar contra base existente (produce migración vacía) o recrear desde cero perdiendo datos. Descartadas por inconsistencia y destrucción de información. |
| **Modo Batch de Alembic para CHECK en SQLite** | SQLite no admite modificación directa de restricciones; el modo batch reconstruye la tabla preservando filas, claves foráneas e índices. | Eliminar el CHECK o no validar en la BD. Descartada para mantener integridad de datos (Principio IV y restricciones técnicas). |
| **Notificación por Consola de Flask** | Permite probar el flujo de restablecimiento de contraseña en desarrollo local sin dependencias externas de red o credenciales SMTP en Git. | Integrar un servidor SMTP real con credenciales. Descartada bajo Principio V (YAGNI / sobreingeniería en entorno local). |
