# rqtll-ide

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/assets/branding/logo-main-light.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/assets/branding/logo-main-dark.svg">
  <img alt="RQTLL Logo" src="https://github.com/RQTLL/rqtll-components/blob/main/assets/branding/logo-main-color.svg" width="50px">
</picture>

Entorno de Desarrollo Integrado (IDE) diseñado en PySide6 para ROS 2 (Robot Operating System). Facilita el desarrollo, compilación, visualización de grafos de nodos y control de robots .

## Table of Contents
- [rqtll-ide](#rqtll-ide)
  - [Table of Contents](#table-of-contents)
  - [Quickstart](#quickstart)
    - [Requisitos](#requisitos)
      - [Mínimos](#mínimos)
      - [Recomendados](#recomendados)
    - [Instalación](#instalación)
    - [Ejecución](#ejecución)
  - [Estructura del Repositorio](#estructura-del-repositorio)
  - [Controladores Internos](#controladores-internos)
  - [Consumo de API y Recursos](#consumo-de-api-y-recursos)
  - [Capturas de Pantalla](#capturas-de-pantalla)
    - [Asistente de instalación](#asistente-de-instalación)
    - [Pantalla de bienvenida](#pantalla-de-bienvenida)
    - [Espacios de trabajo](#espacios-de-trabajo)
  - [Cómo contribuir](#cómo-contribuir)
  - [Security](#security)
  - [License](#license)
  - [Maintainers](#maintainers)

## Quickstart

### Requisitos

#### Mínimos

- `Python 3.10`
- `PySide6`
- `protobuf`
- `grpcio` y `grpcio-tools`
- Ubuntu o derivada compatible con ROS 2.

#### Recomendados

- `Python 3.14+`
- `protobuf 6.4+`
- `grpcio 1.8+` y `grpcio-tools 1.8+`
- `PySide6 6.5+`
- Ubuntu 26.04 LTS o derivada compatible con ROS 2.

### Instalación

Clona el repositorio e instala los submódulos y librerías necesarias:
```bash
git clone --recursive https://github.com/RQTLL/rqtll-ide.git
cd rqtll-ide
git submodule update --init --recursive
pip install .
```

### Ejecución

Asegúrate de que el backend (`rqtll-service`) esté en ejecución y luego inicia la IDE:
```bash
python3 main.py
```

---

## Estructura del Repositorio

```text
./
├── external/                # Submódulos (rqtll-api, rqtll-components, rqtll-widgets)
├── intern/                  # Lógica y controladores de la IDE
│   ├── wizard/              # Controlador del asistente de instalación inicial
│   ├── clone_ws.py          # Lógica para clonación de repositorios
│   ├── code_editor.py       # Pestañas y gestión del editor
│   ├── compiler.py          # Invocador de compilación colcon y administrador de nodos
│   ├── editor_widget.py     # Instancia individual del editor y guardado
│   ├── gz_launcher.py       # Lanzador de simulación Gazebo
│   ├── home.py              # Controlador de la pantalla de bienvenida
│   ├── ide.py               # Enrutador principal y gestor de vistas
│   ├── new_ws.py            # Asistente de creación de espacios de trabajo
│   ├── nodes_visualizer.py  # Controlador del grafo de ROS 2 (cuerpo Blender-style)
│   ├── package_manager.py   # Gestor de paquetes apt
│   ├── rqt_launcher.py      # Lanzador de rqt
│   ├── rviz_launcher.py     # Lanzador de RViz2
│   ├── ssh.py               # Panel de conexión SSH remota y terminal
│   ├── syntax_highlighter.py# Resaltador de sintaxis multilingüe
│   └── twist_controller.py  # Teleoperación de robots con stream de cámara
├── main.py                  # Punto de entrada de la aplicación y captura global SVG
└── README.md
```

---

## Controladores Internos

La IDE divide su lógica en controladores modulares asíncronos alojados bajo `intern/`:

- **ide.py**: Administra el cambio de vistas principales mediante el panel lateral `nav`.
- **compiler.py**: Gestiona la llamada gRPC `BuildWorkspace` y procesa la salida de registro utilizando un buffer de throttling de **100ms** para evitar la degradación de rendimiento de la interfaz gráfica ante ráfagas masivas de logs.
- **nodes_visualizer.py**: Se suscribe de manera asíncrona a las métricas de tópicos y nodes del backend. Incluye un mecanismo de histéresis de **3 ciclos** para evitar parpadeos visuales en tópicos de actualización lenta y permite exportar la escena gráfica de manera vectorial pura (`NoCache`).
- **twist_controller.py**: Genera comandos `geometry_msgs/msg/Twist` para teleoperación por teclado e inicia un canal secundario dinámico para vídeo comprimido en ROS.
- **wizard**: Asistente de instalación de ROS 2, microROS y configuración.
---

## Consumo de API y Recursos

- **rqtll-api**: gRPC es el canal exclusivo para comunicarse con el sistema operativo y ROS 2. La IDE actúa como cliente gRPC y consume stubs asíncronos generados a partir de los archivos `.proto`.
- **rqtll-widgets**: Proporciona las plantillas de ventanas Qt Designer y las utilidades compartidas (como `base_window.py` y `graph.py`).
- **rqtll-components**: Aporta los archivos `.qss` de hojas de estilo (Light y Dark) y el catálogo de iconos vectoriales SVG. Los colores se cargan de forma dinámica basándose en la configuración de `palette.json`.

---

## Capturas de Pantalla

La interfaz sigue las [Material Design Rules](https://m3.material.io/foundations/overview/principles) y [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/) para el diseño de interfaces de usuario.


### Asistente de instalación

El asistente de instalación ayuda a configurar el entorno de desarrollo. Consta de 3 pasos:

1. **Configuración de repositorios**: Se encarga de habilitar los `software-properties-common` y `universe` repositories de Ubuntu y agregar los repositorios de ROS 2.
2. **Instalación de ROS 2**: Se encarga de instalar ROS 2 acorde a la versión de Ubuntu y la seleccionada por el usuario (por ejemplo, `ROS 2 Humble Core` o `ROS 2 Lyrical Desktop Full`).
3. **Configuración post-instalación**: Se encarga de configurar microROS acorde a la versión de Ubuntu; en caso de que se haya seleccionado, también se encarga de configurar la shell y el firewall de Ubuntu para cargar las herramientas de ROS 2 al abrir una terminal nueva y permitir la comunicación con múltiples máquinas.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-1D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A1-WIZARD-1L.webp">
  <img alt="Asistente de Instalación" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-1D.webp" width="49%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-3D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A1-WIZARD-3L.webp">
  <img alt="Instalación de ROS 2" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-3D.webp" width="49%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-4D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A1-WIZARD-4L.webp">
  <img alt="Instalación de ROS 2" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-4D.webp" width="49%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-5D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A1-WIZARD-5L.webp">
  <img alt="Post-instalación" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A1-WIZARD-5D.webp" width="49%" height="auto">
</picture>

### Pantalla de bienvenida

La pantalla de bienvenida permite crear, abrir y clonar espacios de trabajo, ademas de acceder al gestor de paquetes apt y la página de documentación de RQTLL.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-1D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A2-START-1L.webp">
  <img alt="Pantalla de bienvenida" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-1D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-3D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A2-START-3L.webp">
  <img alt="Crear espacio de trabajo" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-3D.webp" width="64%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-4D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A2-START-4L.webp">
  <img alt="Clonación de espacio de trabajo" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-4D.webp" width="35%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-2D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A2-START-2L.webp">
  <img alt="Gestor de paquetes" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A2-START-2D.webp" width="100%" height="auto">
</picture>

### Espacios de trabajo

Los espacios de trabajo usan el mismo template que incluye un sistema de navegación lateral izquierdo para navegar entre las diferentes vistas del workspace:

1. **Editor de texto y emulador de terminal**: Contiene un tree-view para navegar entre los archivos del workspace, el editor de código y el emulador de terminal para ejecutar comandos de ROS 2 y comandos de sistema.
2. **Panel de control**: Contiene un dashboard para compilar, grabar, ejecutar y detener lanzadores y nodos del workspace e interactuar con tópicos de ROS 2.
3. **Visualizador de nodos**: Visualiza los nodos y tópicos de ROS 2 en un grafo de nodos estilo Blender.
4. **SSH Manager**: Permite conectarse a máquinas remotas.
5. **Lanzadores**: Multiples ventanas para iniciar conexiones a RViz2, Gazebo Sim y rqt.
6. **Gestor de paquetes**: Permite instalar paquetes de apt.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-1D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-1L.webp">
  <img alt="Editor de codigo" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-1D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-2D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-2L.webp">
  <img alt="Panel de control" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-2D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-3D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-3L.webp">
  <img alt="Visualizador de nodos" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-3D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-4D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-4L.webp">
  <img alt="SSH Manager" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-4D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-5D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-5L.webp">
  <img alt=" Lanzador de RViz2" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-5D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-6D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-6L.webp">
  <img alt="Lanzador de Gazebo Sim" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-6D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-7D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-7L.webp">
  <img alt="Lanzador de rqt" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-7D.webp" width="100%" height="auto">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-WORKSPACE-8D.webp">
  <source media="(prefers-color-scheme: light)" srcset="https://github.com/RQTLL/rqtll-components/blob/main/releases/light/web/A3-WORKSPACE-8L.webp">
  <img alt="Gestor de paquetes apt" src= "https://github.com/RQTLL/rqtll-components/blob/main/releases/dark/web/A3-workspace-8D.webp" width="100%" height="auto">
</picture>

---

## Cómo contribuir

- Lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar un Pull Request.
- Para proponer cambios de diseño en las vistas, edita el archivo correspondiente en `intern/` y compruébalo ejecutando la IDE localmente.
- Los nuevos controladores deben colocarse en `intern/` y agregarse al enrutador en `ide.py`.

## Security

Consulta [SECURITY.md](SECURITY.md) para conocer el procedimiento de reporte de vulnerabilidades.

## License

Este proyecto está bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

## Maintainers

* **adnKSharp** <adnksharp@gmail.com>
