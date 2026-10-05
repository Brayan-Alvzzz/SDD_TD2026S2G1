# Technical Research: Organización y Priorización de Tareas (Incremento 3)

**Feature**: [spec.md](spec.md) | **Date**: 2026-10-04 | **Branch**: `003-task-organization-prioritization`

---

## 1. Decisiones de Arquitectura y Persistencia

### Decisión 1: Modelado de Prioridad en Entidad Task y Base de Datos
* **Decisión**: Incorporar un atributo `priority` como `String(10)` en `Task` y `TaskORM`, con valor obligatorio, valor por defecto `'media'`, y restricción de dominio/base de datos `CHECK (priority IN ('alta', 'media', 'baja'))`.
* **Razón**: Satisface directamente HU-07 y el criterio de valor por defecto explícito. Mantenerlo como texto legible con restricción CHECK asegura semántica clara en consultas SQL y en la capa de dominio sin necesidad de mapeos numéricos oscuros.
* **Alternativas evaluadas**:
  - *Entero (1, 2, 3)*: Requiere traducción constante en contratos JSON y plantillas. Se descartó por legibilidad y simplicidad.
  - *Tabla separada de prioridades*: Violación de YAGNI (Principio V), pues los niveles son fijos (`alta`, `media`, `baja`) y no configurables por el usuario.

### Decisión 2: Modelado de Categorías y Regla de Desvinculación sin Cascada
* **Decisión**: Crear una nueva entidad `Category` / `CategoryORM` con clave foránea opcional `category_id` en `tasks`, configurada con `ondelete='SET NULL'` y `nullable=True`.
* **Razón**: Satisface el requerimiento estricto de HU-08: eliminar una categoría desvincula sus tareas en vez de eliminarlas. Al contar con `PRAGMA foreign_keys = ON` habilitado por defecto en todas las conexiones SQLite de la aplicación (cerrado en el Incremento 2), la base de datos ejecuta automáticamente la desvinculación a nivel referencial cuando se elimina la fila en `categories`.
* **Comportamiento en SQLite**:
  - En la tabla `tasks`: `FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL`.
  - Cuando se ejecuta `DELETE FROM categories WHERE id = :id;`, el motor SQLite actualiza todas las filas asociadas en `tasks` fijando `category_id = NULL` en la misma transacción atómica.
* **Aislamiento multi-usuario**:
  - La tabla `categories` cuenta con una restricción única por usuario: `UNIQUE(user_id, name)` para impedir categorías duplicadas del mismo usuario, permitiendo que usuarios distintos utilicen el mismo nombre (ej. "Trabajo").
* **Alternativas evaluadas**:
  - *Eliminación lógica de categorías*: No solicitada en HU-08 ni en el backlog. Añadiría complejidad innecesaria (`is_deleted` en categorías).
  - *Desvinculación manual por bucle en Python*: Ineficiente y propenso a inconsistencias frente a la garantía ACID nativa del motor con `ON DELETE SET NULL`.

### Decisión 3: Cálculo Dinámico del Indicador de Vencimiento (HU-09)
* **Decisión**: El indicador `is_overdue` se calcula estrictamente en tiempo de ejecución en la capa de servicios de dominio (`TaskService`) y se inyecta como propiedad booleana derivada en el contrato de datos entregado al frontend y API. NUNCA se persiste como columna en la tabla `tasks`.
* **Regla de cálculo**:
  - Formato de fecha: `due_date` es una cadena de fecha de calendario `YYYY-MM-DD` sin hora.
  - Fecha de referencia: Fecha actual del sistema obtenida en UTC (`datetime.now(timezone.utc).strftime("%Y-%m-%d")`).
  - Condición de vencimiento:
    ```python
    is_overdue = bool(
        not is_deleted
        and status != "completada"
        and due_date
        and due_date.strip()
        and due_date < today_utc
    )
    ```
  - **Regla para la fecha de hoy**: Si `due_date == today_utc`, la tarea **NO** está vencida. Vence únicamente cuando `due_date < today_utc`.
* **Razón**: Elimina la necesidad de trabajos cron o tareas en segundo plano para sincronizar una columna física, previene condiciones de carrera y asegura consistencia absoluta y centralizada en el backend (Principio II).
* **Alternativas evaluadas**:
  - *Columna persistida `is_overdue`*: Requeriría un proceso periódico de actualización (cron) o disparadores complejos, introduciendo riesgo de desincronización y violando el Principio V (YAGNI).
  - *Cálculo en JavaScript*: Prohibido explícitamente por el Principio II y HU-09 para evitar fallos por desfase de zona horaria o reloj del cliente.

