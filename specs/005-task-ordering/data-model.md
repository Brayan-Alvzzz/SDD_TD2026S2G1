# Data Model: Task Ordering

## 1. Entities

### Task
Se expande la entidad `Task` y su correspondencia `TaskORM` con el siguiente campo numérico.

**Nuevos Campos**:
- `position` (integer, nullable=False, default=0, server_default='0'): Determina el orden relativo de las tareas de un usuario. Un valor menor significa que la tarea aparece primero en la lista.
  
**Comportamiento del ciclo de vida**:
- *Creación*: Las tareas nuevas se insertan al final. El repositorio buscará la posición más alta entre las tareas no eliminadas del usuario y le sumará 10 (o 1) a la nueva tarea.
- *Eliminación*: Se mantiene la eliminación lógica (`is_deleted = True`). El campo `position` de las tareas restantes no cambia, lo que preserva su orden relativo.
- *Actualización individual (Estado, Prioridad, etc.)*: Modificar un campo distinto no debe alterar la `position`. 
- *Resolución de Empates (Tie-breaking)*: A nivel de consulta SQL, la cláusula de ordenamiento será `ORDER BY position ASC, id ASC`.

## 2. Validation & Constraints

- **Restricción de Integridad**: Ningún cambio en base de datos; la cardinalidad sigue siendo la misma. 
- **Validación Lógica**: Solo las tareas propiedad del usuario (`user_id = X`) tienen garantizada una progresión de `position` coherente entre sí. Tareas compartidas (asignadas) no entran en este esquema organizativo (el usuario asignado las verá de otra forma, típicamente por prioridad o fecha).

## 3. Data Migration (Alembic)

Se requiere un script de migración que inicialice el campo `position` para asegurar un comportamiento determinista.
- **Acción:** `ALTER TABLE tasks ADD COLUMN position INTEGER NOT NULL DEFAULT 0;`
- **Población (Data Migration)**: Iterar mediante SQLAlchemy u operaciones de SQL cada usuario. Para cada `user_id`, obtener sus tareas ordenadas por la fecha de creación descendente (el orden default actual). Asignar a la primera `position = 10`, a la segunda `position = 20`, y así sucesivamente. (Los incrementos de a 10 ayudan a inserciones manuales si se requiriera, pero para reordenaciones masivas cualquier índice secuencial funciona).
