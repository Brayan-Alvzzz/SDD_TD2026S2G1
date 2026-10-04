# Quickstart & Verification Guide: Incremento 2

**Feature**: `002-task-lifecycle-access-recovery`  
**Date**: 2026-10-04 (Actualizado)  
**Status**: Ready for Implementation  

---

## 1. Prerrequisitos y Configuración de Entorno

Asegurarse de tener el entorno virtual activo y las dependencias actualizadas:

```powershell
# Activar entorno virtual en Windows PowerShell
.\venv\Scripts\Activate.ps1

# Instalar dependencias requeridas (Flask, Flask-SQLAlchemy, Flask-Migrate, pytest)
pip install -r requirements.txt
```

---

## 2. Procedimiento Reproducible de Migraciones y Preservación de Datos

> [!WARNING]
> **No autogenerar contra la base poblada sin versionar**: Queda estrictamente prohibido generar la revisión 002 contra la base de trabajo `taskcontrol.db` sin versionar. Si se ejecuta `flask db migrate` directamente sobre una base ya poblada, Alembic omitirá sentencias y generará revisiones vacías o inconsistentes.
> **Prohibido el uso de `db.create_all()`**: Las migraciones versionadas de Flask-Migrate deben ser el único mecanismo de evolución de la base de datos.
> **El cambio de CHECK en SQLite no es autogenerado**: Alembic no detecta modificaciones de `CheckConstraint` en SQLite; la revisión 002 debe incorporar manualmente la recreación en modo batch (`recreate="always"`).

### Paso 1: Generación Limpia de la Revisión 001 (Incremento 1)
Genera la revisión inicial contra una base de datos nueva/vacía para garantizar que el archivo `001_initial_schema.py` contenga las sentencias `create_table` completas:

```powershell
# Usar base de datos limpia temporal
$env:DATABASE_PATH = "clean_init.db"

# Inicializar repositorio de migraciones (crea carpeta migrations/)
flask --app src.web.app:create_app db init

# Generar la revisión inicial 001 completa
flask --app src.web.app:create_app db migrate -m "001_initial_schema"

# Inspeccionar migrations/versions/*001_initial_schema.py y verificar que contenga
# las tablas 'users', 'tasks', 'audit_logs' con restricciones (NOCASE, CHECKs) e índices.
```

### Paso 2: Aplicación de la Revisión 001 sobre `clean_init.db`
Mantén `clean_init.db` y aplícale la revisión 001 para que alcance exactamente dicho estado de esquema:

```powershell
# Reemplazar <rev_001_id> con el prefijo ID de la revisión 001
flask --app src.web.app:create_app db upgrade <rev_001_id>
```

### Paso 3: Ampliación de Modelos y Generación de la Revisión 002
Una vez que los modelos ORM en `src/infrastructure/models.py` incluyen `is_deleted`, `deleted_at`, la restricción ampliada de `audit_logs` y `PasswordResetTokenORM`, genera la revisión 002 apuntando **todavía** a `clean_init.db`:

```powershell
# Generar la revisión incremental 002 sobre clean_init.db (ya en versión 001)
# ¡NUNCA generar la revisión 002 contra la base de trabajo sin versionar!
flask --app src.web.app:create_app db migrate -m "002_task_lifecycle_recovery"
```

### Paso 4: Revisión Manual de la Revisión 002 y Limpieza Temporal
Alembic no autogenera modificaciones de restricciones `CHECK` en SQLite. Edita manualmente `migrations/versions/*002_task_lifecycle_recovery.py` para asegurar el uso de `batch_alter_table("audit_logs", recreate="always")` con el nuevo `CHECK (action IN ('create', 'update', 'status_change', 'delete', 'reopen'))`. Luego limpia la base temporal:

```powershell
# Restaurar variable de entorno y remover base de prueba inicial
Remove-Item env:DATABASE_PATH
if (Test-Path "clean_init.db") { Remove-Item "clean_init.db" }
```

