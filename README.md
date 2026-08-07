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
  - [Capturas de Pantalla](#capturas-de-pantalla)
  - [Estructura del Repositorio](#estructura-del-repositorio)
  - [Controladores Internos](#controladores-internos)
  - [Consumo de API y Recursos](#consumo-de-api-y-recursos)
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

## Capturas de Pantalla

La interfaz sigue las [Material Design Rules](https://m3.material.io/foundations/overview/principles) y [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/) para el diseño de interfaces de usuario.

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
