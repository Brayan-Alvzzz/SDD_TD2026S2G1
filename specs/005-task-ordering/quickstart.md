# Quickstart: Validation Guide for Task Ordering

## 1. Prerequisites

- Aplicación corriendo localmente (ejecutar `flask run` o `python -m flask run`).
- Base de datos actualizada ejecutando el comando: `flask db upgrade` (inicializará el campo `position` de forma determinista para tareas existentes).
- Usuario de prueba autenticado (ej: `test@example.com`).

## 2. Test Setup (Manual)

- Ingresar al listado de tareas ("Mis Tareas" en modo `role=owned`).
- Asegurarse de que no existan filtros de estado o categoría (URL no debe tener `?status=X` ni `?sort=Y`).
- Crear 3 tareas: "Tarea A", "Tarea B", "Tarea C". Quedarán ordenadas por defecto A (arriba), B (medio), C (abajo).

## 3. Validation Scenarios

### Scenario A: Drag and Drop Persistence
1. Arrastrar "Tarea C" y soltarla arriba de "Tarea A".
2. **Expected Local Outcome**: Visualmente el orden cambia a C, A, B. El icono de carga (si existe) desaparece, confirmando guardado.
3. **Persistencia E2E**: Recargar la página (F5 o Ctrl+R).
4. **Expected Outcome**: El orden C, A, B se mantiene idéntico.

### Scenario B: Concurrent Out-of-Sync Rejection (409)
1. Abrir una pestaña incógnito, iniciar sesión con el mismo usuario.
2. En incógnito, crear "Tarea D".
3. Volver a la pestaña normal (desactualizada). Arrastrar "Tarea B" al primer lugar.
4. **Expected Outcome**: El DOM intentará reordenar, pero la solicitud fallará devolviendo un `409 Conflict`. El frontend restaurará la tarea a su lugar original (rollback visual) y lanzará un error que indica que la vista está desactualizada y sugiere recargar la página.

### Scenario C: No Drag-And-Drop en Vistas Filtradas
1. Cambiar el filtro a "Completadas" o "Asignadas a mí".
2. Intentar arrastrar una tarea usando el handle de mover.
3. **Expected Outcome**: El arrastre debe estar deshabilitado nativamente (no existe el atributo `draggable="true"` ni la clase `drag-handle`). No se iniciará el evento.
