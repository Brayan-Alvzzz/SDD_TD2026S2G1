# Implementation Plan: Gestión Básica de Tareas y Autenticación

**Branch**: `001-auth-task-management` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-auth-task-management/spec.md`

## Summary

Implementación del núcleo fundacional de **TaskControl** correspondiente al primer incremento del backlog (historias *Must*: HU-01 a HU-04 y HU-12, HU-13). La solución adopta una arquitectura de **Monolito Modular en Python con Flask**, desacoplando el núcleo de dominio de la infraestructura web. Abarca autenticación de usuarios (registro con contraseña >= 8 caracteres y login con cookies de sesión seguras HttpOnly con 24h de expiración por inactividad), gestión de tareas con validación estricta en el servidor, control determinista de transiciones de estado (`pendiente` → `en_progreso` → `completada`), ordenación cronológica descendente por fecha de creación, manejo guiado de estados vacíos y trazabilidad inmutable en log de auditoría para cada mutación.

## Technical Context

**Language/Version**: Python 3.14 (compatible con Python 3.10+)

**Primary Dependencies**: Flask 3.x, Werkzeug (hashing criptográfico `scrypt` / `pbkdf2:sha256`), Jinja2

**Storage**: SQLite 3 (biblioteca estándar `sqlite3`, claves foráneas habilitadas `PRAGMA foreign_keys = ON;`, patrón Repositorio)

**Testing**: `pytest` y cliente de pruebas de Flask (`app.test_client()`)

**Target Platform**: Multiplataforma (Windows 10/11, Linux, macOS)

**Project Type**: Monolito Web (Flask + Jinja2 + Vanilla JavaScript ES6 modular)

**Performance Goals**: Tiempo de respuesta en vistas web < 1s (según SC-006); ejecución de lógica de dominio en < 50ms

**Constraints**:
- Cumplimiento estricto de la Constitución de TaskControl (v1.0.0).
- Dominio puro sin importaciones de Flask.
- Autoridad exclusiva del backend para validación de títulos (1-150 caracteres), descripciones (max 1000 caracteres) y estados.
- Reversión visual optimista (rollback) en el cliente JavaScript ante cualquier error de red o API.
- Sesiones protegidas por cookies `HttpOnly`, `SameSite='Lax'` con caducidad tras 24 horas continuas de inactividad.

**Scale/Scope**: Primer incremento MVP; soporte para múltiples cuentas independientes con aislamiento total de tareas.

## Constitution Check

*GATE: Evaluado antes de la fase de diseño y re-verificado post-diseño.*

| Principio Constitucional | Estado | Justificación / Mecanismo de Cumplimiento |
|---|---|---|
| **I. Modularidad y Núcleo de Dominio Independiente** | **PASS** | El paquete `src/domain/` no contiene importaciones de Flask ni dependencias web. Las rutas en `src/web/` actúan exclusivamente como controladores delgados que delegan a `TaskService` y `UserService`. |
| **II. Autoridad Estricta del Backend y Contratos Explícitos** | **PASS** | Todas las validaciones de campos, unicidad de correo y máquinas de estados se validan en el servidor. Los contratos de API definidos en `contracts/` rigen la comunicación, y `tasks.js` implementa rollback ante fallos en peticiones dinámicas. |
| **III. Enfoque Test-First y Verificación Automatizada** | **PASS** | La suite se divide en pruebas unitarias puras de dominio (`tests/unit/`) y pruebas de integración de endpoints (`tests/integration/`) ejecutadas con `pytest` bajo disciplina Red-Green-Refactor. |
| **IV. Trazabilidad, Auditoría e Inmutabilidad del Historial** | **PASS** | La entidad y tabla `audit_logs` registra de manera inmutable `task_id`, `actor_id`, `action`, payload de diferencias en JSON y marca temporal ISO 8601 para toda creación, edición o cambio de estado. |
| **V. Simplicidad, YAGNI y Entrega Incremental** | **PASS** | Se utiliza SQLite estándar sin servidores externos, Vanilla JS sin dependencias de Node.js/bundlers, y se limita el alcance estrictamente a las historias *Must* del primer incremento. |

## Project Structure

### Documentation (this feature)

```text
specs/001-auth-task-management/
├── spec.md              # Especificación del requerimiento con clarificaciones
├── plan.md              # Este plan de implementación arquitectónico
├── research.md          # Fase 0: Decisiones técnicas y justificaciones de arquitectura
├── data-model.md        # Fase 1: Entidades, reglas de datos, máquina de estados y DDL
├── quickstart.md        # Fase 1: Guía de ejecución, pruebas y validación E2E
├── contracts/           # Fase 1: Contratos de interfaz y esquemas JSON
│   ├── auth-api.json    # Contrato para /register, /login, /logout
│   └── tasks-api.json   # Contrato para /api/tasks y sus transiciones de estado
└── checklists/
    └── requirements.md  # Lista de calidad y completitud de especificación
