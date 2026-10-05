# Implementation Plan: Organización y Priorización de Tareas (Incremento 3)

**Branch**: `003-task-organization-prioritization` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-task-organization-prioritization/spec.md`

---

## Summary

Plan técnico de implementación del **Incremento 3** de TaskControl que introduce organización temática y priorización personal de tareas, cubriendo las tres historias de usuario del backlog:
- **HU-07 (Could / P1)**: Asignación de nivel de prioridad (`alta`, `media`, `baja`) a cada tarea con valor predeterminado explícito (`media`), permitiendo cambiar la prioridad en cualquier momento. El listado de tareas conserva el orden cronológico descendente por fecha de creación (`created_at DESC`) cuando no se elige un orden específico; la jerarquía de prioridad `alta` → `media` → `baja` se aplica cuando el usuario selecciona explícitamente ordenar por prioridad, combinándose fluidamente con los filtros de estado ya existentes.
- **HU-08 (Could / P2)**: Agrupación de tareas en categorías o proyectos propios (relación 0..1 a N), donde eliminar una categoría desvincula automáticamente todas sus tareas fijando `category_id = NULL` (mediante `ON DELETE SET NULL` nativo en base de datos) sin eliminación en cascada.
- **HU-09 (Could / P3)**: Cálculo dinámico de tareas vencidas resuelto exclusivamente en el backend (servicios de dominio) comparando la fecha límite `due_date` (`YYYY-MM-DD` sin hora) contra la fecha actual en UTC (`due_date < fecha_actual_utc`), excluyendo explícitamente tareas completadas, eliminadas o con fecha límite del día de hoy. El resultado se expone como propiedad derivada en el contrato de datos del listado sin persistirse en base de datos.

La implementación se apoya estrictamente sobre la arquitectura ORM adoptada en el Incremento 2 (`SQLAlchemy` + `Flask-Migrate` / `Alembic`) y preserva la integridad de las bases existentes mediante una migración versionada (`a6aa1e24bf8e_003_task_organization.py`). Dicha migración crea la tabla `categories`, añade `priority` (con default `'media'`) y `category_id` (FK `SET NULL`) a `tasks`, y recrea de forma segura en modo batch la tabla `audit_logs` ampliando la restricción `chk_audit_logs_action` para permitir `'priority_change'` y `'category_change'` conservando íntegros todos los registros preexistentes de auditoría.

---

## Technical Context

**Language/Version**: Python 3.14 (compatible con Python 3.10+)

**Primary Dependencies**:
- `Flask>=3.0.0` (enrutamiento HTTP y controladores delgados)
- `Flask-SQLAlchemy>=3.1.0` (mapeo ORM y gestión de sesiones transaccionales)
- `Flask-Migrate>=4.0.0` (gestión de migraciones de esquema mediante Alembic)
- `Werkzeug>=3.0.0` (hashing criptográfico y utilidades WSGI)
- `pytest>=8.0.0` y `pytest-cov>=4.0.0` (suite de pruebas y cobertura)

**Storage**: SQLite 3 (`taskcontrol.db` para desarrollo local; base de datos temporal en memoria o aislada en archivo para pruebas y validaciones) gestionado mediante SQLAlchemy ORM con integridad referencial estricta (`PRAGMA foreign_keys = ON;`).

**Testing**: `pytest`, cliente de pruebas de Flask (`test_client()`), con cobertura unitaria de dominio (`tests/unit/`), integración de rutas HTTP (`tests/integration/`) y pruebas de migración de esquema.

**Target Platform**: Multiplataforma (Windows 10/11, Linux, macOS).

**Project Type**: Monolito Modular Web (Flask + Jinja2 + Vanilla JavaScript modular).

**Performance Goals**: Tiempo de respuesta en listados de tareas con filtros y ordenamiento < 1s (SC-007); cómputo de vencimiento y ordenamiento en memoria/SQL en < 20ms para colecciones personales.

**Constraints**:
- Cumplimiento irrestricto de la [Constitución v1.0.0](file:///.specify/memory/constitution.md) de TaskControl.
- Desacoplamiento estricto del núcleo de dominio (`src/domain/`) respecto al framework web y detalles de persistencia.
- Aislamiento estricto de bases reales: `taskcontrol.db` y `taskcontrol_backup.db` permanecen intactas y sin modificaciones durante el desarrollo y las pruebas; la migración se valida exclusivamente en bases de datos temporales aisladas, garantizando que toda tarea preexistente reciba `priority='media'` y `category_id=NULL`.
- Cálculo de vencimiento exclusivamente en backend; prohibido evaluar vencimiento por reloj local en JavaScript.
- Desvinculación de tareas sin eliminación en cascada garantizada a nivel relacional (`ON DELETE SET NULL`).

---

## Constitution Check

*GATE: Evaluación previa a la implementación técnica.*

| Principio Constitucional | Estado | Justificación y Mecanismo de Cumplimiento |
|---|---|---|
| **I. Modularidad y Núcleo de Dominio Independiente** | **PASS** | Las entidades `Task` y `Category` se definen en `src/domain/models.py` como dataclasses puras. Las operaciones de validación de prioridades, lógica de categorías y cálculo de vencimiento residen en `TaskService` y `CategoryService` en `src/domain/services.py`. Las rutas Flask en `src/web/task_routes.py` y `src/web/category_routes.py` actúan exclusivamente como controladores delgados. |
| **II. Autoridad Estricta del Backend y Contratos Explícitos** | **PASS** | El cálculo de vencimiento (`is_overdue`) y el ordenamiento/filtrado son resueltos exclusivamente por el backend como parte del contrato de datos entregado a la interfaz. No se delega la determinación de vencimiento a la lógica de presentación del cliente para evitar inconsistencias por zona horaria o reloj del navegador. |
| **III. Enfoque Test-First y Verificación Automatizada** | **PASS** | Se diseñan pruebas unitarias y de integración bloqueantes antes de escribir el código de producción. Las 97 pruebas automatizadas existentes del Incremento 2 deben mantenerse al 100% en verde, sumando las nuevas pruebas del Incremento 3. |
| **IV. Trazabilidad, Auditoría e Inmutabilidad del Historial** | **PASS** | Las modificaciones de prioridad (`action='priority_change'`) y asignaciones/desvinculaciones de categoría en tareas (`action='category_change'`) se registran en el log de auditoría persistente con actor y marca temporal. La eliminación de categorías es segura y no afecta la integridad ni la existencia de las tareas asociadas. |
| **V. Simplicidad, YAGNI y Entrega Incremental** | **PASS** | Se implementa estrictamente lo solicitado por el backlog. Quedan explícitamente fuera de alcance las jerarquías de categorías (subcategorías anidadas), renombrar categorías, ordenar tareas por categoría, asignaciones multi-usuario (HU-10, HU-11) y drag-and-drop dinámico (HU-15, HU-16). |

---

## Project Structure

### Documentation (Artifacts for Feature 003)

```text
specs/003-task-organization-prioritization/
├── spec.md                              # Especificación funcional detallada
├── plan.md                              # Este plan técnico de implementación
├── research.md                          # Fase 0: Decisiones arquitectónicas y justificaciones
├── data-model.md                        # Fase 1: Diagrama ER, dataclasses de dominio y modelos ORM
├── quickstart.md                        # Fase 1: Guía de validación manual en entorno aislado
├── checklists/
│   └── requirements.md                  # Checklist de calidad de requisitos (16/16 pass)
└── contracts/
    ├── task-organization-api.json       # Contrato API para listado extendido, orden y prioridad
    └── category-management-api.json     # Contrato API para creación, listado y eliminación de categorías
