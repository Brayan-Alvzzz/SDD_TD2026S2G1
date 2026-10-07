# TaskControl

Aplicación web para gestionar tareas personales y colaborar mediante asignaciones a otros usuarios. Desarrollada para la asignatura **Tecnologías Disruptivas**, siguiendo **Spec Driven Development (SDD)** y ciclos de pruebas *RED → GREEN → REFACTOR*.

El proyecto comprende cinco incrementos: gestión básica, ciclo de vida y recuperación de acceso, organización, colaboración y ordenamiento manual.

## Funcionalidades

- Registro, inicio y cierre de sesión.
- Creación, consulta y edición de tareas con título, descripción y fecha límite.
- Estados **Pendiente**, **En progreso** y **Completada**, con posibilidad de reabrir una tarea.
- Eliminación lógica de tareas.
- Recuperación de contraseña mediante un enlace con token; en desarrollo, el enlace puede mostrarse en la consola.
- Prioridades, categorías y detección de tareas vencidas.
- Asignación, reasignación y desasignación por correo de un usuario registrado.
- Notificaciones internas de asignación y registro de auditoría.
- Vistas de tareas propias, asignadas y delegadas.
- Cambios de estado sin recargar la página.
- Ordenamiento manual mediante arrastrar y soltar, con persistencia al recargar.

## Incrementos

| Incremento | Alcance | Historias | Responsable |
| --- | --- | --- | --- |
| 1 | Gestión básica y autenticación | HU01–HU04, HU12–HU13 | Brayan |
| 2 | Eliminación, reapertura y recuperación de contraseña | HU05–HU06, HU14 | Brayan |
| 3 | Prioridades, categorías y tareas vencidas | HU07–HU09 | Brayan |
| 4 | Colaboración y notificaciones | HU10–HU11 | Sebastián |
| 5 | Cambios de estado sin recarga y orden manual | HU15–HU16 | Sebastián |

## Tecnologías y arquitectura

El sistema es una aplicación Flask con páginas renderizadas en el servidor. JavaScript utiliza Fetch para las operaciones que actualizan la interfaz sin recargarla.

| Componente | Tecnología |
| --- | --- |
| Backend | Python y Flask |
| Persistencia | SQLite, SQLAlchemy y Flask-SQLAlchemy |
| Migraciones | Flask-Migrate y Alembic |
| Interfaz | Jinja2, HTML, CSS y JavaScript |
| Pruebas | pytest, pytest-cov y Playwright |
| Seguridad | Flask-WTF (Protección CSRF) |

Se utiliza Flask-WTF para proveer protección CSRF global, exigiendo tokens válidos en todos los formularios y peticiones de modificación (AJAX) para prevenir ataques de falsificación.

El código se organiza en tres capas: **dominio**, para reglas y servicios; **infraestructura**, para persistencia; y **web**, para rutas e interfaz.

## Instalación local

Se necesita Git y Python 3.11 o superior. Ejecuta los comandos desde la raíz del proyecto y con el entorno virtual activado.

### 1. Clonar el repositorio

```bash
git clone https://github.com/Brayan-Alvzzz/SDD_TD2026S2G1.git
cd SDD_TD2026S2G1
```


