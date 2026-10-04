# Feature Specification: Gestión Básica de Tareas y Autenticación

**Feature Branch**: `001-auth-task-management`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Primer incremento: Gestión básica de tareas y autenticación (HU-01 a HU-04 + HU-12, HU-13) según el backlog de TaskControl"

## Clarifications

### Session 2026-09-29

- Q: ¿Cuál debe ser la política mínima de longitud y complejidad para las contraseñas en el registro de usuarios? (FR-001) → A: Longitud mínima de 8 caracteres, sin requisitos obligatorios de caracteres especiales ni combinaciones complejas.
- Q: ¿Cuál debe ser el límite máximo de caracteres permitido para el título y la descripción de una tarea? (FR-007) → A: Título obligatorio de hasta 150 caracteres y descripción opcional de hasta 1,000 caracteres.
- Q: ¿Cómo debe responder visualmente la vista principal cuando el usuario aún no tiene tareas creadas o cuando un filtro no arroja resultados? (FR-010) → A: Mostrar un mensaje descriptivo de estado vacío con botón directo para crear la primera tarea (o sugerencia de restablecer filtros si la búsqueda queda vacía).
- Q: ¿Cuál debe ser la política de duración y expiración para la sesión de usuario autenticado? (FR-004) → A: Sesión gestionada mediante cookies seguras (HttpOnly, SameSite) con expiración tras 24 horas de inactividad o al cierre de sesión explícito.
- Q: ¿Cuál debe ser el orden de visualización por defecto para el listado de tareas del usuario? (FR-007) → A: Orden cronológico descendente por fecha de creación (las tareas recién agregadas aparecen en la parte superior).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registro y Acceso Seguro de Usuarios (Priority: P1)

Como nuevo usuario del sistema, quiero registrar una cuenta con mi correo electrónico y contraseña (mínimo 8 caracteres), e iniciar sesión de forma segura, para disponer de un espacio personal privado donde gestionar mis tareas.

**Why this priority**: Es la base imprescindible de identidad y seguridad. Sin autenticación no es posible asociar tareas a usuarios específicos ni garantizar la privacidad de los datos personales.

**Independent Test**: Un usuario puede registrar una nueva cuenta con credenciales válidas, iniciar sesión, observar su espacio de trabajo inicial vacío y cerrar sesión exitosamente.

**Acceptance Scenarios**:

1. **Given** un visitante en la página de registro, **When** ingresa un correo electrónico válido no registrado y una contraseña de al menos 8 caracteres y envía el formulario, **Then** el sistema crea su cuenta de usuario y le permite iniciar sesión inmediatamente.
2. **Given** un visitante en la página de registro, **When** ingresa una contraseña con menos de 8 caracteres, **Then** el sistema rechaza el registro e informa que la contraseña debe contener al menos 8 caracteres.
3. **Given** un visitante en la página de registro, **When** ingresa un correo electrónico que ya existe en el sistema, **Then** el sistema rechaza el registro e informa que el correo ya se encuentra en uso.
4. **Given** un usuario registrado en la página de inicio de sesión, **When** introduce sus credenciales correctas, **Then** el sistema inicia su sesión de forma segura y lo redirige a su panel de tareas con una sesión válida por 24 horas de inactividad.
5. **Given** un usuario registrado en la página de inicio de sesión, **When** introduce una contraseña incorrecta o un correo inexistente, **Then** el sistema deniega el acceso con un mensaje de error claro sin revelar detalles sensibles.
6. **Given** un usuario autenticado con sesión activa, **When** selecciona la opción de cerrar sesión, **Then** la sesión finaliza y los accesos posteriores a rutas protegidas son denegados.

---

### User Story 2 - Creación y Visualización de Tareas (Priority: P1)

Como usuario autenticado, quiero crear nuevas tareas indicando obligatoriamente un título de hasta 150 caracteres (y opcionalmente descripción de hasta 1,000 caracteres y fecha límite) y visualizar el listado completo de mis tareas ordenadas cronológicamente (las más recientes primero), para tener visibilidad y control inmediato de mis pendientes.

