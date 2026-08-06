import sys, os, subprocess

base_path = os.path.dirname(os.path.abspath(__file__))
proto_py_path = os.path.join(base_path, "external", "rqtll_api", "py")
if proto_py_path not in sys.path:
    sys.path.insert(0, proto_py_path)

import grpc
import packages_pb2
import packages_pb2_grpc
import installer_pb2
import installer_pb2_grpc
import workspace_pb2
import workspace_pb2_grpc
import interactive_execution_pb2
import interactive_execution_pb2_grpc
import data_stream_pb2
import data_stream_pb2_grpc
import build_pb2
import build_pb2_grpc
import introspection_pb2
import introspection_pb2_grpc
import execution_pb2
import execution_pb2_grpc
import file_system_pb2
import file_system_pb2_grpc
import terminal_pb2
import terminal_pb2_grpc
import system_utils_pb2
import system_utils_pb2_grpc

from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu,
                               QPushButton, QToolButton, QTreeWidgetItem,
                               QListWidgetItem, QTableWidgetItem, QLabel,
                               QFileDialog, QWidget, QGraphicsView)
from PySide6.QtGui import QFontDatabase, QIcon, QGuiApplication, QAction, QPixmap
from PySide6.QtCore import Qt, QObject, QEvent, QPoint, QRect

# Monkeypatching for dynamic icon reloading on theme change
original_add_file = QIcon.addFile
def custom_add_file(self, path, *args, **kwargs):
    self._rqtll_path = path
    return original_add_file(self, path, *args, **kwargs)
QIcon.addFile = custom_add_file

original_icon_pixmap = QIcon.pixmap
def custom_icon_pixmap(self, *args, **kwargs):
    pix = original_icon_pixmap(self, *args, **kwargs)
    if hasattr(self, "_rqtll_path"):
        pix._rqtll_path = self._rqtll_path
    return pix
QIcon.pixmap = custom_icon_pixmap

original_set_pixmap = QLabel.setPixmap
def custom_set_pixmap(self, pixmap):
    if hasattr(pixmap, "_rqtll_path"):
        self._rqtll_pixmap_path = pixmap._rqtll_path
        self._rqtll_pixmap_size = pixmap.size()
    return original_set_pixmap(self, pixmap)
QLabel.setPixmap = custom_set_pixmap

original_set_icon_btn = QPushButton.setIcon
def custom_set_icon_btn(self, icon):
    if hasattr(icon, "_rqtll_path"):
        self._rqtll_icon_path = icon._rqtll_path
    return original_set_icon_btn(self, icon)
QPushButton.setIcon = custom_set_icon_btn

original_set_icon_tool = QToolButton.setIcon
def custom_set_icon_tool(self, icon):
    if hasattr(icon, "_rqtll_path"):
        self._rqtll_icon_path = icon._rqtll_path
    return original_set_icon_tool(self, icon)
QToolButton.setIcon = custom_set_icon_tool

original_set_icon_twi = QTreeWidgetItem.setIcon
def custom_set_icon_twi(self, column, icon):
    if hasattr(icon, "_rqtll_path"):
        if not hasattr(self, "_rqtll_icon_paths"):
            self._rqtll_icon_paths = {}
        self._rqtll_icon_paths[column] = icon._rqtll_path
    return original_set_icon_twi(self, column, icon)
QTreeWidgetItem.setIcon = custom_set_icon_twi

original_set_icon_lwi = QListWidgetItem.setIcon
def custom_set_icon_lwi(self, icon):
    if hasattr(icon, "_rqtll_path"):
        self._rqtll_icon_path = icon._rqtll_path
    return original_set_icon_lwi(self, icon)
QListWidgetItem.setIcon = custom_set_icon_lwi

original_set_icon_tbi = QTableWidgetItem.setIcon
def custom_set_icon_tbi(self, icon):
    if hasattr(icon, "_rqtll_path"):
        self._rqtll_icon_path = icon._rqtll_path
    return original_set_icon_tbi(self, icon)
QTableWidgetItem.setIcon = custom_set_icon_tbi

original_set_icon_act = QAction.setIcon
def custom_set_icon_act(self, icon):
    if hasattr(icon, "_rqtll_path"):
        self._rqtll_icon_path = icon._rqtll_path
    return original_set_icon_act(self, icon)