```

### Source Code Layout (Repository Root)

```text
src/
├── domain/                              # Núcleo de negocio independiente (Clean Monolith)
│   ├── exceptions.py                    # ValidationError, NotFoundError, UnauthorizedError
│   ├── models.py                        # User, Task (con priority, category_id, is_overdue), Category, AuditLog
│   ├── services.py                      # TaskService (list con sort/category, calculate is_overdue, update priority/category), CategoryService
│   └── state_machine.py                 # Máquina de estados determinista (ciclo de vida intacto)
├── infrastructure/                      # Adaptadores de persistencia, ORM y notificaciones
│   ├── database.py                      # db (Flask-SQLAlchemy) y eventos PRAGMA foreign_keys
│   ├── models.py                        # TaskORM (priority, category_id), CategoryORM, UserORM, AuditLogORM
│   ├── repositories.py                  # TaskRepository (queries con filter/sort), CategoryRepository
│   ├── notifications.py                 # ConsoleNotificationService (desarrollo local)
│   └── security.py                      # Hash de contraseñas seguro
├── web/                                 # Capa de presentación y controladores delgados
│   ├── app.py                           # App factory, registro de blueprints y context processors
│   ├── auth_routes.py                   # Rutas de autenticación y recuperación de contraseñas
│   ├── category_routes.py               # NUEVO: Rutas web y API de categorías (list, create, delete)
│   ├── task_routes.py                   # Rutas extendidas de tareas (sort, category filter, priority patch)
│   ├── static/
│   │   ├── css/style.css                # Estilos para insignias de prioridad y advertencia de vencidas
│   │   └── js/tasks.js                  # Manejo de interfaz (selectores de prioridad/categoría)
│   └── templates/
│       ├── categories/
│       │   └── list.html                # NUEVO: Plantilla para listar y crear/eliminar categorías
│       └── tasks/
│           ├── list.html                # Listado extendido con selector de orden, filtro y badges
│           ├── create.html              # Formulario con selector de prioridad y categoría
│           └── edit.html                # Formulario con selector de prioridad y categoría
migrations/
└── versions/
    ├── 001_initial_schema.py            # Revisión inicial base
    ├── 002_task_lifecycle_recovery.py   # Soft delete, reopen y tokens
    └── a6aa1e24bf8e_003_task_organization.py # NUEVA: Tabla categories, columnas priority y category_id