### Paso 5: Pruebas Automatizadas de Migración y Parada de Verificación
Ejecuta la suite de pruebas de migración para validar tanto la creación desde cero como la preservación en copia:

```powershell
pytest tests/integration/test_migrations.py -v
```

> [!CRITICAL]
> **PARADA DE VERIFICACIÓN**: Si alguna de las pruebas en `test_migrations.py` falla, DETENERSE y corregir. No tocar ni estampar `taskcontrol.db` hasta tener 100% de éxito en las pruebas automatizadas.

### Paso 6: Respaldo y Comprobación Previa de `taskcontrol.db`
Antes de cualquier modificación sobre la base real:

```powershell
# 1. Crear respaldo obligatorio
Copy-Item taskcontrol.db taskcontrol_backup.db

# 2. Registrar conteos y esquema iniciales
python -c "import sqlite3; conn = sqlite3.connect('taskcontrol.db'); cur = conn.cursor(); print('users:', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]); print('tasks:', cur.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]); print('audit_logs:', cur.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0])"
# Conteos esperados: users: 1, tasks: 4, audit_logs: 7
```

### Paso 7: Estampado Exclusivo de la Revisión 001
Estampa en `taskcontrol.db` **únicamente la revisión 001**, nunca `head`:

```powershell
# Reemplazar <rev_001_id> con el ID real de la revisión 001 (ej. 3a7b1c4d9e2f)
flask --app src.web.app:create_app db stamp <rev_001_id>
```

### Paso 8: Aplicación de la Revisión 002 sobre `taskcontrol.db`
Aplica los cambios incrementales sobre la base de datos de trabajo:

```powershell
# Aplicar la migración 002 sobre taskcontrol.db
flask --app src.web.app:create_app db upgrade
```

### Paso 9: Comprobación de Preservación de Datos Post-Migración
Verificar que todos los registros se preservaron y que las nuevas columnas e índices existen:

```powershell
python -c "import sqlite3; conn = sqlite3.connect('taskcontrol.db'); cur = conn.cursor(); print('users post-migracion:', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]); print('tasks post-migracion:', cur.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]); print('audit_logs post-migracion:', cur.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]); cur.execute('SELECT id, is_deleted, deleted_at FROM tasks'); print('Valores tasks:', cur.fetchall())"
# Comprobar que users=1, tasks=4, audit_logs=7 y que is_deleted=0 para las 4 tareas existentes.
```

---

## 3. Verificación Automatizada (Pruebas Bloqueantes)

Ejecutar la suite completa con `pytest`:

```powershell
pytest -v
```

### Casos de Prueba Bloqueantes Obligatorios:

1. **Pruebas de Migración y Conservación de Datos (`tests/integration/test_migrations.py`)**:
   - `test_clean_database_upgrade_from_scratch`: Ejecuta `upgrade()` sobre una base vacía y comprueba que se creen las tablas `users`, `tasks`, `audit_logs`, `password_reset_tokens` y todos sus índices.
   - `test_migration_preserves_existing_data`: Carga una copia de la base con datos reales del Incremento 1, ejecuta el estampado 001 y upgrade a 002, verificando que los registros (1 usuario, 4 tareas, 7 logs) sigan intactos y que las claves foráneas funcionen.
   - `test_audit_logs_check_constraint_allows_new_actions`: Inserta registros en `audit_logs` con `action='delete'` y `action='reopen'`, comprobando que la restricción ampliada los acepta y rechaza valores inválidos.
2. **Soft Delete (`tests/unit/test_task_service.py`)**:
   - `test_soft_delete_marks_task_deleted`: Verifica `is_deleted=True` y `deleted_at` con fecha ISO 8601.
   - `test_list_tasks_excludes_deleted_tasks`: Verifica que la consulta regular de tareas (HU-02) excluya eliminadas.
   - `test_cannot_delete_already_deleted_task`: Verifica que intentar re-eliminar una tarea falle con error.
   - `test_cannot_edit_or_advance_deleted_task`: Impide editar o avanzar tareas eliminadas.