QAction.setIcon = custom_set_icon_act

from intern.home import HomeController
from intern.package_manager import PackageManagerController
from intern.wizard import WizardController
try:
    from external.rqtll_widgets.utils.theme_manager import get_theme_manager
except Exception:
    try:
        from rqtll_widgets.utils.theme_manager import get_theme_manager
    except Exception:
        def get_theme_manager():
            return None

icon_dirs = [
    os.path.join(base_path, "external", "rqtll_components"),
    os.path.join(base_path, "external", "rqtll_components", "assets"),
    os.path.join(base_path, "external", "rqtll_components", "assets", "branding"),
    os.path.join(base_path, "external", "rqtll_components", "assets", "icons"),
    os.path.join(base_path, "external", "rqtll_components", "styles"),
    os.path.join(base_path, "external", "rqtll_components", "styles", "themes"),
    os.path.join(base_path, "external", "rqtll_widgets"),
]

def load_resources(app, components_path, theme="dark.qss"):
    fonts_path = os.path.join(components_path, "assets/fonts")
    for root, dirs, files in os.walk(fonts_path):
        for file in files:
            if file.endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(root, file))

    qss_file = os.path.join(components_path, f"styles/themes/{theme}")
    if os.path.exists(qss_file):
        with open(qss_file, "r") as f:
            app.setStyleSheet(f.read())

class GlobalScreenshotFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F12 or (event.key() == Qt.Key_S and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier)):
                self.capture_active_window()
                return True
        return super().eventFilter(obj, event)

    def capture_active_window(self):
        active_window = QApplication.activeWindow()
        if not active_window:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            active_window,
            "Guardar captura de pantalla vectorial (SVG)",
            os.path.expanduser("~/captura.svg"),
            "Vector Graphics (*.svg)"
        )
        if not file_path:
            return

        from PySide6.QtSvg import QSvgGenerator
        from PySide6.QtGui import QPainter
        
        widgets = [active_window] + active_window.findChildren(QWidget)
        saved_states = {}
        saved_caches = {}
        from PySide6.QtWidgets import QGraphicsItem
        
        for w in widgets:
            if isinstance(w, QLabel):
                pixmap_path = getattr(w, "_rqtll_pixmap_path", None)
                if pixmap_path and w.pixmap():
                    saved_states[w] = ('label', w.pixmap(), pixmap_path)
                    w.setPixmap(QPixmap())
            elif isinstance(w, (QPushButton, QToolButton)):
                icon_path = getattr(w, "_rqtll_icon_path", None)
                if icon_path and not w.icon().isNull():
                    saved_states[w] = ('button', w.icon(), icon_path)
                    w.setIcon(QIcon())
            elif isinstance(w, QGraphicsView):
                scene = w.scene()
                if scene:
                    for item in scene.items():
                        orig_cache = item.cacheMode()
                        if orig_cache != QGraphicsItem.CacheMode.NoCache:
                            saved_caches[item] = orig_cache
                            item.setCacheMode(QGraphicsItem.CacheMode.NoCache)

        generator = QSvgGenerator()
        generator.setFileName(file_path)
        generator.setSize(active_window.size())
        generator.setViewBox(active_window.rect())
        generator.setTitle(f"RQTLL Captura: {active_window.windowTitle()}")
        
        painter = QPainter(generator)
        active_window.render(painter, QPoint())

        from PySide6.QtSvg import QSvgRenderer
        
        for w, (w_type, original_val, path) in saved_states.items():
            if not os.path.exists(path):
                continue
            
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                continue
            
            if w_type == 'label':
                w_size = w.size()
                p_size = getattr(w, "_rqtll_pixmap_size", w_size)
                x = (w_size.width() - p_size.width()) // 2
                y = (w_size.height() - p_size.height()) // 2
                local_rect = QRect(x, y, p_size.width(), p_size.height())
                target_rect = QRect(w.mapTo(active_window, local_rect.topLeft()), local_rect.size())
                renderer.render(painter, target_rect)
                
            elif w_type == 'button':
                w_size = w.size()
                icon_size = w.iconSize()
                x = (w_size.width() - icon_size.width()) // 2
                y = (w_size.height() - icon_size.height()) // 2
                local_rect = QRect(x, y, icon_size.width(), icon_size.height())
                target_rect = QRect(w.mapTo(active_window, local_rect.topLeft()), local_rect.size())
                renderer.render(painter, target_rect)

        painter.end()

        for w, (w_type, original_val, path) in saved_states.items():
            if w_type == 'label':
                w.setPixmap(original_val)
            elif w_type == 'button':
                w.setIcon(original_val)

        for item, orig_cache in saved_caches.items():
            try:
                item.setCacheMode(orig_cache)
            except RuntimeError:
                pass

        import base64
        css_parts = []
        fonts_path = os.path.join(os.path.dirname(__file__), "external/rqtll_components/assets/fonts")
        if os.path.exists(fonts_path):
            for root, dirs, files in os.walk(fonts_path):
                for file in files:
                    if file.endswith((".ttf", ".otf")):
                        font_name = os.path.splitext(file)[0]
                        font_format = "truetype" if file.endswith(".ttf") else "opentype"
                        full_path = os.path.join(root, file)
                        try:
                            with open(full_path, "rb") as f:
                                b64_data = base64.b64encode(f.read()).decode("utf-8")
                            font_family_main = font_name.split("-")[0]
                            font_weight = "normal"
                            if "bold" in font_name.lower():
                                font_weight = "bold"
                            elif "light" in font_name.lower():
                                font_weight = "300"
                            elif "medium" in font_name.lower():
                                font_weight = "500"
                            
                            css_parts.append(f"""
@font-face {{
    font-family: '{font_name}';
    src: url(data:font/{font_format};charset=utf-8;base64,{b64_data}) format('{font_format}');
}}
@font-face {{
    font-family: '{font_family_main}';
    font-weight: {font_weight};
    src: url(data:font/{font_format};charset=utf-8;base64,{b64_data}) format('{font_format}');
}}
""")
                        except Exception as e:
                            print(f"Error encoding font {file}: {e}")
        
        fonts_css = "".join(css_parts)
        if fonts_css:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                idx = content.find("<svg")
                if idx != -1:
                    close_idx = content.find(">", idx)
                    if close_idx != -1:
                        style_block = f'\n<defs>\n<style type="text/css"><![CDATA[\n{fonts_css}\n]]></style>\n</defs>\n'
                        new_content = content[:close_idx+1] + style_block + content[close_idx+1:]
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
            except Exception as e:
                print(f"Failed to embed fonts in SVG: {e}")