**Why this priority**: Es la funcionalidad nuclear del sistema. Proporciona el valor primario de registrar y consultar las obligaciones pendientes del usuario.

**Independent Test**: Un usuario autenticado crea varias tareas con distintas combinaciones de campos y visualiza su listado personal actualizado, comprobando que las tareas creadas por otros usuarios permanecen inaccesibles.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado en la vista de tareas, **When** crea una tarea ingresando un título obligatorio (1-150 caracteres) y guarda los cambios, **Then** la tarea se guarda con estado inicial "pendiente", se registra en la auditoría con fecha/hora y actor, y aparece en la parte superior de su listado.
2. **Given** un usuario autenticado en el formulario de creación, **When** intenta guardar una tarea con el título vacío o compuesto únicamente por espacios en blanco, **Then** el sistema rechaza la creación e indica que el título es obligatorio.
3. **Given** un usuario autenticado en el formulario de creación, **When** intenta ingresar un título que excede 150 caracteres o una descripción que excede 1,000 caracteres, **Then** el sistema bloquea el guardado e informa los límites permitidos.
4. **Given** un usuario autenticado recién registrado que aún no ha creado tareas, **When** accede a su panel principal, **Then** visualiza un estado vacío descriptivo con un botón directo para registrar su primera tarea.
5. **Given** un usuario autenticado que ha creado múltiples tareas, **When** accede a su panel principal, **Then** visualiza sus tareas mostrando título, estado y fecha límite, presentadas en orden cronológico descendente de creación.
6. **Given** un usuario autenticado consultando su listado, **When** aplica un filtro por estado ("pendiente", "en progreso", "completada"), **Then** el listado se actualiza mostrando únicamente las tareas coincidentes, o un mensaje de estado vacío con opción de restablecer filtros si ninguna coincide.
7. **Given** dos usuarios registrados (Usuario A y Usuario B), **When** el Usuario A crea una tarea, **Then** el Usuario B no puede ver ni acceder a dicha tarea en ningún momento.

---

### User Story 3 - Transición y Control de Avance de Tareas (Priority: P2)

Como usuario autenticado, quiero actualizar el estado de mis tareas siguiendo el ciclo de avance real (de "pendiente" a "en progreso" y finalmente a "completada"), para mantener actualizada la progresión de mis proyectos y asegurar la trazabilidad histórica de los cambios.

**Why this priority**: Permite comunicar el avance real del trabajo y garantiza que no ocurran saltos de estado inconsistentes o no autorizados.

**Independent Test**: El usuario actualiza progresivamente el estado de una tarea y constata que cada cambio válido queda reflejado en la interfaz y en el registro histórico de auditoría, mientras que los cambios inconsistentes son bloqueados.

**Acceptance Scenarios**:

1. **Given** una tarea en estado "pendiente", **When** el usuario avanza su estado a "en progreso", **Then** el sistema actualiza el estado y genera un registro de auditoría con la acción, el actor y la marca temporal.
2. **Given** una tarea en estado "en progreso", **When** el usuario avanza su estado a "completada", **Then** el sistema actualiza el estado a completada y genera el correspondiente registro de auditoría.
3. **Given** una tarea en estado "completada", **When** el usuario intenta cambiarla directamente a "pendiente", **Then** el sistema bloquea la operación e indica que una tarea completada requiere un procedimiento explícito de reapertura.

---

### User Story 4 - Modificación y Corrección de Tareas (Priority: P2)

Como usuario autenticado, quiero editar los datos de una tarea existente (título de hasta 150 caracteres, descripción de hasta 1,000 caracteres o fecha límite), para rectificar datos erróneos o ajustar compromisos según evolucione el trabajo.

**Why this priority**: Es indispensable para corregir errores de captura y mantener la información actualizada a lo largo del tiempo.

