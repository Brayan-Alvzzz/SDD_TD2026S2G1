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

## 4. Validación Manual en el Navegador Web (Entorno Aislado)

> [!IMPORTANT]
> **Aislamiento de Bases de Datos**: Para no alterar `taskcontrol.db` ni `taskcontrol_backup.db`, la validación manual debe realizarse sobre una base temporal aislada. Asimismo, la emisión de enlaces en consola requiere activar explícitamente `ENABLE_CONSOLE_PASSWORD_RESET=true`.

Configurar el entorno temporal e iniciar el servidor en PowerShell:
```powershell
# 1. Configurar base temporal aislada y activar emisión de token en consola para pruebas locales
$env:DATABASE_PATH = "quickstart_temp.db"
$env:ENABLE_CONSOLE_PASSWORD_RESET = "true"

# 2. Aplicar las migraciones versionadas (001 y 002) sobre la base temporal
flask --app src.web.app:create_app db upgrade

# 3. Iniciar el servidor de desarrollo
python -m src.web.app
```

> [!NOTE]
> Al terminar las pruebas manuales, detener el servidor (`Ctrl+C`), restaurar el entorno y remover la base temporal:
> ```powershell
> Remove-Item env:DATABASE_PATH
> Remove-Item env:ENABLE_CONSOLE_PASSWORD_RESET
> if (Test-Path "quickstart_temp.db") { Remove-Item "quickstart_temp.db" }
> ```

### Escenario A: Eliminación Lógica de Tareas (HU-05)
1. Navegar a `http://localhost:5000/register` y registrar un usuario de prueba (ej. `demo@taskcontrol.com` con `password123`).
2. Crear una o más tareas de prueba en `/tasks` (ej. "Tarea para eliminar").
3. En el listado de tareas (`/tasks`), ubicar la tarea activa y hacer clic en el botón «Eliminar».
4. Comprobar que aparece el diálogo nativo de confirmación del navegador (`confirm: "¿Está seguro de que desea eliminar esta tarea?"`).
5. Al confirmar, la tarea desaparece del listado visible y se muestra un mensaje flash de éxito.
6. Si se cancela el diálogo, la tarea permanece en el listado y no se ejecuta ninguna petición destructiva.
7. Intentar acceder por URL directa a `/tasks/<id>/edit`: el sistema responde `404 Not Found`.

### Escenario B: Reapertura de Tareas Completadas (HU-06)
1. En `/tasks`, crear una tarea "Tarea de ciclo completo" (inicia en `pendiente`).
2. Pulsar «Iniciar ▶» (transiciona a `en_progreso`).
3. Pulsar «Completar ✓» (transiciona a `completada`).
4. Comprobar que en estado `completada` aparece exclusivamente el botón «Reabrir ↺».
5. Pulsar «Reabrir ↺»:
   - La interfaz actualiza de forma inmediata y optimista el estado a `pendiente` con su insignia correspondiente.
   - En caso de fallo de red/servidor, la interfaz revierte al estado previo y muestra alerta de error.
6. Verificar que la tarea reabierta permite reanudar su avance normal («Iniciar ▶»).

### Escenario C: Recuperación Segura de Contraseña (HU-14)
1. Cerrar sesión (`/logout`) y navegar a `http://localhost:5000/login`.
2. Hacer clic en el enlace «¿Olvidó su contraseña?» (`http://localhost:5000/forgot-password`).
3. Probar con un correo no registrado (ej. `inexistente@correo.com`) y enviar:
   - Se muestra el mensaje neutro:
     *"Si la dirección de correo electrónico está registrada en el sistema, se ha enviado un enlace para restablecer la contraseña."*
   - La terminal del servidor NO imprime ningún enlace.
4. Ingresar el correo registrado (`demo@taskcontrol.com`) y enviar:
   - Se muestra exactamente el mismo mensaje neutro de confirmación.
   - En la terminal del servidor (con `ENABLE_CONSOLE_PASSWORD_RESET=true`) se imprime:
     ```text
     =======================================================
     [DESARROLLO LOCAL - RECUPERACIÓN DE CONTRASEÑA]
     Para: demo@taskcontrol.com
     Enlace de restablecimiento (válido por 30 minutos):
     http://localhost:5000/reset-password/<token>
     =======================================================
     ```
   - Ni el token ni su hash aparecen en la respuesta HTTP visible.
5. Copiar el enlace de la terminal y abrirlo en el navegador.
6. Ingresar una nueva contraseña (mínimo 8 caracteres, ej. `nuevaClave2026`) y su confirmación.
7. Al enviar, redirige a `/login` con confirmación de éxito. Iniciar sesión con la nueva clave.
8. Intentar reutilizar el enlace del token ya consumido: el sistema rechaza el acceso y redirige a `/login` con alerta de error.

