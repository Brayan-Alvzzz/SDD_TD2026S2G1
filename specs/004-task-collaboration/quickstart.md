# Quickstart: Validación del Incremento 4 (Colaboración)

> [!IMPORTANT]
> **Aislamiento de bases de datos**: toda validación usa una BD temporal (`quickstart_inc4_temp.db`). No ejecutar migraciones, pruebas ni la aplicación contra `taskcontrol.db` ni `taskcontrol_backup.db`.

Este documento es una guía de validación; el código, las migraciones y las pruebas se crean en la fase de implementación (ver `tasks.md`). Contratos: [task-collaboration-api.json](./contracts/task-collaboration-api.json). Modelo: [data-model.md](./data-model.md).

## 1. Preparación (bash/zsh)

```bash
export DATABASE_PATH="quickstart_inc4_temp.db"
flask --app src.web.app:create_app db upgrade      # aplica 001 → 004
python -m src.web.app
```

Limpieza: detener el servidor, `unset DATABASE_PATH` y borrar `quickstart_inc4_temp.db`.

## 2. Escenarios manuales (tres usuarios: A propietario, B asignado, C ajeno)

1. **Asignar (HU-10)**: A crea "Tarea X" y la asigna a B por correo. Esperado: aparece en el listado de A con "Asignada a B" y en el de B con "Asignada por A".
2. **Validaciones**: A intenta asignar a un correo inexistente (400), a sí mismo (400) y a B otra vez (éxito sin cambios, sin nueva auditoría ni notificación).
3. **Notificación (HU-11)**: B ve contador 1 en la barra, abre `/notifications`, marca leída: contador 0 y la notificación sigue visible.
4. **Permisos del asignado**: B completa y reabre "Tarea X" **sin recarga** (con rollback visual si se fuerza un error); B no ve Editar/Eliminar/Asignar y las peticiones directas a editar, eliminar o reasignar devuelven 403.
5. **Ajeno**: C abre `/tasks/<id>` o llama a la API de la tarea: 404; C no puede leer ni marcar la notificación de B (404).
6. **Reasignación**: A reasigna a C: desaparece del listado de B, aparece en el de C; C recibe notificación; B conserva la suya como "ya no disponible" sin enlace, y `GET /tasks/<id>` como B devuelve 404.
7. **Desasignación y eliminación**: A desasigna (sin notificación) y vuelve a asignar a B: B tiene una notificación nueva navegable y la antigua sigue "ya no disponible". Si A elimina la tarea, B deja de verla y su notificación pasa a "ya no disponible".
8. **Listado**: filtrar por rol (todas / propias / asignadas a mí / delegadas) combinado con estado, orden y categoría: sin filas duplicadas.

## 3. Verificación automatizada (después de implementar)

```bash
mkdir -p docs/evidencias/inc4
python -m pytest -v 2>&1 | tee docs/evidencias/inc4/green-final.txt
```

Esperado: las 156 pruebas existentes más las nuevas pasan sin modificar las existentes. Cada fase conserva su salida RED (`red-<fase>.txt`) y GREEN (`green-<fase>.txt`) tal como la produce `pytest`.