**Independent Test**: El usuario modifica el título y la fecha límite de una tarea existente, comprobando que se aplican las mismas reglas de validación que al crearla y que los cambios quedan guardados y auditados.

**Acceptance Scenarios**:

1. **Given** una tarea existente perteneciente al usuario, **When** el usuario modifica su título, descripción o fecha límite con valores válidos dentro de los límites permitidos, **Then** el sistema actualiza la tarea y registra el evento de edición en la auditoría.
2. **Given** una tarea existente, **When** el usuario intenta guardar una edición dejando el título en blanco o excediendo los límites de longitud (150 caracteres para título, 1,000 para descripción), **Then** el sistema rechaza la actualización y mantiene los valores anteriores intactos.

---

### Edge Cases

- **Acceso no autenticado**: Si un usuario sin sesión activa intenta acceder a cualquier funcionalidad o pantalla de tareas, el sistema debe denegar el acceso y redirigirlo a la pantalla de inicio de sesión.
- **Acceso cruzado entre usuarios**: Si un usuario autenticado intenta consultar, editar o cambiar el estado de una tarea perteneciente a otro usuario, el sistema debe denegar la acción respondiendo con error de acceso no autorizado o recurso no encontrado.
- **Contraseñas menores a 8 caracteres**: Si se intenta registrar un usuario con una contraseña inferior al umbral mínimo de 8 caracteres, el sistema debe rechazar el registro inmediatamente antes de procesar el hash.
- **Límites de longitud excedidos**: Si un usuario intenta enviar un título de más de 150 caracteres o una descripción de más de 1,000 caracteres, el sistema debe rechazar la petición con un error de validación específico.
- **Sesión expirada por inactividad**: Tras 24 horas continuas sin peticiones activas, la cookie de sesión se considerará inválida y el sistema solicitará al usuario iniciar sesión nuevamente para continuar.
- **Títulos con espacios o caracteres especiales**: Títulos compuestos únicamente por caracteres invisibles o espacios en blanco deben ser rechazados. Títulos válidos con caracteres internacionales o símbolos deben almacenarse y renderizarse de forma segura sin alteraciones.
- **Fechas límite inválidas**: Intentos de enviar formatos de fecha inexistentes o mal construidos deben ser rechazados con mensajes claros de validación.
- **Fallas de comunicación en actualizaciones dinámicas**: Si una petición asíncrona de actualización falla por problemas de red o error del servidor, la interfaz debe cancelar cualquier cambio visual optimista (rollback) y mostrar un aviso de error sin dejar estados inconsistentes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE proporcionar una funcionalidad de registro para nuevos usuarios mediante correo electrónico válido y una contraseña con longitud mínima de 8 caracteres.
- **FR-002**: El sistema DEBE validar el formato del correo electrónico y verificar su unicidad global antes de admitir un nuevo registro.
- **FR-003**: El sistema DEBE almacenar las credenciales de los usuarios protegiendo la contraseña mediante algoritmos de hash criptográfico seguros con sal, prohibiendo en todo momento el almacenamiento en texto plano.
- **FR-004**: El sistema DEBE autenticar a los usuarios contra sus credenciales registradas y mantener una sesión segura basada en cookies HTTP con atributos `HttpOnly` y `SameSite`, con una vigencia de 24 horas de inactividad o hasta el cierre de sesión explícito.
- **FR-005**: El sistema DEBE proveer un mecanismo explícito de cierre de sesión que invalide la sesión activa tanto en el cliente como en el servidor.
- **FR-006**: El sistema DEBE exigir sesión autenticada activa para toda operación de consulta o manipulación sobre las tareas.
- **FR-007**: El sistema DEBE permitir la creación de tareas asignando de forma obligatoria un título no vacío de máximo 150 caracteres y, de forma opcional, una descripción textual de máximo 1,000 caracteres y una fecha límite.
- **FR-008**: Toda tarea DEBE inicializarse automáticamente con el estado "pendiente" al momento de ser creada.
- **FR-009**: El sistema DEBE restringir la visibilidad y consulta de tareas exclusivamente al usuario propietario que las haya creado, presentándolas por defecto en orden cronológico descendente según su fecha de creación.
- **FR-010**: El sistema DEBE permitir filtrar el listado de tareas según su estado ("pendiente", "en progreso", "completada") y desplegar un estado visual vacío asistido (con opción de reinicio de filtro o botón de creación) si la consulta no contiene elementos.
- **FR-011**: El sistema DEBE permitir modificar el título (hasta 150 caracteres), descripción (hasta 1,000 caracteres) y fecha límite de una tarea existente, aplicando las mismas reglas de validación exigidas durante la creación.
- **FR-012**: El sistema DEBE aplicar una máquina de estados determinista para el avance de tareas: transiciones válidas de "pendiente" a "en progreso" y de "en progreso" a "completada".
- **FR-013**: El sistema DEBE rechazar transiciones de estado no autorizadas, impidiendo el retroceso directo de "completada" a "pendiente" sin una acción explícita de reapertura.
- **FR-014**: El sistema DEBE registrar de forma inmutable en un log de auditoría el identificador del actor, la acción realizada y la marca temporal (timestamp ISO 8601) para cada evento de creación, edición y cambio de estado de tareas.
- **FR-015**: Toda respuesta ante errores de validación o autorización DEBE ser descriptiva, orientada al usuario y exenta de filtración de información sensible o trazas internas del sistema.

