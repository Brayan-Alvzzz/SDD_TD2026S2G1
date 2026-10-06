# Research & Decisions: Task Ordering

## 1. Positional Storage Mechanism
- **Decision:** Agregar un campo numérico entero `position` (o `display_order`) en la tabla `tasks` (TaskORM).
- **Rationale:** Permite establecer un orden arbitrario mediante un número. Como se requiere "tareas nuevas al final", la creación de tareas asignará `position = MAX(position) + 1` para las tareas de ese usuario. Al eliminar una tarea, el orden relativo de las demás se mantiene, por lo que no es necesario renumerar (los huecos numéricos son irrelevantes para el orden final, que se hace mediante `ORDER BY position ASC, id ASC`).
- **Alternatives considered:** Lista enlazada (complejo de consultar, no ideal para bases de datos relacionales). Arreglo serializado en JSON (viola formas normales y es poco escalable).

## 2. Inicialización de Datos Existentes (Migración)
- **Decision:** La migración poblará el nuevo campo `position` de forma determinista asignándole un orden basado en `id` (por ejemplo, actualizando cada registro con la secuencia de su creación) u ordenando por la prioridad / fecha actual y asignando un ROW_NUMBER particionado por `user_id`. Para mantenerlo compatible con SQLite y determinista sin usar `ROW_NUMBER()` complejo en dialects sin soporte completo, se hará por medio de un script Python dentro de Alembic que cargue las tareas y les asigne una `position` secuencial `i * 10` agrupadas por `user_id` y ordenadas por `created_desc`.
- **Rationale:** SQLite en versiones antiguas puede ser complicado con funciones analíticas en UPDATE. Una pasada programática (Data Migration) en Python dentro del archivo Alembic es 100% determinista y segura para volúmenes manejables como los que tenemos.
- **Alternatives considered:** Dejar que `position` sea NULL y tratar NULL como el final, lo que complica el motor de ordenación.

## 3. Concurrencia y Validación "All-or-Nothing"
- **Decision:** El endpoint `PATCH /api/tasks/order` iniciará una transacción bloqueante en SQLite mediante `BEGIN IMMEDIATE` (si se usa crudo) o asegurando aislamiento a nivel de SQLAlchemy antes de la lectura. Luego obtendrá los IDs y verificará que coinciden exactamente con el payload.
- **Rationale:** En SQLite, una lectura `SELECT` estándar seguida de un `UPDATE` puede sufrir intercalado. Un `BEGIN IMMEDIATE` adquiere el bloqueo de escritura inmediatamente, garantizando que nadie más modifique la tabla entre la validación (lectura de IDs) y la escritura (`UPDATE`). Esto distingue un *conjunto desactualizado* (409 devuelto deliberadamente al usuario porque su frontend tenía menos/más tareas) de un bloqueo de base de datos (Database is locked, que se resuelve reintentando a nivel driver).
- **Alternatives considered:** `SELECT FOR UPDATE` (no soportado nativamente como bloqueo preventivo robusto en SQLite). Optimistic locking con columna global. El bloqueo de escritura inmediato es idiomático en SQLite para prevenir colisiones "read-modify-write".

## 4. Re-ordenamiento en Frontend
- **Decision:** Usar SortableJS (o la librería nativa de HTML5) integrándolo en la vista de `role=owned`. Solo se activa si no hay filtros activos adicionales. Al soltar (`onEnd`), se deshabilita momentáneamente y se despacha la petición AJAX a `PATCH /api/tasks/order`. Si falla, se hace rollback del DOM (SortableJS permite cancelar o simplemente recargar el orden previo guardado en memoria).
- **Rationale:** Evita incluir frameworks SPA complejos como React.
