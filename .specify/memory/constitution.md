<!--
Sync Impact Report
- Version change: Uninitialized (template) → 1.0.0
- List of modified principles:
  - [PRINCIPLE_1_NAME] → I. Modularidad y Núcleo de Dominio Independiente (Modular Monolith)
  - [PRINCIPLE_2_NAME] → II. Autoridad Estricta del Backend y Contratos Explícitos
  - [PRINCIPLE_3_NAME] → III. Enfoque Test-First y Verificación Automatizada (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Trazabilidad, Auditoría e Inmutabilidad del Historial
  - [PRINCIPLE_5_NAME] → V. Simplicidad, YAGNI y Entrega Incremental
- Added sections:
  - Restricciones Técnicas y Estándares de Seguridad
  - Flujo de Trabajo y Puertas de Calidad (Quality Gates)
- Removed sections: None
- Follow-up TODOs: None
-->

# TaskControl Constitution

## Core Principles

### I. Modularidad y Núcleo de Dominio Independiente (Modular Monolith)
La lógica de negocio del dominio (gestión de tareas, máquinas de estados, transiciones de ciclo de vida y asignaciones) DEBE residir en módulos o servicios Python independientes, desacoplados del framework web y de la capa de presentación. Las vistas y rutas de Flask DEBEN actuar exclusivamente como controladores delgados (thin controllers), limitándose al enrutamiento HTTP, validación de esquemas de transporte, serialización y delegación hacia los servicios de dominio.
*Razón*: Permite probar, refactorizar y mantener las reglas de negocio de manera aislada sin acoplamiento a detalles de transporte HTTP o tecnologías de interfaz.

### II. Autoridad Estricta del Backend y Contratos Explícitos
El backend DEBE ser la única fuente de verdad para la validación de datos, los cálculos de estado (incluido el cálculo de tareas vencidas) y la autorización de sesiones. Ninguna validación o lógica ejecutada en JavaScript en el navegador sustituye la validación del servidor. Toda interacción dinámica entre frontend y backend DEBE regirse por contratos de interfaz y respuestas JSON estandarizadas con códigos de estado HTTP semánticos. Ante cualquier fallo en la comunicación asíncrona, el cliente JavaScript DEBE revertir cualquier cambio visual optimista (rollback) e informar el error de forma clara al usuario.
*Razón*: Garantiza la integridad de datos contra manipulaciones indebidas y evita discrepancias de lógica originadas por zonas horarias del navegador o estados inconsistentes de red.

### III. Enfoque Test-First y Verificación Automatizada (NON-NEGOTIABLE)
El desarrollo DEBE seguir una disciplina estricta de pruebas automatizadas (TDD / Test-First). Antes de implementar código en producción, DEBEN escribirse pruebas que reflejen los criterios de aceptación especificados y fallen en rojo. Se exige respetar el ciclo Red-Green-Refactor. Cada historia de usuario DEBE contar con pruebas unitarias para el dominio y pruebas de integración para los endpoints HTTP, cubriendo casos de éxito, validaciones de entrada, transiciones de estado inválidas y denegación de accesos no autorizados.
*Razón*: Previene regresiones, documenta contractualmente el comportamiento del software y asegura que cada incremento sea verificable de manera automatizada y continua.

### IV. Trazabilidad, Auditoría e Inmutabilidad del Historial
Todo cambio significativo en el ciclo de vida de las entidades (creación, modificación, transiciones de estado, reaperturas y asignaciones) DEBE registrarse de forma inmutable en un log de auditoría persistente, registrando identificador del actor y marca temporal (timestamp ISO 8601). Las eliminaciones de tareas o entidades críticas DEBEN ser lógicas (soft delete) en lugar de destrucciones físicas de registros, garantizando la preservación del historial histórico y la consistencia relacional.
*Razón*: Asegura la rendición de cuentas, la auditabilidad ante incidentes o disputas de estado y la trazabilidad completa del ciclo de vida del trabajo.

### V. Simplicidad, YAGNI y Entrega Incremental
Cada funcionalidad DEBE implementarse comenzando con la solución técnica más simple que satisfaga los criterios de aceptación (priorización MoSCoW: foco inicial en historias *Must* antes de introducir colaboración o interacciones complejas). Se DEBE aplicar rigurosamente el principio YAGNI (You Aren't Gonna Need It): queda prohibido incorporar abstracciones prematuras, dependencias externas innecesarias o componentes arquitectónicos no requeridos. Cualquier complejidad agregada DEBE ser explícitamente justificada.
*Razón*: Minimiza la deuda técnica, optimiza los tiempos de entrega y asegura que la arquitectura evolucione respondiendo a requerimientos reales comprobados.

## Restricciones Técnicas y Estándares de Seguridad

- **Pila Tecnológica**:
  - Backend: Python 3.10+ utilizando el microframework Flask.
  - Frontend: Plantillas Jinja2 combinadas con JavaScript nativo/modular (ES6+) para dinamismo e interacción asíncrona fluida sin dependencias de frameworks SPA pesados.
  - Persistencia: Base de datos relacional con esquemas estructurados, claves foráneas e integridad referencial garantizada.
- **Estándares de Seguridad**:
  - Almacenamiento de credenciales: Las contraseñas NUNCA deben persistirse en texto plano; DEBEN procesarse mediante funciones de hash criptográfico seguras con sal (salt) como Argon2 o bcrypt.
  - Protección de rutas y sesiones: Las operaciones protegidas DEBEN validar la sesión activa en el backend en cada petición, impidiendo accesos mediante manipulación directa de la interfaz.
  - Mitigación de vulnerabilidades: Todas las entradas DEBEN validarse y sanitizarse para prevenir ataques de inyección (SQLi), Cross-Site Scripting (XSS) y Cross-Site Request Forgery (CSRF).

## Flujo de Trabajo y Puertas de Calidad (Quality Gates)

- **Ciclo Spec-Driven Development (SDD)**:
  - Todo desarrollo funcional debe respetar las fases: Especificación (`speckit-specify`) → Plan de Implementación (`speckit-plan`) → Desglose de Tareas (`speckit-tasks`) → Implementación (`speckit-implement`).
  - No se permite iniciar codificación sin una especificación clara, planes revisados y tareas ordenadas por dependencias.
- **Puertas de Calidad Obligatorias**:
  1. Cobertura completa de pruebas para los criterios de aceptación de la historia o funcionalidad abordada.
  2. Ejecución 100% limpia de la suite de pruebas sin fallos ni omisiones.
  3. Adherencia al estándar PEP 8 en Python y reglas de estilo limpias en JavaScript.
  4. Revisión y aprobación explícita de cambios que involucren contratos de datos o lógica de estados de dominio.

## Governance

- **Supremacía Constitucional**: Esta Constitución es el documento de gobernanza supremo del proyecto TaskControl y prevalece sobre cualquier práctica informal, convención ad-hoc o decisión aislada.
- **Procedimiento de Enmiendas**: Cualquier modificación a los principios o normas de esta Constitución requiere una propuesta documentada que justifique la necesidad, evalúe el impacto arquitectónico, cuente con aprobación del equipo y defina un plan de migración si aplica.
- **Política de Versionado Semántico**:
  - `MAJOR`: Modificaciones que eliminen principios existentes, relajen restricciones fundamentales o redefinan la gobernanza de forma incompatible.
  - `MINOR`: Adición de nuevos principios, incorporación de nuevas secciones normativas o ampliación sustancial de directrices existentes.
  - `PATCH`: Correcciones de redacción, clarificaciones tipográficas o ajustes de formato sin impacto semántico.
- **Auditoría y Revisión**: Todo Pull Request, plan técnico o entrega de código debe validar explícitamente su conformidad con esta Constitución antes de integrarse.

**Version**: 1.0.0 | **Ratified**: 2026-09-24 | **Last Amended**: 2026-09-29