tests/
├── conftest.py                          # Fixtures de pytest con migraciones sobre bases temporales
├── integration/
│   ├── test_auth_routes.py              # Pruebas de autenticación y recuperación
│   ├── test_category_routes.py          # NUEVO: Pruebas de integración de categorías
│   ├── test_foreign_keys.py             # Pruebas de integridad referencial y PRAGMA foreign_keys
│   ├── test_migrations.py               # Pruebas de revisión 003 y preservación de datos
│   ├── test_task_routes.py              # Pruebas de listado extendido, orden y filtros
│   └── test_transaction_rollback.py     # Pruebas de atomicidad transaccional
└── unit/
    ├── test_category_service.py         # NUEVO: Pruebas unitarias de CategoryService
    ├── test_state_machine.py            # Pruebas de transiciones de estado
    ├── test_task_service.py             # Pruebas unitarias de prioridad, vencimiento y filtros
    └── test_user_service.py             # Pruebas unitarias de usuario
```

---

## Detailed Technical Design

### 1. Extensión del Modelo Task y Relación con Category

#### En Dominio (`src/domain/models.py`)
La dataclass `Task` se amplía con:
* `priority: str = "media"`: Valores permitidos estrictamente `('alta', 'media', 'baja')`.
* `category_id: Optional[int] = None`: Clave foránea opcional a `Category.id`.
* `category_name: Optional[str] = None`: Nombre denormalizado para facilitar la presentación en vistas sin acoplamiento a consultas externas.
* `is_overdue: bool = False`: Propiedad booleana calculada en tiempo de consulta, no persistida.

Se incorpora la nueva dataclass `Category`:
```python
@dataclass
class Category:
    id: Optional[int]
    user_id: int
    name: str
    created_at: str = ""
```

#### En Infraestructura (`src/infrastructure/models.py`)
* `TaskORM` añade:
  * `priority`: `db.Column(db.String(10), nullable=False, default="media", server_default="media")`
  * `category_id`: `db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)`
  * `CheckConstraint("priority IN ('alta', 'media', 'baja')", name="chk_tasks_priority")`
  * Índices optimizados: `idx_tasks_user_priority` (`user_id`, `priority`) y `idx_tasks_user_category` (`user_id`, `category_id`).
  * Relación: `category = db.relationship("CategoryORM", backref=db.backref("tasks", passive_deletes=True))`

---

### 2. Modelo de Datos de Category y Desvinculación sin Cascada

#### Campos Mínimos de `CategoryORM`
* `id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
* `user_id`: `INTEGER NOT NULL`, clave foránea a `users.id` con `ON DELETE CASCADE`.
* `name`: `VARCHAR(50) NOT NULL`.
* `created_at`: `VARCHAR(35) NOT NULL` (formato ISO 8601 en UTC).
* Restricciones:
  * `UniqueConstraint("user_id", "name", name="uq_categories_user_name")`: Garantiza que ningún usuario pueda tener categorías duplicadas con el mismo nombre, permitiendo que usuarios distintos compartan nombres.
  * Índice: `idx_categories_user_id` sobre `user_id`.