También puedes clonar la copia de [Sebastián](https://github.com/sebastianquintanam/SDD_TD2026S2G1). Si el repositorio es privado, necesitas acceso autorizado.

### 2. Crear y activar el entorno virtual

*macOS o Linux:*

```bash
python3 -m venv .venv
source .venv/bin/activate
```


*Windows — PowerShell:*

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```


### 3. Instalar dependencias y aplicar las migraciones

```bash
python -m pip install -r requirements.txt
python -m flask --app src.web.app:create_app `db upgrade`
```


Las migraciones existentes crean o actualizan el esquema de la base de datos. Para instalar el proyecto basta con ejecutar `db upgrade`.

### 4. Iniciar la aplicación

```bash
python -m flask --app src.web.app:create_app run
```


Abre *http://127.0.0.1:5000*, registra una cuenta e inicia sesión. Para probar la colaboración, registra una segunda cuenta con otro correo y utiliza un navegador o perfil separado.

## Configuración

La aplicación lee estas variables de entorno:

| Variable | Uso | Valor predeterminado |
| --- | --- | --- |
| `SECRET_KEY` | Firma de las sesiones de Flask y tokens CSRF | Clave de desarrollo |
| `DATABASE_PATH` | Ruta del archivo SQLite | `taskcontrol.db` |
| `ENABLE_CONSOLE_PASSWORD_RESET` | Mostrar enlaces de recuperación en la consola | `false` |

Para una instalación compartida, configura una `SECRET_KEY` propia. Las variables deben estar definidas antes de iniciar Flask.

### Recuperación de contraseña en desarrollo

Activa el mecanismo de consola antes de iniciar el servidor:

*macOS o Linux:*

```bash
export ENABLE_CONSOLE_PASSWORD_RESET=true
```


*Windows — PowerShell:*

```powershell
$env:ENABLE_CONSOLE_PASSWORD_RESET = "true"
```


Después de solicitar la recuperación desde la aplicación, consulta el enlace en la terminal del servidor. Este mecanismo sirve para pruebas locales; no constituye un servicio de envío de correo. Las notificaciones de asignación se consultan dentro de TaskControl.

## Uso y permisos

Una tarea conserva siempre a su propietario, aunque se asigne a otra persona.

| Operación | Propietario | Usuario asignado |
| --- | --- | --- |
| Consultar la tarea | Sí | Sí |
| Cambiar el estado o reabrir | Sí | Sí |
| Editar o eliminar | Sí | No |
| Asignar, reasignar o desasignar | Sí | No |
| Ordenar dentro de sus tareas propias | Sí | No |

Para asignar, introduce el correo de otro usuario registrado. Repetir la misma asignación no duplica la auditoría ni la notificación. Asignar o reasignar notifica al nuevo destinatario; desasignar no genera notificación.

Las reglas de acceso se validan en el backend. Un usuario ajeno no obtiene acceso a la tarea.

### Ordenar mediante arrastrar y soltar

Selecciona la vista **Propias**, el orden **Manual**, todas las categorías y la pestaña de estados **Todas**. Arrastra una tarea a otra posición y recarga para comprobar la persistencia.

El arrastre se habilita cuando se muestra la lista completa de tareas propias. Las tareas propias delegadas siguen formando parte de esa lista; las recibidas de otros propietarios no se pueden ordenar allí.

### Cambiar el estado

La secuencia es **Pendiente** → **En progreso** → **Completada**. Al reabrir una tarea completada, vuelve a **Pendiente**. El texto del botón indica la siguiente acción disponible: iniciar, completar o reabrir.

## Pruebas

Para preparar las pruebas de navegador, instala el complemento y Chromium dentro del entorno virtual:

```bash
python -m pip install pytest-playwright
python -m playwright install chromium
```


Ejecuta la suite completa:

```bash
python -m pytest
```


En Linux, Playwright puede requerir dependencias adicionales del sistema; consulta su [documentación de instalación](https://playwright.dev/python/docs/intro).

Las pruebas cubren servicios, rutas HTTP, permisos, persistencia, rollback e interacción en navegador. Las salidas de verificación se conservan en `docs/evidencias/`.

El último resultado de la suite comunicado durante la revisión del **7 de octubre de 2026**, fue **272 pruebas aprobadas, 2 advertencias, en 55.45 segundos y código de salida 0**. Es un resultado registrado de esa revisión, ver [regresion-final-inc5.txt](docs/evidencias/inc5/regresion-final-inc5.txt); la ejecución local permite verificar la versión instalada.

## Estructura del proyecto

| Ruta | Contenido |
| --- | --- |
| `.specify/` | Constitución y recursos del proceso SDD |
| `specs/` | Especificaciones, planes, contratos, modelos de datos y tareas por incremento |
| `src/domain/` | Reglas de negocio y servicios |
| `src/infrastructure/` | Modelos de persistencia, repositorios y base de datos |
| `src/web/` | Aplicación Flask, rutas, plantillas y archivos estáticos |
| `migrations/` | Historial de migraciones de la base de datos |
| `tests/` | Pruebas automatizadas |
| `docs/bitacora.md` | Bitácora del desarrollo |
| `docs/evidencias/` | Evidencias de pruebas por incremento |

## Spec Driven Development

Las especificaciones de cada incremento documentan el comportamiento esperado antes de implementar. Los contratos definen las interfaces; el plan y el modelo de datos guían la solución; `tasks.md` permite seguir el avance.

El ciclo de desarrollo utiliza pruebas RED para identificar comportamiento pendiente, implementación GREEN para satisfacerlas y revisión posterior para mejorar el código conservando el comportamiento. La bitácora y las evidencias documentan las ejecuciones y decisiones del proyecto.

## Autores

- *Brayan — [@Brayan-Alvzzz](https://github.com/Brayan-Alvzzz):* incrementos 1, 2 y 3.
- *Sebastián Quintana Morales — [@sebastianquintanam](https://github.com/sebastianquintanam):* incrementos 4 y 5.

Repositorio original: [Brayan-Alvzzz/SDD_TD2026S2G1](https://github.com/Brayan-Alvzzz/SDD_TD2026S2G1).

Copia en la cuenta de Sebastián: [sebastianquintanam/SDD_TD2026S2G1](https://github.com/sebastianquintanam/SDD_TD2026S2G1).