### Key Entities

- **Usuario**: Representa la cuenta individual registrada en el sistema. Atributos esenciales: identificador único, dirección de correo electrónico única, credencial segura (hash de contraseña con sal, mínimo 8 caracteres originales) y fecha de creación.
- **Tarea**: Representa una unidad de trabajo asignada a un usuario. Atributos esenciales: identificador único, identificador del usuario propietario, título (1 a 150 caracteres), descripción opcional (hasta 1,000 caracteres), fecha límite opcional, estado actual (valores permitidos: "pendiente", "en progreso", "completada"), fecha de creación y fecha de última modificación. Orden por defecto: fecha de creación descendente (`created_at DESC`).
- **Evento de Auditoría**: Representa el registro histórico inmutable de una acción sobre el ciclo de vida de una tarea. Atributos esenciales: identificador único, identificador de la tarea afectada, identificador del usuario actor, tipo de acción (creación, edición, transición de estado), detalle o resumen del cambio y marca temporal (timestamp ISO 8601).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un usuario nuevo puede completar el proceso de registro y encontrarse autenticado en la plataforma en menos de 60 segundos.
- **SC-002**: El 100% de las tareas creadas se asignan unívocamente al usuario creador y ninguna tarea es visible para otros usuarios del sistema.
- **SC-003**: El 100% de los intentos de creación o modificación con títulos vacíos o que excedan los 150 caracteres (o descripciones > 1,000 caracteres) son rechazados con mensajes de validación comprensibles.
- **SC-004**: El 100% de los eventos de creación, edición y cambio de estado generan un registro correspondiente en el log de auditoría con actor y marca temporal.
- **SC-005**: El 100% de las transiciones de estado no permitidas son bloqueadas de forma preventiva por el sistema.
- **SC-006**: Las operaciones de carga de listado, creación y cambio de estado se completan y reflejan visualmente para el usuario en menos de 1 segundo bajo condiciones operativas normales.

## Assumptions

- Los usuarios utilizan navegadores web modernos con soporte estándar para formularios, cookies y JavaScript (ES6+).
- La activación de la cuenta tras el registro es inmediata para este primer incremento (no se requiere confirmación por correo saliente externo).
- La eliminación de tareas (HU-05) y la reapertura de tareas completadas (HU-06) forman parte de historias subsecuentes ("Should") según el backlog.
- Las fechas límite se ingresan y almacenan con referencia temporal estándar universal para evitar ambigüedades de zona horaria.
- El almacenamiento de contraseñas cumple con estándares criptográficos robustos establecidos en la Constitución del proyecto.