class RQTLLRoot:
    def __init__(self, theme="dark.qss"):
        self.theme = theme
        self.icon_dirs = icon_dirs
        self.current_notify_id = None
        
        options = [
            ('grpc.max_receive_message_length', 1024 ** 3),
            ('grpc.max_send_message_length', 1024 ** 3)
        ]
        self.channel = grpc.insecure_channel('127.0.0.1:50051', options=options)
        self.package_stub = packages_pb2_grpc.PackageServiceStub(self.channel)
        self.installer_stub = installer_pb2_grpc.ROSInstallerServiceStub(self.channel)
        self.workspace_stub = workspace_pb2_grpc.WorkspaceServiceStub(self.channel)
        self.execution_stub = interactive_execution_pb2_grpc.CommandExecutionServiceStub(self.channel)
        self.data_stream_stub = data_stream_pb2_grpc.DataStreamServiceStub(self.channel)
        self.build_stub = build_pb2_grpc.BuildServiceStub(self.channel)
        self.introspection_stub = introspection_pb2_grpc.IntrospectionServiceStub(self.channel)
        self.node_execution_stub = execution_pb2_grpc.ExecutionServiceStub(self.channel)
        self.file_stub = file_system_pb2_grpc.FileServiceStub(self.channel)
        self.terminal_stub = terminal_pb2_grpc.TerminalServiceStub(self.channel)
        self.system_utils_stub = system_utils_pb2_grpc.SystemUtilsStub(self.channel)
        
        self.load_available_libraries()
        
        self.show_startup_notification()
        if not self.check_ros2_installed():
            self.wizard = WizardController(self)
            self.wizard.start()
        else:
            self.open_home()

    def load_available_libraries(self):
        self.available_libs = {"py": [], "cpp": [], "arduino": []}
        try:
            import types_pb2
            request = types_pb2.Empty()
            response = self.system_utils_stub.GetAvailableLibraries(request)
            self.available_libs["py"] = list(response.python_libraries)
            self.available_libs["cpp"] = list(response.cpp_libraries)
            self.available_libs["arduino"] = list(response.arduino_libraries)
            print(f"Loaded {len(response.python_libraries)} Python, {len(response.cpp_libraries)} C++, and {len(response.arduino_libraries)} Arduino libraries.")
        except Exception as e:
            print(f"Failed to load available libraries from backend: {e}")

    def check_ros2_installed(self) -> bool:
        try:
            request = packages_pb2.ListPackagesRequest(filter="ros-core")
            response_iter = self.package_stub.ListAvailablePackages(request)
            try:
                first_pkg = next(response_iter)
                distro = first_pkg.version if first_pkg.version else "Jazzy"
                if distro in ["Ninguna", "No detectada"]:
                    return False
                return True
            except StopIteration:
                return False
        except Exception:
            exit(1)

    def open_home(self):
        self.home = HomeController(self)
        self.pkg_manager = PackageManagerController(self, self.home.f0)

    def update_theme(self, theme: str):
        self.theme = theme

    def send_notification(self, title, msg, icon="logo", replace_id=None):
        icon_str = icon
        if icon == "logo":
            logo_path = os.path.join(base_path, "external/rqtll_components/assets/branding/logo.svg")
            if os.path.exists(logo_path):
                icon_str = logo_path
            else:
                icon_str = "dialog-information"
        
        cmd = ['notify-send', '--app-name', 'RQTLL IDE', '--icon', icon_str, title, msg]
        if replace_id:
            cmd.extend(['--replace-id', replace_id.strip()])
        cmd.append('--print-id')
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
            self.current_notify_id, _ = process.communicate()
        except Exception as e:
            print(f"Failed to run notify-send: {e}")

    def show_startup_notification(self):
        try:
            request = packages_pb2.ListPackagesRequest(filter="ros-base")
            response_iter = self.package_stub.ListAvailablePackages(request)
            try:
                first_pkg = next(response_iter)
                distro = first_pkg.version if first_pkg.version else "Jazzy"
                if distro in ["Ninguna", "No detectada"]:
                    self.send_notification("RQTLL IDE", "Motor funcionando pero ROS 2 no está instalado.", "logo")
                else:
                    self.send_notification("RQTLL IDE", f"Motor funcionando. ROS 2 {distro.capitalize()} listo.", "logo")
            except StopIteration:
                self.send_notification("RQTLL IDE", "Motor funcionando pero ROS 2 no está instalado.", "logo")
        except grpc.RpcError as e:
            msg = "Motor no disponible. Verifica que rqtll.service esté funcionando. (systemctl status rqtll.service)" if e.code() == grpc.StatusCode.UNAVAILABLE else f"Error de conexión con el backend: {e.details()}"
            self.send_notification("RQTLL Error", msg, "dialog-error")
        except Exception as e:
            self.send_notification("RQTLL Error", f"Error inesperado: {str(e)}", "dialog-error")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    theme = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark and "dark.qss" or "light.qss"
    components_path = os.path.join(os.path.dirname(__file__), "external/rqtll_components")
    load_resources(app, components_path, theme)

    screenshot_filter = GlobalScreenshotFilter()
    app.installEventFilter(screenshot_filter)

    from intern.compiler import update_terminal_colors
    update_terminal_colors("dark" if theme == "dark.qss" else "light")

    def _on_color_scheme_changed(*args, **kwargs):
        global theme
        new_theme = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark and "dark.qss" or "light.qss"
        if new_theme != theme:
            load_resources(app, components_path, new_theme)
            theme = new_theme
            update_terminal_colors("dark" if new_theme == "dark.qss" else "light")
            if 'root' in globals() and isinstance(globals().get('root'), RQTLLRoot):
                globals().get('root').update_theme(new_theme)
            try:
                tm = get_theme_manager()
                tm.themeChanged.emit(new_theme)
            except Exception:
                pass

    try:
        QGuiApplication.styleHints().colorSchemeChanged.connect(_on_color_scheme_changed)
    except Exception:
        pass
    root = RQTLLRoot(theme)
    sys.exit(app.exec())
