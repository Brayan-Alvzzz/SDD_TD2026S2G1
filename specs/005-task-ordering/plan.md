# Implementation Plan: 005-task-ordering

**Branch**: `sebastian/incrementos-4-5` | **Date**: 2026-10-06 | **Spec**: [specs/005-task-ordering/spec.md](specs/005-task-ordering/spec.md)

**Input**: Feature specification from `/specs/005-task-ordering/spec.md`

## Summary

Implementar la capacidad de reordenar visualmente tareas propias (y preservarlo en backend) mediante Drag & Drop desde la vista principal (`role=owned`). Se aplicará persistencia atómica, una política estricta anti-desfases de concurrencia y no requerirá frameworks SPA. 

## Technical Context

**Language/Version**: Python 3.11 / Vanilla JS (ES6)

**Primary Dependencies**: Flask, SQLAlchemy, Alembic, Playwright (Testing)

**Storage**: SQLite (requiere manejo cuidadoso de commits y aislamientos).

**Testing**: pytest + Playwright

**Target Platform**: Web Browsers (Desktop/Mobile compatibility)

**Project Type**: Monolithic Web Application

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
- [x] YAGNI: No se instalan SPAs (React/Vue). Se resuelve con un endpoint simple y nativo HTML5 Drag & Drop (o Sortable liviano si el nativo resulta improductivo, pero el plan arranca con HTML5 nativo o JS existente).
- [x] Modular Monolith: El código se añade en la capa de servicios y rutas correspondientes (TaskService, task_routes.py).
- [x] Test-Driven: Pruebas asíncronas y del servicio claramente delimitadas en el plan.

## Project Structure

### Documentation (this feature)

```text
specs/005-task-ordering/
├── plan.md              
├── research.md          
├── data-model.md        
├── quickstart.md        
├── contracts/task-ordering-contract.md 
└── tasks.md             (To be generated)
```

### Source Code (repository root)

```text
# Option 1: Single project (DEFAULT)
migrations/
└── versions/
    └── [new_migration_file_task_ordering].py
src/
├── domain/
│   └── models.py      # Add 'position' to Task
│   └── services.py    # Add reorder_tasks method to TaskService
├── infrastructure/
│   └── models.py      # Add 'position' column to TaskORM
│   └── repositories.py # Atomic ordering updates (ensure no partial commits)
├── web/
│   └── task_routes.py # Add PATCH /api/tasks/order route
│   └── static/js/
│       └── api.js     # Add API call
│       └── tasks.js   # Add Drag&Drop events and handlers
│   └── templates/
│       └── tasks/index.html # Add draggable attributes & tooltips
tests/
├── integration/
│   └── test_migrations.py
│   └── test_task_services.py
│   └── test_task_routes.py
│   └── test_task_ordering_html.py # UI Drag & Drop + Playwright
```

**Structure Decision**: El proyecto es un monolito clásico (Option 1). Se añadirán columnas y rutas respetando la división Infra/Dominio/Web.

## Phase 1 Design Details

### 1. Persistencia
- Modificar `Task` y `TaskORM` agregando `position` (`db.Integer, nullable=False, default=0, server_default='0'`).
- Modificar el comportamiento de lectura/listar para usar `ORDER BY position ASC, id ASC`.
- La inserción de nuevas tareas buscará la posición actual más alta de las tareas del usuario (activas) y asignará el siguiente número (creciendo). Las tareas se crean al final de la lista.
- Borrar una tarea solo pone `is_deleted = True`, dejando el orden de las demás intacto pero comprimiendo su relación virtual, lo cual conserva perfectamente su orden visual relativo.
- La migración incluirá la lógica programática (Data Migration) usando la conexión base de Alembic para asegurar la inicialización de los datos actuales, garantizando un índice determinista.
- Ningún atributo de lógica de negocio (status, prioridad, due_date, assignee) será mutado al reordenar.