### Decisión 4: Extensión del Listado con Filtros y Ordenamiento Combinados
* **Decisión**: El repositorio `TaskRepository` y el servicio `TaskService` amplían el método de listado para recibir parámetros opcionales:
  - `status: Optional[str] = None` ('todas', 'pendiente', 'en_progreso', 'completada').
  - `category_id: Optional[Union[int, str]] = None` (ID entero para categoría específica, o `'none'` para tareas sin categoría).
  - `sort: str = "created_desc"` ('created_desc', 'priority_desc', 'priority_asc').
* **Preservación del orden predeterminado**:
  - Si el usuario no selecciona un criterio de ordenación (o se mantiene el valor por defecto `created_desc`), el listado se ordena **cronológicamente por fecha de creación descendente** (`created_at DESC`), conservando exactamente el comportamiento y apariencia de los Incrementos 1 y 2.
  - La jerarquía `alta` → `media` → `baja` se aplica **únicamente cuando el usuario selecciona explícitamente ordenar por prioridad** (`sort='priority_desc'`).
* **Mapeo de ordenamiento en SQL**:
  - Cuando se solicita `priority_desc`:
    ```sql
    ORDER BY
      CASE priority
        WHEN 'alta' THEN 1
        WHEN 'media' THEN 2
        WHEN 'baja' THEN 3
        ELSE 4
      END ASC,
      created_at DESC
    ```
  - Cuando se solicita `priority_asc`:
    ```sql
    ORDER BY
      CASE priority
        WHEN 'baja' THEN 1
        WHEN 'media' THEN 2
        WHEN 'alta' THEN 3
        ELSE 4
      END ASC,
      created_at DESC
    ```
  - Esto garantiza que tareas con igual prioridad mantengan un orden secundario determinista y reproducible por fecha de creación.
* **Compatibilidad hacia atrás**: Si no se envían parámetros adicionales, el comportamiento permanece 100% idéntico al de los Incrementos 1 y 2.

### Decisión 5: Estrategia de Migración Alembic (Revisión 003)
* **Decisión**: Generar la revisión `003_task_organization_prioritization.py` mediante Alembic en modo batch (`recreate="always"` para SQLite), asegurando:
  1. Creación de la tabla `categories`.
  2. Modificación de la tabla `tasks` para añadir `priority` (con default `'media'`) y `category_id` (FK `SET NULL`).
  3. Preservación íntegra de los datos existentes comparando conteos dinámicos (`COUNT(*)`) antes y después, donde todas las tareas preexistentes quedan con `priority = 'media'` y `category_id = NULL`.
* **Aislamiento y Pruebas de migración**: Pruebas automáticas en base limpia y sobre bases de prueba aisladas (u opcionalmente copia temporal efímera) antes de cualquier aplicación; `taskcontrol.db` y `taskcontrol_backup.db` permanecen intactas y sin modificar.

### Decisión 6: Ampliación Segura de la Restricción `chk_audit_logs_action` en Migración 003
* **Contexto**: En la revisión 002, la tabla `audit_logs` posee la restricción:
  ```sql
  CHECK (action IN ('create', 'update', 'status_change', 'delete', 'reopen'))
  ```
  El registro de los nuevos eventos `priority_change` (HU-07) y `category_change` (HU-08) sería rechazado por SQLite si no se amplía esta restricción.
* **Decisión**: Incluir en la migración 003 la recreación segura en modo batch de `audit_logs` (`batch_alter_table("audit_logs", recreate="always")`), definiendo la restricción ampliada:
  ```sql
  CHECK (action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change'))
  ```
* **Garantías de seguridad e integridad**:
  - Se copian íntegramente todos los registros históricos preexistentes de `audit_logs`.
  - Se conservan las claves foráneas a `tasks.id` (`ON DELETE CASCADE`) y `users.id`.
  - Se preservan los índices `idx_audit_logs_task` e `idx_audit_logs_actor`.
* **Prueba automatizada requerida**: Se incluye la prueba de integración `test_audit_logs_check_constraint_allows_new_actions_in_migration_003` que verifica que, tras aplicar la migración 003, la base de datos acepta inserciones con `action='priority_change'` y `action='category_change'`, y continúa rechazando acciones inválidas no permitidas.

