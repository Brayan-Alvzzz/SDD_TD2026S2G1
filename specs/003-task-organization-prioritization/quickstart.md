# Quickstart: Validación Manual del Incremento 3 (Entorno Aislado)

> [!IMPORTANT]
> **Aislamiento de Bases de Datos**: Para no alterar `taskcontrol.db` ni `taskcontrol_backup.db`, toda validación manual debe realizarse sobre una base de datos temporal aislada (`quickstart_inc3_temp.db`). Bajo ninguna circunstancia se deben ejecutar migraciones, pruebas o iniciar la aplicación apuntando a las bases de datos reales ni sobre el archivo de respaldo. Ambos archivos deben permanecer estrictamente intactos.

---

## 1. Configuración del Entorno de Prueba

En una terminal PowerShell desde la raíz del repositorio:

```powershell
# 1. Configurar base temporal aislada
$env:DATABASE_PATH = "quickstart_inc3_temp.db"

# 2. Aplicar las migraciones versionadas (001, 002 y 003) sobre la base temporal
flask --app src.web.app:create_app db upgrade

# 3. Iniciar el servidor de desarrollo
python -m src.web.app
```

> [!NOTE]
> Al finalizar las pruebas, detener el servidor (`Ctrl+C`), restaurar el entorno y remover la base temporal:
> ```powershell
> Remove-Item env:DATABASE_PATH
> if (Test-Path "quickstart_inc3_temp.db") { Remove-Item "quickstart_inc3_temp.db" }
> ```

---

## 2. Escenarios de Validación Manual

### Escenario A: Prioridad de Tareas y Ordenamiento (HU-07)
1. Navegar a `http://localhost:5000/register` y registrar un usuario de prueba (ej. `usuario3@test.com` con `clave12345`).
2. En `/tasks`, crear una tarea "Tarea Sin Selección de Prioridad": verificar que el formulario muestra "media" por defecto y que la tarea se guarda con prioridad `media`.
3. Crear una tarea "Tarea Urgente" seleccionando prioridad `alta`.
4. Crear una tarea "Tarea de Rutina" seleccionando prioridad `baja`.
5. En el listado sin seleccionar orden: comprobar que las tareas conservan el orden cronológico descendente por fecha de creación ("Tarea de Rutina", "Tarea Urgente", "Tarea Sin Selección").
6. En el control de ordenamiento del listado, seleccionar explícitamente "Ordenar por prioridad (Alta primero)":
   - Comprobar que el listado sitúa en primer lugar "Tarea Urgente" (alta), seguida de "Tarea Sin Selección" (media) y al final "Tarea de Rutina" (baja).
7. Aplicar un filtro por estado (ej. "pendiente") y verificar que el ordenamiento por prioridad se mantiene activo de manera combinada.
8. Modificar la prioridad de "Tarea de Rutina" a `alta`: comprobar que se reubica entre las de prioridad alta y se genera un registro en el log de auditoría con acción `priority_change`.

### Escenario B: Categorías y Desvinculación sin Cascada (HU-08)
1. Navegar a la sección de categorías (`http://localhost:5000/categories`).
2. Crear una categoría llamada "Proyecto Alfa".
3. Intentar crear nuevamente una categoría llamada "Proyecto Alfa": verificar que el sistema rechaza la creación por nombre duplicado para el mismo usuario.
4. En `/tasks`, crear una tarea "Entregable 1" y asignarle la categoría "Proyecto Alfa".
5. Crear una segunda tarea "Entregable 2" asignada también a "Proyecto Alfa".
6. En el listado de tareas, filtrar por la categoría "Proyecto Alfa":
   - Comprobar que únicamente se muestran "Entregable 1" y "Entregable 2".
7. Regresar a `/categories` y pulsar «Eliminar» en la categoría "Proyecto Alfa" aceptando el diálogo de confirmación:
   - La categoría "Proyecto Alfa" desaparece de la lista de categorías.
8. Regresar al listado general de tareas (`/tasks`):
   - **Comprobación crítica**: "Entregable 1" y "Entregable 2" **continúan existiendo y activas** en el sistema.
   - Ambas tareas figuran ahora con la indicación "Sin categoría" (`category_id = NULL`), demostrando que no hubo eliminación en cascada.

### Escenario C: Indicación Confiable de Tareas Vencidas en Backend (HU-09)
1. En `/tasks`, crear una tarea "Tarea Vencida de Ayer" con fecha límite configurada para la fecha de ayer (YYYY-MM-DD) y estado `pendiente`.
2. Crear una tarea "Tarea de Hoy" con fecha límite igual a la fecha actual del día de hoy en UTC (YYYY-MM-DD) y estado `pendiente`.
3. Crear una tarea "Tarea a Futuro" con fecha límite para el próximo mes.
4. Crear una tarea "Tarea Sin Fecha" sin fecha límite.
5. Observar el listado de tareas:
   - "Tarea Vencida de Ayer": muestra de forma destacada la insignia roja **«Vencida»**.
   - "Tarea de Hoy": **NO** muestra insignia de vencida (su fecha límite no ha sido superada).
   - "Tarea a Futuro": **NO** muestra insignia de vencida.
   - "Tarea Sin Fecha": **NO** muestra insignia de vencida.
6. Cambiar el estado de "Tarea Vencida de Ayer" a `completada`:
   - Comprobar que la insignia **«Vencida»** desaparece inmediatamente.
7. Reabrir la tarea completada (HU-06):
   - Al volver a estado `pendiente`, el backend recalcula su condición y la tarea vuelve a mostrarse como **«Vencida»**.