#### Regla de Desvinculación Relacional (`ON DELETE SET NULL`)
* **A nivel de Base de Datos**: La clave foránea en `tasks` está declarada como:
  ```sql
  FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
  ```
* Al estar activo `PRAGMA foreign_keys = ON` en cada conexión SQLite, cuando se ejecuta `DELETE FROM categories WHERE id = :cat_id`, el propio motor SQLite ejecuta la acción referencial: actualiza atómicamente todas las tareas asociadas estableciendo `category_id = NULL`.
* **Resultado**: Las tareas no se eliminan, no sufren borrado lógico ni sufren alteraciones en sus estados o auditorías previas; únicamente pierden el vínculo con la categoría eliminada.
* **A nivel de Servicio**: `CategoryService.delete_category(category_id, user_id)` verifica que la categoría exista y pertenezca al usuario autenticado, y ejecuta la eliminación sobre `CategoryORM` dentro de la sesión transaccional de SQLAlchemy con un único `commit()`.

---

### 3. Contrato de Endpoints y Extensión del Listado de Tareas

#### 3.1 Endpoints de Categorías
* `GET /categories` (Web) / `GET /api/categories` (JSON):
  * Retorna la lista de categorías del usuario autenticado junto con el conteo de tareas activas (`task_count`).
* `POST /categories` (Web) / `POST /api/categories` (JSON):
  * Carga: `{"name": "Nombre de categoría"}` (1 a 50 caracteres).
  * Validación: No vacío, trim, longitud <= 50 caracteres, unicidad por usuario.
  * Respuesta: `201 Created` con el objeto categoría creado.
* `POST /categories/<int:category_id>/delete` (Web) / `DELETE /api/categories/<int:category_id>` (JSON):
  * Validación: Verifica propiedad del usuario.
  * Respuesta: `200 OK` (JSON) o redirección con mensaje flash. Desvincula tareas asociadas en la base de datos sin borrarlas.

#### 3.2 Endpoints de Prioridad y Categoría en Tareas
* `PATCH /api/tasks/<int:task_id>/priority`:
  * Carga: `{"priority": "alta"|"media"|"baja"}`.
  * Validación: Verifica propiedad, estado activo (no eliminada) y valor válido.
  * Registra evento de auditoría `action='priority_change'` con detalle `{"old_priority": "media", "new_priority": "alta"}`.
* `PATCH /api/tasks/<int:task_id>/category`:
  * Carga: `{"category_id": 1|null}`.
  * Validación: Si no es nulo, verifica que la categoría exista y pertenezca al mismo usuario.
  * Registra evento de auditoría `action='category_change'`.

#### 3.3 Extensión del Endpoint de Listado (`GET /tasks` y `GET /api/tasks`)
El endpoint existente se amplía de manera retrocompatible aceptando tres parámetros opcionales en la cadena de consulta (query string):
* `status`: `'todas' | 'pendiente' | 'en_progreso' | 'completada'` (por defecto `'todas'`).
* `category_id`: `''` (todas), `'none'` (solo tareas sin categoría), o número entero (ID de la categoría).
* `sort`:
  * `'created_desc'` (por defecto): Conserva el orden cronológico descendente por fecha de creación de forma predeterminada cuando el usuario no elige orden, preservando la apariencia y orden de los Incrementos 1 y 2.
  * `'priority_desc'`: Aplica la jerarquía de prioridad alta a baja (`alta` > `media` > `baja`) con desempate secundario por `created_at DESC`.
  * `'priority_asc'`: Aplica la jerarquía de prioridad baja a alta (`baja` > `media` > `alta`) con desempate secundario por `created_at DESC`.

En SQL, el ordenamiento por prioridad se traduce de manera determinista:
```sql
ORDER BY
  CASE tasks.priority
    WHEN 'alta' THEN 1
    WHEN 'media' THEN 2
    WHEN 'baja' THEN 3
    ELSE 4
  END ASC,
  tasks.created_at DESC
```