### 2. Servicio y transacción
- Endpoint y Servicio extraerán el `actor` de la sesión segura actual.
- Se implementará el método `TaskService.update_task_order(user_id: int, task_ids: List[int]) -> int`.
- **Validación Atómica y Concurrencia**:
  1. Adquirir el bloqueo de escritura inmediatamente mediante una sentencia de actualización idempotente (`sa.update(...)`) manejada por SQLAlchemy dentro del bloque transaccional general, para escalar la transacción a `RESERVED`/`EXCLUSIVE` en SQLite sin requerir commits prematuros ni consultas crudas fuera del ORM.
  2. Extraer todos los IDs vivos y propios del usuario (`is_deleted=False`).
  3. Comprobar que no hay duplicados (len(set) == len(list)). Si hay, 400.
  4. Comprobar permisos/existencia (403/404).
  5. Comparar los sets de la BD (vivos) vs el request: `if set(db_vivos) != set(task_ids): raise ConflictError("Desactualizado")`.
  6. La iteración actualizará `position` de cada ORM entity a su índice en el arreglo `(0..N)`.
  7. Se usará un `session.commit()` final único. Todo error derivará en un solo `session.rollback()`. No habrá commits de repositorios parciales.
- El último `commit()` válido triunfa ("Last write wins"). Una repetición produce 0 cambios (Idempotente).
- Se creará un `AuditLog` del tipo `"reorder"` agrupando el evento general.

### 3. Contrato `PATCH /api/tasks/order`
- Ya cubierto extensamente en [contracts/task-ordering-contract.md](contracts/task-ordering-contract.md). 
- Errores definidos inequívocamente: 
  - 401 (sin sesión).
  - 400 (malformado, no enteros o duplicados).
  - 403 (contiene IDs asignados pero no propios).
  - 404 (contiene IDs ajenos inexistentes o eliminados).
  - 409 (lista desactualizada por desincronización de sesión: todos los IDs provistos son válidos y propios, pero faltan o sobran respecto al estado vivo en la base de datos).
- Precedencia respetada (Auth -> Estructura -> Permisos/Existencia (403/404) -> Concurrencia exacta (409)).

### 4. Listado e Interfaz
- Se aplicará atributo `draggable="true"` en los list-items usando JavaScript si y solo si la vista es `Mis Tareas` y no hay un ordenamiento de interfaz activado distinto.
- Drag & Drop nativo de HTML5 con eventos `dragstart`, `dragover`, `drop`.
- Al soltar (`drop`):
  1. Se suspende la capacidad de mover temporalmente y se recopilan todos los IDs (`data-task-id`) en el DOM actual en orden de aparición.
  2. Petición PATCH asíncrona a `api.js`.
  3. Si falla (409), muestra mensaje `toast/alert`: "El listado está desactualizado. Se recargará para mostrar cambios." y puede gatillar `window.location.reload()`.
  4. Si falla por red u otra cosa (500), se deshace el DOM al orden de guardado previo y se avisa.
- Las funciones asíncronas de la HU-15 se conservan y operan igual, dado que el DOM sigue siendo el mismo y el JS sigue inyectado.

### 5. Estrategia de Pruebas
1. **Migrations**: Comprobar que al lanzar `flask db upgrade` la base de datos se modifica. Tareas viejas reciben un orden base y no quedan NULL.
2. **Domain/Service (Integration)**: `test_task_services.py` probará la persistencia desde sesión independiente de SQLAlchemy, emulando la ausencia total de commits fantasma, verificando el rechazo por desactualización o IDs ajenos, y el guardado exitoso con la posición mutada.
3. **Web Routes**: `test_task_routes.py` validará estrictamente las respuestas 401, 400, 404 y 409 del contrato.
4. **Browser (Playwright)**: `test_task_ordering_html.py`. Emular arrastre DOM a DOM usando eventos sintéticos de Playwright (o API mouse actions) y comprobando que `fetch` reciba y se pinte bien, sobreviviendo la recarga (F5).
5. **Cierre de Ciclo**: Mantendremos bloques concisos `RED` seguidos de implementaciones con evidencia real (`GREEN`), finalizando con regresión de suite completa.
