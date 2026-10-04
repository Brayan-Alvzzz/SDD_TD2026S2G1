# Research & Architecture Decisions: Gestión Básica de Tareas y Autenticación

**Feature**: `001-auth-task-management`
**Date**: 2026-09-29
**Status**: Approved

## 1. Web Framework & Application Structure

- **Decision**: Python 3.10+ con **Flask** estructurado bajo el patrón de **Monolito Modular** con Application Factory (`create_app`).
- **Rationale**: 
  - Flask es liviano, no impone acoplamiento estricto de ORM o estructura de carpetas, lo que permite implementar el Principio I de la Constitución (núcleo de dominio desacoplado del framework).
  - La Application Factory facilita instanciar aplicaciones aisladas con configuraciones específicas para pruebas unitarias y de integración sin efectos secundarios globales.
- **Alternatives considered**:
  - *Django*: Descartado por violar el principio de Simplicidad/YAGNI para este primer incremento (sobrecarga de admin, ORM propietario fuertemente acoplado y migraciones complejas innecesarias).
  - *FastAPI*: Aunque moderno para APIs REST puras, añade complejidad asíncrona (`asyncio`) innecesaria para un monolito con renderizado Jinja2 y requiere librerías adicionales para plantillas y sesiones de servidor.

## 2. Persistencia y Almacenamiento

- **Decision**: **SQLite 3** mediante la biblioteca estándar de Python (`sqlite3`) utilizando el **Patrón Repositorio** y transacciones explícitas (`PRAGMA foreign_keys = ON;`).
- **Rationale**:
  - Cero fricción operativa: no requiere instalar ni administrar un motor de base de datos externo (PostgreSQL/MySQL), respetando el Principio V (Simplicidad y YAGNI).
  - SQLite en modo archivo es ideal para desarrollo y pruebas; además permite pruebas de integración ultrarrápidas en memoria (`:memory:`).
  - El desacoplamiento mediante interfaces de Repositorio en el dominio asegura que la migración futura a PostgreSQL requiera únicamente cambiar la implementación del repositorio, sin tocar la lógica de negocio.
- **Alternatives considered**:
  - *SQLAlchemy / Flask-SQLAlchemy*: Descartado para el primer incremento para evitar dependencias pesadas y magia de metaclasses/ActiveRecord que suelen acoplar el modelo de base de datos a las capas de negocio.
  - *PostgreSQL*: Descartado temporalmente; introduce dependencia de servidor externo innecesaria para el MVP.

## 3. Autenticación y Manejo de Sesiones

- **Decision**: Sesiones de servidor gestionadas mediante cookies seguras firmadas por Flask (`HttpOnly`, `SameSite='Lax'`, expiración de 24 horas por inactividad) y hashing de contraseñas mediante **`werkzeug.security`** (algoritmo `scrypt` / `pbkdf2:sha256` con sal criptográfica).
- **Rationale**:
  - `werkzeug.security` viene integrado con Flask, utiliza implementaciones criptográficas robustas y auditadas sin requerir dependencias de compiladores C externos en Windows.
  - Las cookies `HttpOnly` mitigan el robo de sesiones vía Cross-Site Scripting (XSS).
  - Cumple estrictamente con el requisito de seguridad constitucional y la clarificación de 24h de expiración por inactividad.
- **Alternatives considered**:
  - *JWT (JSON Web Tokens) en LocalStorage*: Descartado por alta vulnerabilidad a ataques XSS y complejidad añadida para invalidación de sesiones en cierre de sesión (logout).
  - *Flask-Login*: Descartado para mantener el código simple y pedagógico en este primer incremento, implementando un decorador delgado `@login_required` acoplado al servicio de autenticación.

## 4. Frontend e Interacción Dinámica

- **Decision**: Plantillas del lado del servidor con **Jinja2** combinadas con **JavaScript ES6 modular nativo (Vanilla JS)** para peticiones asíncronas (`fetch`) con actualización optimista y rollback visual ante error.
- **Rationale**:
  - Proporciona renderizado inicial inmediato (SSR) y excelente indexabilidad/rendimiento, cumpliendo el criterio de respuesta < 1s.
  - El uso de Vanilla JS evita la sobrecarga de herramientas de empaquetado (webpack/vite/npm), permitiendo que cualquier desarrollador clone y ejecute el proyecto sin configurar entornos Node.js.
  - Permite implementar fielmente el Principio II de la Constitución (contrato explícito de endpoints y reversión visual de cambios ante fallo).
- **Alternatives considered**:
  - *React / Vue SPA*: Descartado por sobreingeniería drástica para un primer incremento monolítico y por introducir un ecosistema dual (Node + Python).
  - *HTMX*: Excelente opción conceptual, pero usar Vanilla JS explícito garantiza total control sobre el protocolo de rollback y manejo de errores exigido en las especificaciones.

## 5. Estrategia de Pruebas Automatizadas

- **Decision**: **pytest** como ejecutor de pruebas, complementado con el cliente de pruebas nativo de Flask (`app.test_client()`).
- **Rationale**:
  - Permite separar limpiamente pruebas unitarias de dominio (sin base de datos ni servidor web) de pruebas de integración HTTP (con base de datos SQLite en memoria).
  - Cumple con la exigencia estricta de Test-First (Principio III de la Constitución).
- **Alternatives considered**:
  - *unittest estándar*: Aunque viable, `pytest` ofrece aserciones más expresivas, manejo superior de fixtures para bases de datos limpias y ejecución más rápida.
