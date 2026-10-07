# TaskControl

Aplicación web para gestionar tareas personales y colaborar mediante asignaciones a otros usuarios. Fue desarrollada para la asignatura Tecnologías Disruptivas siguiendo un proceso de desarrollo guiado por especificaciones (Spec Driven Development) y pruebas.

El proyecto comprende cinco incrementos: gestión básica, ciclo de vida y recuperación de acceso, organización, colaboración y mejoras de interacción.

## Funcionalidades

- Registro, inicio y cierre de sesión.
- Creación, consulta y edición de tareas con título, descripción y fecha límite.
- Estados pendiente, en progreso y completada, con posibilidad de reabrir una tarea.
- Eliminación lógica de tareas, conservando su historial.
- Recuperación de contraseña mediante un enlace con token. En desarrollo, el enlace puede mostrarse en la consola.
- Prioridades, categorías e indicación de tareas vencidas.
- Asignación, reasignación y desasignación de tareas a usuarios registrados.
- Notificaciones internas y registro de auditoría.
- Vistas de tareas propias, asignadas y delegadas.
- Cambio de estado sin recargar la página.
- Ordenamiento manual mediante arrastrar y soltar, persistente al recargar.

## Incrementos

| Incremento | Alcance | Historias |
| --- | --- | --- |
| 1 | Gestión básica y autenticación | HU-01 a HU-04, HU-12 y HU-13 |
| 2 | Eliminación, reapertura y recuperación de contraseña | HU-05, HU-06 y HU-14 |
| 3 | Prioridades, categorías y tareas vencidas | HU-07 a HU-09 |
| 4 | Colaboración y notificaciones | HU-10 y HU-11 |
| 5 | Cambios de estado sin recarga y orden manual | HU-15 y HU-16 |

## Tecnologías y arquitectura

El backend utiliza Python y Flask. Los datos se almacenan en SQLite mediante SQLAlchemy; los cambios del esquema se gestionan con Flask-Migrate y Alembic. La interfaz utiliza plantillas Jinja2, HTML, CSS y JavaScript. Las pruebas se ejecutan con pytest y Playwright.

El código se organiza en `src/domain/` para las reglas de negocio, `src/infrastructure/` para la persistencia y `src/web/` para las rutas y la interfaz.

## Instalación local

Se requiere Git y Python 3.11 o superior.

### 1. Clonar el repositorio

```bash
git clone https://github.com/Brayan-Alvzzz/SDD_TD2026S2G1.git
cd SDD_TD2026S2G1
```

El repositorio es privado; para clonarlo se necesita acceso autorizado.

### 2. Crear y activar un entorno virtual

En Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En macOS o Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias y aplicar migraciones

```bash
python -m pip install -r requirements.txt
python -m flask --app src.web.app:create_app db upgrade
```

### 4. Iniciar la aplicación

```bash
python -m flask --app src.web.app:create_app run
```

Abre `http://127.0.0.1:5000`, registra una cuenta e inicia sesión. Para probar la colaboración, registra una segunda cuenta y utiliza otro navegador o perfil.

## Configuración

| Variable | Uso | Valor predeterminado |
| --- | --- | --- |
| `SECRET_KEY` | Firma de las sesiones de Flask | Clave de desarrollo |
| `DATABASE_PATH` | Ruta del archivo SQLite | `taskcontrol.db` |
| `ENABLE_CONSOLE_PASSWORD_RESET` | Muestra enlaces de recuperación en la consola | `false` |

Para probar localmente la recuperación de contraseña, define `ENABLE_CONSOLE_PASSWORD_RESET=true` antes de iniciar el servidor. En PowerShell:

```powershell
$env:ENABLE_CONSOLE_PASSWORD_RESET = "true"
```

El enlace aparecerá en la terminal del servidor después de solicitar el restablecimiento. Esto es únicamente una facilidad de prueba local, no un servicio real de envío de correo. No se deben publicar tokens ni claves privadas.

## Uso de colaboración y orden manual

El propietario conserva el control de su tarea aunque la asigne a otro usuario. La persona asignada puede verla y cambiar su estado; la edición, eliminación y reasignación corresponden al propietario. Estas reglas se validan en el backend.

Para ordenar tareas mediante arrastrar y soltar, selecciona la vista de tareas propias, el orden manual, todas las categorías y la pestaña de todos los estados. Después de mover una tarea, recarga la página para comprobar que el orden se conservó.

## Pruebas

Instala Chromium para las pruebas de navegador:

```bash
python -m playwright install chromium
```

Ejecuta la suite:

```bash
python -m pytest
```

La evidencia registrada al cierre del desarrollo, el 6 de octubre de 2026, muestra **264 pruebas aprobadas, 2 advertencias y código de salida 0**. Ese resultado se conserva en `docs/evidencias/inc5/green-ui-fixes.txt`; ejecutar la suite localmente permite comprobar la versión instalada.

## Estructura del proyecto

| Ruta | Contenido |
| --- | --- |
| `.specify/` | Constitución y recursos del proceso de especificación |
| `specs/` | Especificaciones, planes, contratos y tareas por incremento |
| `src/` | Código de la aplicación |
| `migrations/` | Migraciones de la base de datos |
| `tests/` | Pruebas automatizadas |
| `docs/bitacora.md` | Bitácora de desarrollo |
| `docs/evidencias/` | Resultados de pruebas por incremento |

## Autores

- [Brayan Felipe Álvarez Nieto](https://github.com/Brayan-Alvzzz): incrementos 1, 2 y 3.
- [Andrés Sebastián Quintana Morales](https://github.com/sebastianquintanam): incrementos 4 y 5.