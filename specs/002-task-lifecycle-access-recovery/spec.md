# Feature Specification: Cierre de Gestión de Tareas y Recuperación de Acceso

**Feature Branch**: `002-task-lifecycle-access-recovery`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Especifica el segundo incremento funcional de TaskControl: cierre de la gestión básica de tareas y recuperación de acceso. Este incremento cubre HU-05, HU-06 y HU-14 del backlog, y asume que el Incremento 1 (registro, login/logout, creación, listado, cambio de estado y edición de tareas) ya está implementado y en producción."

---

## Observaciones de Gobernanza y Alcance

> [!NOTE]
> **Alineación con la Constitución y Entorno del Proyecto**:
> 1. **Estado del Incremento 1**: El Incremento 1 funciona de forma verificada en el entorno local (39 pruebas automáticas aprobadas y base de datos local con datos de muestra). No está aún desplegado en producción.
> 2. **Mapeo de Principios Constitucionales**: El requerimiento original hace referencia a principios "VI", "VII" y "VIII". La [Constitución vigente de TaskControl](file:///.specify/memory/constitution.md) contiene formalmente los Principios I al V. Los mandatos se mapean exactamente con los principios vigentes así:
>    - *Soft delete y registro inmutable*: Cumple el **Principio IV** (*Trazabilidad, Auditoría e Inmutabilidad del Historial*).
>    - *Transiciones válidas y registradas*: Cumple el **Principio I** (*Máquinas de estado en el núcleo de dominio*) y **Principio IV** (*Auditoría inmutable*).
>    - *Seguridad de contraseñas y secretos*: Cumple la sección **Restricciones Técnicas y Estándares de Seguridad** (*Almacenamiento y gestión de credenciales con hashing seguro*).
> 3. **Arquitectura y Persistencia**: Esta especificación se mantiene **agnóstica a la tecnología de base de datos** (centrada en el QUÉ y el POR QUÉ para los usuarios). La transición desde `sqlite3` hacia `SQLAlchemy` con `Flask-Migrate/Alembic` preservando los datos existentes se abordará y planificará en la fase de arquitectura/plan técnico (`plan.md`).

---

## Clarifications

### Session 2026-10-04

- Q: ¿Cómo debe entregarse o exponerse el enlace de recuperación de contraseña durante el desarrollo y las pruebas locales en el navegador sin un servidor de correo real? (FR-010) → A: Mostrar el enlace con token en la terminal/consola únicamente durante desarrollo y pruebas locales, sin guardarlo en archivos ni logs persistentes (sin equiparar esta facilidad operativa a una entrega segura de producción); la respuesta servida en el navegador permanece estrictamente neutra tanto para correos registrados como inexistentes.
- Q: ¿Debe existir en la interfaz de usuario una vista o filtro de "Tareas Eliminadas" (papelera) para que el usuario consulte lo que ha descartado, o deben permanecer completamente invisibles en la interfaz durante este incremento? (FR-002) → A: Totalmente invisibles en la interfaz de usuario (se preservan exclusivamente en la base de datos y en el historial de auditoría, sin vista de papelera en este incremento).
- Q: ¿Hacia qué estado activo específico debe transicionar una tarea completada cuando el usuario ejecuta la acción de reapertura? (FR-006) → A: Transicionar automáticamente al estado "pendiente" (reinicio del ciclo de vida ordinario).
- Q: ¿Qué política de revocación debe aplicarse a los tokens de recuperación pendientes cuando un usuario solicita varias veces el restablecimiento de contraseña en un corto período de tiempo? (FR-015) → A: Invalidar inmediatamente cualquier token previo no consumido; solo el último enlace generado permanece activo.
- Q: ¿Cómo debe solicitarse la confirmación del usuario en la interfaz web antes de ejecutar la eliminación lógica de una tarea para prevenir borrados accidentales? (FR-001) → A: Diálogo de confirmación nativo del navegador (confirm) previo a enviar la petición de eliminación.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Eliminación Lógica de Tareas (HU-05) (Priority: P1)

Como usuario autenticado, quiero eliminar una tarea propia que ya no resulte relevante o haya sido creada por equivocación, para mantener mi listado de tareas despejado y enfocado en el trabajo vigente, asegurando al mismo tiempo que el historial y la auditoría no se pierdan.

**Why this priority**: Completa el ciclo básico de vida de las tareas permitiendo al usuario descartar elementos obsoletos, al tiempo que garantiza el cumplimiento estricto del Principio IV de gobernanza (prohibición de borrado físico destructivo).

**Independent Test**: Un usuario con múltiples tareas activas marca una de ellas para eliminar. La tarea desaparece inmediatamente de su listado principal, pero su registro histórico permanece intacto en los registros de auditoría y no puede ser modificada ni eliminada nuevamente.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado con una tarea activa en su listado, **When** hace clic en eliminar dicha tarea y acepta el diálogo nativo de confirmación del navegador (`confirm`), **Then** el sistema marca la tarea como eliminada lógicamente (soft delete), la excluye de la visualización predeterminada del listado y genera un evento de auditoría registrando la acción, el actor y la marca temporal.
2. **Given** un usuario autenticado consultando su listado de tareas activas, **When** se procesa la consulta de tareas, **Then** el sistema presenta únicamente tareas que no han sido marcadas como eliminadas.
3. **Given** una tarea que ya ha sido eliminada lógicamente, **When** se intenta ejecutar cualquier operación de modificación, transición de estado o una segunda eliminación sobre ella, **Then** el sistema rechaza la operación informando que la tarea no se encuentra activa o no existe.
4. **Given** un usuario intentando eliminar una tarea que pertenece a otro usuario, **When** envía la solicitud de eliminación, **Then** el sistema deniega la acción impidiendo cualquier alteración y respondiendo con error de acceso o recurso no encontrado.

---

### User Story 2 - Reapertura Explícita de Tareas Completadas (HU-06) (Priority: P1)

Como usuario autenticado, quiero reabrir una tarea que fue marcada como completada por error o cuyo trabajo deba retomarse, devolviéndola a un estado activo ("pendiente" o "en progreso"), para corregir el avance real del trabajo con plena trazabilidad histórica.

**Why this priority**: Resuelve la restricción estricta del Incremento 1 (donde las tareas completadas no permitían transiciones de retroceso directo) y proporciona flexibilidad operativa manteniendo la auditabilidad requerida por el negocio.

**Independent Test**: El usuario toma una tarea en estado "completada" y ejecuta la acción explícita de "Reabrir". La tarea regresa al estado activo seleccionado/configurado ("pendiente" o "en progreso") y en el historial de auditoría se comprueba que el evento quedó tipificado unívocamente como "reapertura" (reopen), diferenciándose de la creación original y de los cambios de avance ordinarios.

**Acceptance Scenarios**:

1. **Given** una tarea en estado "completada" perteneciente al usuario, **When** el usuario ejecuta la acción explícita de reapertura, **Then** el sistema transiciona la tarea a un estado activo (por defecto "pendiente"), actualiza su fecha de modificación y registra un evento de auditoría específico de reapertura con actor y marca temporal.
2. **Given** una tarea en estado "pendiente" o "en progreso", **When** se intenta invocar sobre ella la acción de reapertura, **Then** el sistema rechaza la operación informando que solo las tareas completadas pueden ser reabiertas.
3. **Given** una tarea que fue reabierta, **When** se consulta el historial de auditoría de dicha tarea, **Then** el historial exhibe claramente el evento de reapertura como un hito diferenciado de la creación y de las transiciones convencionales.
4. **Given** un usuario intentando reabrir una tarea completada perteneciente a otro usuario, **When** envía la solicitud, **Then** el sistema deniega el acceso y bloquea la transición.

---

### User Story 3 - Recuperación Segura de Contraseña (HU-14) (Priority: P2)

Como usuario que ha olvidado su contraseña, quiero solicitar el restablecimiento de mi clave de acceso proporcionando mi correo electrónico registrado, para recuperar el acceso a mi cuenta de forma autónoma sin comprometer la seguridad ni revelar a terceros qué correos están registrados en el sistema.

**Why this priority**: Evita la pérdida permanente de acceso a las cuentas de usuario y mitiga riesgos de seguridad informática como la enumeración de usuarios (user enumeration) y la reutilización indebida de credenciales temporales.

**Independent Test**: Se solicita la recuperación para un correo existente y para un correo ficticio; en ambos casos el sistema ofrece la misma respuesta neutra de confirmación. Con el token de un solo uso emitido para el correo real, el usuario establece una nueva contraseña válida (mínimo 8 caracteres) y consigue iniciar sesión. Un intento posterior de reutilizar el mismo token o utilizarlo después de su expiración resulta denegado.

**Acceptance Scenarios**:

1. **Given** un usuario en la pantalla de solicitud de recuperación de contraseña, **When** ingresa una dirección de correo (independientemente de si está registrada o no en el sistema) y envía el formulario, **Then** el sistema muestra un mensaje uniforme y neutro ("Si el correo electrónico está registrado en el sistema, se ha enviado un enlace para restablecer la contraseña"), impidiendo determinar si la cuenta existe.
2. **Given** un correo efectivamente registrado en el sistema, **When** se procesa la solicitud de recuperación, **Then** el sistema genera un token de restablecimiento criptográficamente seguro, con un tiempo de caducidad limitado (ej. 30 minutos) y de un único uso, sin exponer dicho secreto en registros planos.
3. **Given** un usuario que accede al enlace de restablecimiento con un token válido y no expirado, **When** introduce una nueva contraseña válida (mínimo 8 caracteres) y la confirma, **Then** el sistema actualiza la credencial aplicando hash criptográfico seguro, invalida el token de forma permanente y confirma el cambio de contraseña para permitir el inicio de sesión.
4. **Given** un usuario que intenta utilizar un token de restablecimiento que ya fue consumido anteriormente, **When** intenta cargar el formulario o enviar la nueva contraseña, **Then** el sistema rechaza la petición informando que el enlace ya no es válido.
5. **Given** un usuario que intenta utilizar un token de restablecimiento cuya vigencia temporal ya expiró, **When** intenta acceder o enviar el cambio, **Then** el sistema rechaza la petición informando que el enlace ha caducado y debe solicitarse uno nuevo.
6. **Given** un usuario en el formulario de nueva contraseña, **When** intenta ingresar una contraseña que no cumple con el mínimo de 8 caracteres o que no coincide con su confirmación, **Then** el sistema rechaza la actualización con un mensaje de validación descriptivo y mantiene el token disponible hasta su expiración o uso correcto.

---

### Edge Cases

- **Eliminación concurrente o múltiple**: Si un usuario envía múltiples solicitudes consecutivas para eliminar la misma tarea, la primera la elimina lógicamente y las subsecuentes devuelven un error informativo de que la tarea ya se encuentra eliminada o no existe.
- **Acceso a tareas eliminadas vía URL directa**: Si un usuario intenta acceder a la pantalla de edición o invocar el endpoint de una tarea que ya fue eliminada lógicamente, el sistema responde con error 404 (No Encontrado) o 400 (Recurso no disponible), evitando exponer o permitir modificar tareas archivadas.
- **Reapertura de tareas eliminadas**: No se permite reabrir una tarea que haya sido eliminada lógicamente; para poder interactuar con ella tendría que existir un flujo de restauración (fuera de alcance en este incremento).
- **Múltiples solicitudes de recuperación para un mismo correo**: Si un usuario solicita recuperación de contraseña varias veces en poco tiempo, el sistema debe invalidar los tokens anteriores generados para ese usuario y mantener únicamente activo el más reciente, evitando confusión o acumulación de accesos abiertos.
- **Inyección o manipulación de tokens de recuperación**: Cualquier token alterado, mal formado o con longitud/firma incorrecta debe ser rechazado inmediatamente con error genérico sin generar fallos internos ni exponer trazas del sistema.
- **Formato de correo no válido en recuperación**: Si se ingresa una cadena con formato inválido de correo (ej. sin `@`), el sistema valida sintácticamente la entrada y avisa al usuario antes de procesar el flujo.
- **Sesión activa durante restablecimiento**: Si un usuario con sesión abierta restablece su contraseña desde otro navegador mediante el token, el sistema debe garantizar la coherencia de credenciales en el siguiente inicio de sesión.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Eliminación Lógica de Tareas (HU-05)
- **FR-001**: El sistema DEBE permitir al usuario autenticado marcar una de sus tareas activas como eliminada lógicamente (soft delete), solicitando confirmación explícita mediante un diálogo nativo del navegador (`confirm`) antes de procesar la solicitud e impidiendo cualquier borrado físico destructivo de la base de datos.
- **FR-002**: Las tareas con marca de eliminación lógica DEBEN ser completamente invisibles en la interfaz de usuario y excluirse de todos los listados y filtros activos; no se proporcionará ninguna vista o filtro de "papelera" en este incremento.
- **FR-003**: El sistema DEBE rechazar cualquier intento de modificar, transicionar de estado o volver a eliminar una tarea previamente eliminada.
- **FR-004**: El sistema DEBE generar un registro inmutable en el log de auditoría cada vez que una tarea sea eliminada lógicamente, detallando el identificador de la tarea, el actor responsable, la acción (`delete` / `soft_delete`) y la marca temporal ISO 8601.
- **FR-005**: El sistema DEBE asegurar que un usuario solo pueda eliminar lógicamente tareas de su propiedad, respondiendo con denegación de acceso o recurso no encontrado ante tareas ajenas.

#### Reapertura de Tareas Completadas (HU-06)
- **FR-006**: El sistema DEBE proveer una acción explícita para reabrir tareas que se encuentren en estado "completada", transicionándolas de forma determinista y automática al estado "pendiente" para reiniciar su ciclo regular de avance.
- **FR-007**: El sistema DEBE restringir la acción de reapertura exclusivamente a tareas en estado "completada", bloqueando intentos de reapertura sobre tareas que ya estén pendientes, en progreso o eliminadas.
- **FR-008**: La acción de reapertura DEBE registrarse en el log de auditoría bajo un tipo de evento diferenciado (`reopen`), permitiendo distinguir inequívocamente en el historial que la tarea fue reabierta y no creada nuevamente o modificada por un avance regular.
- **FR-009**: Solo el usuario propietario de la tarea completada DEBE estar autorizado para ejecutar la reapertura de la misma.

#### Recuperación de Contraseña y Acceso (HU-14)
- **FR-010**: El sistema DEBE proporcionar una interfaz pública para solicitar la recuperación de contraseña a través del correo electrónico; en entornos de desarrollo y prueba locales sin pasarela SMTP, el enlace con token puede mostrarse en la terminal únicamente durante dichas sesiones de desarrollo/prueba sin guardarse en archivos ni en logs persistentes, sin describirse como equivalente a una entrega segura en producción. La respuesta del navegador DEBE permanecer neutra tanto para correos existentes como inexistentes.
- **FR-011**: La respuesta del sistema ante la solicitud de recuperación DEBE ser idéntica y neutra tanto para correos registrados como para correos inexistentes, previniendo la enumeración y descubrimiento de usuarios registrados.
- **FR-012**: Para correos registrados válidos, el sistema DEBE generar un identificador de recuperación (token) unívoco, de entropía criptográficamente segura, con caducidad temporal estricta (máximo 30 minutos).
- **FR-013**: Los secretos o tokens de restablecimiento NO DEBEN persistirse en texto plano; su verificación en el servidor debe seguir mecanismos seguros de comparación y protección contra ataques de temporización.
- **FR-014**: El sistema DEBE invalidar de manera inmediata y permanente un token de recuperación una vez haya sido utilizado para cambiar exitosamente la contraseña, impidiendo cualquier reuso posterior.
- **FR-015**: El sistema DEBE revocar e invalidar de forma automática todos los tokens previos no utilizados pertenecientes a un usuario cuando este genere una nueva solicitud de recuperación, garantizando que solo el último token emitido permanezca vigente y rechazando el uso de cualquier token anterior o expirado.
- **FR-016**: El formulario de restablecimiento DEBE exigir y validar que la nueva contraseña cumpla con una longitud mínima de 8 caracteres y almacenar la nueva credencial utilizando funciones de hash criptográfico seguro con sal (conforme a los estándares de seguridad de la Constitución).

---

### Key Entities

- **Tarea (Task)**: Entidad de trabajo existente, enriquecida con el atributo de estado de eliminación lógica (marca booleana `is_deleted` o fecha de eliminación `deleted_at`).
  - *Relaciones*: Pertenece a un `Usuario`. Vinculada a múltiples `Eventos de Auditoría`.
- **Evento de Auditoría (AuditLog)**: Registro inmutable de trazabilidad.
  - *Atributos clave*: Identificador, identificador de tarea, actor, tipo de acción (`create`, `update`, `status_change`, `delete`, `reopen`), detalle del evento y fecha/hora ISO 8601.
- **Solicitud / Token de Restablecimiento de Contraseña (PasswordResetToken)**: Representa la autorización temporal para cambio de credencial.
  - *Atributos clave*: Identificador único, referencia al usuario propietario, valor seguro o hash del token, fecha de creación, fecha de expiración y estado de consumo/revocación (`used`, `expires_at`).
- **Usuario (User)**: Cuenta de acceso del sistema, vinculada a las credenciales y a las solicitudes de recuperación.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las tareas eliminadas mediante la opción de borrado permanecen almacenadas en el sistema para fines de auditoría pero dejan de ser visibles en el listado regular de tareas del usuario.
- **SC-002**: El 100% de los intentos de eliminar o reabrir tareas pertenecientes a otros usuarios son bloqueados con respuesta semántica de no autorización o no existencia.
- **SC-003**: En el 100% de las reaperturas de tareas completadas, el registro de auditoría almacena la acción específica de reapertura (`reopen`), permitiendo a las consultas de auditoría distinguir eventos de reapertura de los cambios de estado ordinarios (`status_change`).
- **SC-004**: Ante una solicitud de recuperación de contraseña, el sistema devuelve exactamente el mismo mensaje en la interfaz y el mismo código de estado HTTP tanto si el correo existe como si no existe; asimismo, la suite de pruebas automatizadas verifica que el procesamiento aplique medidas para reducir variaciones significativas en el tiempo de respuesta entre ambos casos, sin afirmar una garantía matemática absoluta contra ataques avanzados de canal lateral.
- **SC-005**: El 100% de los tokens de restablecimiento quedan invalidados tras su primer uso exitoso o una vez transcurridos 30 minutos desde su emisión, impidiendo cualquier reactivación no autorizada.
- **SC-006**: Los usuarios pueden completar el flujo de eliminación o reapertura de una tarea en menos de 3 clics y recibir confirmación visual en menos de 1 segundo.

---

## Assumptions

- **Entrega de Enlaces de Recuperación en Desarrollo/Prueba**: Dado que el sistema se ejecuta en entorno local y no dispone de un servidor SMTP, el enlace de restablecimiento con su token puede mostrarse en la terminal únicamente durante desarrollo y pruebas locales para permitir al evaluador probar el flujo, sin guardarlo en archivos ni logs persistentes. Esto es una facilidad operativa de prueba y no debe describirse como equivalente a una entrega segura en producción. La respuesta del navegador se mantiene estrictamente neutra tanto para correos existentes como inexistentes.
- **Estado Inicial tras la Reapertura**: Al reabrir una tarea completada, su estado pasa determinísticamente a "pendiente" para permitir que vuelva a transicionar por el flujo ordinario hacia "en progreso" y "completada".
- **Límite de Vigencia de Tokens**: Se establece un valor estándar de 30 minutos de vida útil para el token de recuperación, considerado una práctica recomendada de la industria para equilibrar usabilidad y seguridad.
- **Exclusión de Funcionalidades No Priorizadas**: Quedan formal y explícitamente fuera de este incremento las historias HU-07 y HU-08 (prioridades y categorías), HU-09 (cálculo de vencimiento), HU-10 y HU-11 (asignación y notificaciones) y HU-15 y HU-16 (actualización asíncrona sin recarga y drag-and-drop), respetando la priorización del backlog.
- **Planificación de Infraestructura (SQLAlchemy / Alembic)**: La incorporación del ORM y el sistema de migraciones exigido por la cátedra no altera la lógica funcional descrita en esta especificación; será abordada en el plan de arquitectura e implementación (`plan.md` y `tasks.md`).