Cada tarea retornada en el contrato de datos (Jinja2 y JSON) incluye:
* `priority`: `"alta" | "media" | "baja"`
* `category_id`: `int | null`
* `category_name`: `string | null`
* `is_overdue`: `true | false` (campo derivado calculado en backend)

---

### 4. Cálculo del Indicador de Tareas Vencidas (HU-09)

* **Ubicación del Cálculo**: Se implementa en la capa de dominio dentro de `TaskService` (y encapsulado como método auxiliar en la entidad `Task` o función pura de dominio `compute_is_overdue`).
* **Naturaleza Derivada**: **NUNCA** se persiste como columna en la tabla `tasks`. Se evalúa dinámicamente en tiempo de ejecución al construir la respuesta del listado o consulta de tarea.
* **Algoritmo de Cálculo**:
  1. Si `task.is_deleted` es verdadero (`True`) → `is_overdue = False`.
  2. Si `task.status == 'completada'` → `is_overdue = False`.
  3. Si `task.due_date` es nulo, vacío o contiene solo espacios → `is_overdue = False`.
  4. Se obtiene la fecha actual en UTC en formato calendario: `today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")`.
  5. Se realiza la comparación léxica directa:
     ```python
     is_overdue = (task.due_date < today_utc)
     ```
  6. **Regla de la fecha de hoy**: Si `task.due_date == today_utc`, la comparación `task.due_date < today_utc` evalúa a `False`. Por ende, las tareas con fecha límite de hoy **no** están vencidas.
* **Exposición en Contrato**:
  * En plantillas Jinja2: `task.is_overdue` permite renderizar una insignia visual roja destacada `badge-danger` ("Vencida") junto a la fecha límite.
  * En JSON: `"is_overdue": true|false` en cada objeto de tarea.

---

### 5. Estrategia de Migraciones Versionadas (Revisión Alembic 003)

Para dar estricto cumplimiento al **Principio IV** (Integridad referencial y auditoría) y garantizar que la base de datos de producción/desarrollo no sufra pérdidas ni corrupciones:

#### 5.1 Definición de la Revisión `a6aa1e24bf8e_003_task_organization.py`
Alembic aplicará en modo batch (`recreate="always"` para SQLite) las siguientes operaciones atómicas:
1. Crear la tabla `categories` con su clave foránea a `users.id` y restricción única `(user_id, name)`.
2. Modificar la tabla `tasks`:
   * Agregar columna `priority VARCHAR(10) NOT NULL DEFAULT 'media'`.
   * Agregar columna `category_id INTEGER NULL` vinculada a `categories.id` con `ON DELETE SET NULL`.
   * Preservar y aplicar restricciones `chk_tasks_status` y `chk_tasks_priority`.
   * Crear índices `idx_tasks_user_priority` e `idx_tasks_user_category`.
3. Recrear en modo batch la tabla `audit_logs` (`batch_alter_table("audit_logs", recreate="always")`):
   * Reemplazar la restricción `chk_audit_logs_action` para admitir `priority_change` y `category_change` junto a las 5 acciones anteriores:
     ```sql
     CHECK (action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change'))
     ```
   * Preservar íntegramente todos los registros históricos de auditoría preexistentes.
   * Preservar claves foráneas a `tasks.id` (`ON DELETE CASCADE`) y `users.id`.
   * Preservar índices `idx_audit_logs_task` e `idx_audit_logs_actor`.
4. Migración de Datos Existentes:
   * Al contar con `DEFAULT 'media'` y `server_default='media'`, todas las tareas preexistentes en la base de datos recibirán automáticamente `priority = 'media'` y `category_id = NULL`.

#### 5.2 Puerta de Verificación de Migración (Stop Gate)
1. Probar la migración en base limpia temporal desde 001 hasta 003.
2. Probar la migración sobre bases de prueba creadas por la suite (y opcionalmente sobre una copia temporal efímera y aislada si se desea contrastar con datos preexistentes) y verificar mediante conteos dinámicos (`COUNT(*)`) antes y después que:
   * La tabla `users` conserva el 100% de sus registros.
   * La tabla `tasks` conserva el 100% de sus registros, recibiendo todas `priority = 'media'` y `category_id = NULL`.
   * La tabla `audit_logs` conserva el 100% de sus registros intactos.