3. **Reapertura de Tarea (`tests/unit/test_state_machine.py` y `test_task_service.py`)**:
   - `test_reopen_task_transitions_to_pending`: Valida transición determinista `completada` → `pendiente`.
   - `test_reopen_fails_if_not_completed`: Rechaza reaperturas sobre estados `pendiente` o `en_progreso`.
   - `test_reopen_creates_distinct_audit_log_action`: Comprueba que `action == 'reopen'` en `audit_logs`.
4. **Recuperación de Contraseña (`tests/unit/test_user_service.py` y `test_auth_routes.py`)**:
   - `test_request_reset_neutral_response`: Mismo mensaje y código 200 en `POST /forgot-password` para correos registrados e inexistentes.
   - `test_reset_password_success`: `POST /reset-password/<token>` actualiza contraseña con hash y marca `used=True`.
   - `test_reset_password_with_expired_token_rejected`: Rechaza tokens con más de 30 minutos de antigüedad.
   - `test_reset_password_with_used_token_rejected`: Rechaza tokens reutilizados (`used=True`).
   - `test_new_request_revokes_previous_tokens`: Invalida tokens anteriores al solicitar uno nuevo.

---

## 4. Validación Manual en el Navegador Web

Iniciar el servidor de desarrollo en PowerShell:
```powershell
python -m src.web.app
```

### Escenario A: Eliminación Lógica de Tareas (HU-05)
1. Navegar a `http://localhost:5000/login` e iniciar sesión con `demo@taskcontrol.com` (`password123`).
2. En el listado de tareas (`/tasks`), ubicar una tarea activa y hacer clic en el botón de eliminar.
3. Comprobar que aparece el diálogo nativo del navegador (`confirm: "¿Desea eliminar esta tarea?"`).
4. Al confirmar, la página se recarga, la tarea ya no figura en el listado y se muestra un mensaje flash de éxito.
5. Inspeccionar la base de datos: la fila tiene `is_deleted = 1` y existe un registro en `audit_logs` con `action = 'delete'`.

### Escenario B: Reapertura de Tareas Completadas (HU-06)
1. Filtrar o ubicar una tarea en estado "completada" en `/tasks`.
2. Hacer clic en el botón "Reabrir".
3. La tarea pasa de inmediato a estado "pendiente" y se reubica entre las tareas activas.
4. Inspeccionar la base de datos: el log de auditoría tiene una nueva fila con `action = 'reopen'`, distinguiéndose claramente de `status_change` y `create`.

### Escenario C: Recuperación Segura de Contraseña (HU-14)
1. Cerrar sesión (`/logout`) y navegar a la pantalla de login (`http://localhost:5000/login`).
2. Hacer clic en "¿Olvidaste tu contraseña?" (`http://localhost:5000/forgot-password`).
3. Ingresar `demo@taskcontrol.com` y enviar el formulario.
4. Comprobar que en el navegador se muestra el mensaje neutro de confirmación:
   *"Si la dirección de correo electrónico está registrada en el sistema, se ha enviado un enlace para restablecer la contraseña."*
5. Repetir la solicitud con un correo inexistente (`ficticio@correo.com`): comprobar que la pantalla muestra exactamente el mismo mensaje neutro sin dar pistas de si la cuenta existe o no.
6. En la terminal donde corre Flask, observar la línea impresa:
   `[DEV NOTIFICATION] Enlace de restablecimiento: http://localhost:5000/reset-password/<token>`
7. Copiar el enlace de la terminal y abrirlo en el navegador.
8. Ingresar una nueva contraseña (ej. `nuevaClave2026`) y confirmar.
9. Redirige a `/login` con mensaje de éxito; iniciar sesión con la nueva contraseña.
10. Intentar volver a abrir el mismo enlace en el navegador: el sistema debe rechazar el acceso indicando que el enlace ya fue utilizado o no es válido.
