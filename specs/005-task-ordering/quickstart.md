# Quickstart: Validation Guide for Task Ordering

## 1. Prerequisites

- Aplicación corriendo localmente (`flask run`).
- Base de datos actualizada (`flask db upgrade`) inicializando los campos `position`.
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
4. **Expected Outcome**: El DOM debe intentar soltar la tarea, y luego fallar devolviendo la tarea a su lugar original (rollback visual). Se debe mostrar un mensaje "El listado está desactualizado. Se recargará para mostrar cambios de otra sesión". (Comportamiento `409 Conflict`).

### Scenario C: No Drag-And-Drop en Vistas Filtradas
1. Cambiar el filtro a "Completadas" o "Asignadas a mí".
2. Intentar arrastrar una tarea usando el handle de mover.
3. **Expected Outcome**: El arrastre debe estar deshabilitado (cursor normal o prohibido). Un tooltip o banner debe indicar que "El orden manual arrastrando solo funciona en la vista principal 'Mis tareas' sin filtros activos".