3. Regla irrestricta de aislamiento: `taskcontrol.db` y `taskcontrol_backup.db` permanecen estrictamente intactas y sin modificar; no se sobrescribe el respaldo ni se aplica la migración sobre las bases reales durante la implementación o validación automatizada.

---

### 6. Pruebas Automatizadas Bloqueantes

Siguiendo el **Principio III** (*Enfoque Test-First y Verificación Automatizada*), se establecen las siguientes pruebas como compuertas obligatorias:

#### 6.1 Pruebas Unitarias Bloqueantes (`tests/unit/`)
1. **Prioridad por Defecto**:
   * `test_create_task_assigns_default_media_priority`: Crear tarea sin prioridad asigna `'media'`.
   * `test_create_task_invalid_priority_raises_validation_error`: Asignar valor distinto a `alta`, `media`, `baja` lanza `ValidationError`.
2. **Ordenamiento Predeterminado vs Ordenamiento por Prioridad**:
   * `test_task_list_default_order_is_creation_descending`: Al no especificar parámetro de ordenación (o con `sort='created_desc'`), las tareas se ordenan cronológicamente por fecha de creación descendente (`created_at DESC`).
   * `test_task_list_ordering_by_priority_desc_when_requested`: Al solicitar explícitamente `sort='priority_desc'`, la lista devuelve estrictamente: `alta` → `media` → `baja`.
   * `test_task_list_ordering_by_priority_asc_when_requested`: Al solicitar explícitamente `sort='priority_asc'`, devuelve `baja` → `media` → `alta`.
   * `test_task_list_ordering_tie_breaking`: Tareas con la misma prioridad desempatan por fecha de creación descendente (`created_at DESC`).
3. **Categorías y Desvinculación sin Cascada**:
   * `test_create_category_success_and_unique_per_user`: Creación válida y rechazo de nombres duplicados para el mismo usuario.
   * `test_categories_isolated_between_different_users`: Dos usuarios pueden tener categorías con el mismo nombre sin interferencias.
   * `test_delete_category_unlinks_tasks_without_deleting_them`: Al eliminar una categoría con tareas asociadas, las tareas permanecen activas en la base de datos con `category_id = None`.
4. **Cálculo de Tareas Vencidas**:
   * `test_is_overdue_true_for_past_due_date_pending_or_in_progress`: Tarea con fecha de ayer o anterior en estado pendiente o en progreso evalúa a `is_overdue = True`.
   * `test_is_overdue_false_for_today_due_date`: Tarea con fecha límite del día de hoy en UTC evalúa a `is_overdue = False`.
   * `test_is_overdue_false_for_future_due_date`: Tarea con fecha de mañana o posterior evalúa a `is_overdue = False`.
   * `test_is_overdue_false_for_completed_task_even_if_past_due`: Tarea completada cuya fecha límite pasó evalúa a `is_overdue = False`.
   * `test_is_overdue_false_for_deleted_task_even_if_past_due`: Tarea eliminada lógicamente evalúa a `is_overdue = False`.
   * `test_is_overdue_false_when_due_date_is_none`: Tarea sin fecha límite evalúa a `is_overdue = False`.

#### 6.2 Pruebas de Integración Bloqueantes (`tests/integration/`)
1. `test_api_tasks_get_with_status_category_and_sort_filters`: Validación integral de endpoints combinando filtros de estado, filtro de categoría y ordenamiento por prioridad.
2. `test_category_crud_and_multi_user_isolation`: Validación de rutas HTTP y API para creación, listado y eliminación de categorías asegurando que un usuario no pueda operar sobre categorías de otro.
3. `test_migration_003_preserves_existing_tasks_with_default_priority`: Comprueba sobre base temporal con datos creados por la suite (o sobre copia temporal efímera sin tocar bases reales) que la migración 003 preserva el conteo de tareas preexistentes asignando dinámicamente `priority = 'media'` y `category_id = NULL`.
4. `test_migration_003_audit_logs_check_constraint_allows_new_actions`: Comprueba que tras aplicar la migración 003, la tabla `audit_logs` acepta exitosamente la inserción de registros con `action='priority_change'` y `action='category_change'`, preserva dinámicamente todos los registros existentes de auditoría, y continúa rechazando acciones no autorizadas.