```

### Source Code (repository root)

```text
src/
├── domain/                      # Reglas de negocio puras (independiente de Flask)
│   ├── __init__.py
│   ├── models.py                # User, Task, AuditLog (Dataclasses)
│   ├── state_machine.py         # Validaciones de transiciones de ciclo de vida
│   ├── services.py              # UserService, TaskService
│   └── exceptions.py            # ValidationError, UnauthorizedError, ConflictError
├── infrastructure/              # Adaptadores de persistencia y seguridad
│   ├── __init__.py
│   ├── database.py              # Conexion SQLite, inicializacion DDL y transacciones
│   ├── repositories.py          # Repositorios SQLite para Users, Tasks, AuditLogs
│   └── security.py              # Utilidades de hashing con sal (Werkzeug) y sesion
└── web/                         # Controlador web y capa de transporte Flask
    ├── __init__.py
    ├── app.py                   # Application Factory (create_app)
    ├── auth_routes.py           # Vistas y endpoints de autenticacion
    ├── task_routes.py           # Vistas y endpoints REST de tareas
    ├── static/                  # Recursos estaticos
    │   ├── css/
    │   │   └── style.css        # Diseno responsivo limpio
    │   └── js/
    │       ├── api.js           # Cliente fetch con contratos y manejo de rollback
    │       └── tasks.js         # Interacciones en vivo de tareas y estados
    └── templates/               # Vistas HTML renderizadas con Jinja2
        ├── base.html            # Layout maestro con navbar y notificaciones
        ├── auth/
        │   ├── login.html       # Formulario de inicio de sesion
        │   └── register.html    # Formulario de registro con validacion de 8 caracteres
        └── tasks/
            ├── list.html        # Listado con filtros, orden descendente y estado vacio
            ├── create.html      # Formulario de creacion de tarea
            └── edit.html        # Formulario de edicion de tarea existente

tests/
├── conftest.py                  # Fixtures de pytest: app de prueba, cliente web, DB en memoria
├── unit/                        # Pruebas unitarias de dominio (sin infraestructura)
│   ├── test_state_machine.py    # Transiciones validas e invalidas de estado
│   ├── test_task_service.py     # Validacion de longitudes, orden y auditoria
│   └── test_user_service.py     # Politicas de contrasena y unicidad de correo
└── integration/                 # Pruebas de integracion HTTP y base de datos
    ├── test_auth_routes.py      # Ciclo de vida de autenticacion y sesiones
    ├── test_task_routes.py      # CRUD de tareas, aislamiento multiusuario y filtros
    └── test_repositories.py     # Integridad referencial y operaciones SQLite
```

**Structure Decision**: Monolito modular en Python estructurado en tres capas (`domain`, `infrastructure`, `web`), complementado con una suite de pruebas automatizadas en `tests/` (`unit` e `integration`). Cumple de forma idónea el Principio I y V de la Constitución.

## Complexity Tracking

> **Estado**: No se registraron violaciones a la Constitución. La arquitectura seleccionada respeta las alternativas más simples y directas disponibles (SQLite estándar, Vanilla JS, Flask modular).
