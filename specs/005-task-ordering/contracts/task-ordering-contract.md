# HTTP Contract: Task Ordering

## 1. `PATCH /api/tasks/order`

**Description**: Persiste el orden visual arrastrado por el usuario autenticado para sus propias tareas.

### Request
- **Auth**: Sesión activa requerida (Cookie `session`).
- **Headers**:
  - `Content-Type: application/json`
- **Body**: Un arreglo JSON de enteros que representan los IDs de las tareas en su nuevo orden secuencial.

```json
{
  "task_ids": [4, 1, 9, 2]
}
```

### Validation Precedence & Error Responses

1. **Autenticación (401)**: Si no hay sesión válida o el usuario no existe.
2. **Estructura (400)**: 
   - No es JSON válido.
   - Faltan claves (`task_ids`).
   - El valor no es un arreglo.
   - El arreglo contiene elementos que no son enteros.
   - El arreglo contiene IDs duplicados (`len(set(task_ids)) != len(task_ids)`).
3. **Permisos y Existencia**:
   - **403 Forbidden**: Si el payload incluye una tarea en la que el actor figura como asignado (assignee) pero el propietario es otro usuario. (Las tareas asignadas no pueden ser reordenadas por el asignado en el listado de este modo).
   - **404 Not Found**: Si se incluye un ID ajeno (ni propietario ni asignado), inexistente o eliminado lógicamente (`is_deleted=True`).
4. **Conjunto Desactualizado (409 Conflict)**:
   - Se validará que el subconjunto completo de las tareas **propias no eliminadas** concuerde exactamente.
   - Si todos los IDs provistos son accesibles y propios, pero la longitud o los IDs no coinciden con la BD (es decir, falta alguna tarea creada recientemente o se incluye una eliminada en otra sesión), la transacción completa es abortada. No se devuelve 409 si hay IDs ajenos; los ajenos detonan 404/403 en pasos previos.
5. **Éxito (200)**: Si es exitosa y se guarda. (Ver sección Response).

### Response (Success 200 OK)

- **Headers**: `Content-Type: application/json`
- **Body**: Confirmación e idempotencia.

```json
{
  "status": "success",
  "message": "Orden actualizado correctamente.",
  "changed": 4
}
```

*Donde `changed` es el conteo de registros alterados. Si un usuario envía el mismo orden dos veces, la respuesta es 200 y puede tener `changed = 0` (Idempotencia).*

### Edge Cases
- **Lista vacía**: `{"task_ids": []}` 
  - Si el usuario no tiene tareas activas en DB: Devuelve `200 OK` (`changed: 0`).
  - Si el usuario SÍ tiene tareas activas en DB: Devuelve `409 Conflict` (conjunto desactualizado).
