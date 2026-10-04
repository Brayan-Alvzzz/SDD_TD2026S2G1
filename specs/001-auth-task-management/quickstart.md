# Quickstart & Validation Guide: Gestión Básica de Tareas y Autenticación

**Feature**: `001-auth-task-management`
**Date**: 2026-09-29
**Status**: Ready for Validation

Esta guía permite poner en marcha el entorno de desarrollo y validar de extremo a extremo que todas las funcionalidades del primer incremento de **TaskControl** operan correctamente de acuerdo a la especificación, los contratos de API y el modelo de datos.

---

## 1. Prerrequisitos

- **Python**: Versión 3.10 o superior (verificado con Python 3.14).
- **Entorno virtual**: Directorio `venv/` activado.
- **Git** (opcional para control de versiones).
- **Navegador web moderno** (Chrome, Firefox, Edge) con soporte de cookies y JavaScript ES6+.

---

## 2. Preparación del Entorno

### 2.1 Activar el Entorno Virtual

En PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```

### 2.2 Instalar Dependencias

Instalar los paquetes base del proyecto:
```powershell
pip install flask pytest pytest-cov
```

*(O `pip install -r requirements.txt` una vez generado el archivo de requerimientos en la fase de implementación)*.

### 2.3 Inicializar la Base de Datos

Ejecutar el script de inicialización del esquema SQLite según lo definido en [data-model.md](data-model.md):
```powershell
python -m src.infrastructure.database
```
*Resultado esperado*: Se crea el archivo `taskcontrol.db` en el directorio raíz o de instancia con las tablas `users`, `tasks` y `audit_logs` con claves foráneas habilitadas.

---

## 3. Ejecución de Pruebas Automatizadas (Test-First)

Para ejecutar la suite completa de pruebas unitarias y de integración:

```powershell
pytest -v
```

### Resultados Esperados:
- **Pruebas Unitarias de Dominio** (`tests/unit/`):
  - `test_user_service.py`: Validación de longitud de contraseña (>=8 caracteres), unicidad de correo y hashing con sal.
  - `test_state_machine.py`: Verificación de transiciones `pendiente` → `en_progreso` → `completada` y rechazo estricto de `completada` → `pendiente`.
  - `test_task_service.py`: Validación de longitud de título (1-150), descripción (max 1000) y generación inmutable de registros en `audit_logs`.
- **Pruebas de Integración Web** (`tests/integration/`):
  - `test_auth_routes.py`: Registro con sesión automática, inicio de sesión con cookie `HttpOnly`, rechazo con 401 ante credenciales erróneas y logout exitoso.
  - `test_task_routes.py`: Aislamiento entre usuarios (Usuario B no puede acceder a tareas de Usuario A), orden descendente por fecha de creación, y filtros por estado.

---

## 4. Validación Manual Paso a Paso (Flujo E2E)

### 4.1 Iniciar el Servidor de Desarrollo

```powershell
python -m src.web.app
```
*Salida esperada*: El servidor Flask inicia en `http://127.0.0.1:5000/`.

### 4.2 Escenarios de Verificación en Navegador

1. **Registro de Usuario (User Story 1)**:
   - Navegar a `http://127.0.0.1:5000/register`.
   - Probar contraseña corta (< 8 caracteres): Verificar que la interfaz y el backend impiden el registro.
   - Registrar `usuario1@test.com` con contraseña `password123`.
   - *Resultado esperado*: Cuenta creada e inicio de sesión automático redirigiendo al panel de tareas `/`.

2. **Visualización de Estado Vacío (Clarificación 3 / User Story 2)**:
   - Al ingresar al panel sin tareas: Verificar la presencia del mensaje ilustrado de bienvenida con el botón directo "Crear mi primera tarea".

3. **Creación de Tareas y Orden Cronológico (User Story 2)**:
   - Crear Tarea 1: Título: "Configurar entorno", Fecha límite: opcional.
   - Crear Tarea 2: Título: "Diseñar interfaz", Fecha límite: opcional.
   - *Resultado esperado*: Ambas tareas aparecen listadas; Tarea 2 (la más reciente) se ubica en la parte superior (`created_at DESC`).
   - Probar título vacío o > 150 caracteres: Verificar mensaje de validación claro.

4. **Transición de Estados y Auditoría (User Story 3)**:
   - En Tarea 1: Cambiar estado a `en_progreso`.
   - Cambiar estado a `completada`.
   - Intentar forzar el retroceso directo a `pendiente`: Verificar rechazo con aviso explicativo.
   - Inspeccionar la base de datos o endpoint de auditoría: Verificar los registros de auditoría correspondientes con `actor_id` y timestamp ISO 8601.

5. **Aislamiento Multi-Usuario (Seguridad y Privacidad)**:
   - Cerrar sesión desde la barra superior (`POST /logout`).
   - Registrar `usuario2@test.com`.
   - Acceder al panel: Verificar que la lista de tareas está completamente vacía (cero tareas del Usuario 1 son visibles).

6. **Interacción Dinámica y Rollback en Fallo (Principio II de la Constitución)**:
   - Desconectar temporalmente la red o simular fallo en endpoint PATCH:
   - *Resultado esperado*: La interfaz revierte inmediatamente el cambio visual y muestra una notificación de error al usuario.
