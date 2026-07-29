import os, json, subprocess, time
import build_pb2, data_stream_pb2, introspection_pb2, types_pb2, workspace_pb2, execution_pb2

from PySide6.QtCore import QObject, Qt, QSize, QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, 
                               QTextEdit, QLabel, QLineEdit, QPushButton)

try:
    from external.rqtll_widgets.utils.icon_loader import _resolve_icon
except Exception:
    try:
        from rqtll_widgets.utils.icon_loader import _resolve_icon
    except Exception:
        def _resolve_icon(icon_dirs, path, theme=None):
            return ""

COLOR_MAP = {}
BG_COLOR_MAP = {}
DEFAULT_FG = "#f8f8f2"
DEFAULT_BG = "#1e1e1e"

def update_terminal_colors(theme_name):
    global COLOR_MAP, BG_COLOR_MAP, DEFAULT_FG, DEFAULT_BG
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    palette_path = os.path.join(base_dir, "external", "rqtll_components", "styles", "palette.json")
    
    default_fg = {
        30: "#141417", 31: "#D62C2C", 32: "#42DD76", 33: "#FFB638",
        34: "#28A9FF", 35: "#A95EFF", 36: "#14E5D4", 37: "#c8c8c8",
        90: "#5b5b5f", 91: "#fc0606", 92: "#21fe9b", 93: "#ffb838",
        94: "#28a9ff", 95: "#e66dff", 96: "#00f9e5", 97: "#fbfbfb"
    }
    default_bg = {
        40: "#141417", 41: "#D62C2C", 42: "#42DD76", 43: "#FFB638",
        44: "#28A9FF", 45: "#A95EFF", 46: "#14E5D4", 47: "#c8c8c8"
    }

    if not os.path.exists(palette_path):
        COLOR_MAP.clear()
        COLOR_MAP.update(default_fg)
        BG_COLOR_MAP.clear()
        BG_COLOR_MAP.update(default_bg)
        if theme_name == "dark":
            DEFAULT_FG = "#c8c8c8"
            DEFAULT_BG = "#141417"
        else:
            DEFAULT_FG = "#181818"
            DEFAULT_BG = "#f4f4f4"
        return

    try:
        with open(palette_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        themes = data.get("themes", {})
        theme_colors = themes.get(theme_name, themes.get("dark", {}))
        
        DEFAULT_FG = theme_colors.get("color", "#f8f8f2")
        DEFAULT_BG = theme_colors.get("background", "#1e1e1e")
        
        key_mapping = {
            "ansi_black": (30, 40),
            "ansi_red": (31, 41),
            "ansi_green": (32, 42),
            "ansi_yellow": (33, 43),
            "ansi_blue": (34, 44),
            "ansi_magenta": (35, 45),
            "ansi_cyan": (36, 46),
            "ansi_white": (37, 47),
            "ansi_bright_black": (90, None),
            "ansi_bright_red": (91, None),
            "ansi_bright_green": (92, None),
            "ansi_bright_yellow": (93, None),
            "ansi_bright_blue": (94, None),
            "ansi_bright_magenta": (95, None),
            "ansi_bright_cyan": (96, None),
            "ansi_bright_white": (97, None)
        }
        
        new_fg = {}
        new_bg = {}
        
        for json_key, (fg_code, bg_code) in key_mapping.items():
            color_val = theme_colors.get(json_key)
            if color_val:
                new_fg[fg_code] = color_val
                if bg_code is not None:
                    new_bg[bg_code] = color_val
                    
        COLOR_MAP.clear()
        COLOR_MAP.update(new_fg)
        BG_COLOR_MAP.clear()
        BG_COLOR_MAP.update(new_bg)
    except Exception:
        COLOR_MAP.clear()
        COLOR_MAP.update(default_fg)
        BG_COLOR_MAP.clear()
        BG_COLOR_MAP.update(default_bg)
        if theme_name == "dark":
            DEFAULT_FG = "#c8c8c8"
            DEFAULT_BG = "#141417"
        else:
            DEFAULT_FG = "#181818"
            DEFAULT_BG = "#f4f4f4"

update_terminal_colors("dark")


class TerminalEmulator:
    def __init__(self, rows=1000, cols=150):
        self.rows = rows
        self.cols = cols
        self.clear()
        
        self.fg_color = None
        self.bg_color = None
        self.bold = False

    def clear(self):
        self.screen = [[{"char": " ", "fg": None, "bg": None, "bold": False} for _ in range(self.cols)] for _ in range(self.rows)]
        self.cursor_row = 0
        self.cursor_col = 0
        self.alt_charset = False

    def write(self, raw_text):
        import re
        ansi_re = re.compile(r'\x1b\[([?0-9;]*)([a-zA-Z])|\x1b\((.)|\x1b\)(.)|\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)|\x1b(.)')
        
        pos = 0
        while pos < len(raw_text):
            match = ansi_re.search(raw_text, pos)
            if not match:
                self.print_string(raw_text[pos:])
                break
                
            if match.start() > pos:
                self.print_string(raw_text[pos:match.start()])
                
            if match.group(2): # CSI sequence
                params = match.group(1)
                cmd = match.group(2)
                self.handle_csi(params, cmd)
            elif match.group(3) or match.group(4): # Charset
                charset = match.group(3) or match.group(4)
                if charset == '0':
                    self.alt_charset = True
                elif charset == 'B':
                    self.alt_charset = False
            elif match.group(5): # OSC sequence
                pass # Ignore window/icon title changes
            elif match.group(6): # Simple ESC sequence
                pass # Ignore other simple escape codes
                    
            pos = match.end()

    def print_string(self, s):
        for char in s:
            if char == '\x0e': # SO
                self.alt_charset = True
                continue
            elif char == '\x0f': # SI
                self.alt_charset = False
                continue
                
            if char == '\n':
                self.cursor_row += 1
                self.cursor_col = 0
                if self.cursor_row >= self.rows:
                    self.scroll_up()
            elif char == '\r':
                self.cursor_col = 0
            elif char == '\t':
                self.cursor_col = (self.cursor_col + 8) & ~7
                if self.cursor_col >= self.cols:
                    self.cursor_col = self.cols - 1
            elif char == '\x08' or char == '\x7f':
                if self.cursor_col > 0:
                    self.cursor_col -= 1
            else:
                if self.alt_charset:
                    LINE_DRAWING_MAP = {
                        'q': '─', 'x': '│', 'l': '┌', 'k': '┐',
                        'm': '└', 'j': '┘', 't': '├', 'u': '┤',
                        'v': '┴', 'w': '┬', 'n': '┼', 'a': '▒', '~': '·'
                    }
                    char = LINE_DRAWING_MAP.get(char, char)
                    
                if self.cursor_row >= self.rows:
                    self.scroll_up()
                if self.cursor_col >= self.cols:
                    self.cursor_row += 1
                    self.cursor_col = 0
                    if self.cursor_row >= self.rows:
                        self.scroll_up()
                        
                self.screen[self.cursor_row][self.cursor_col] = {
                    "char": char,
                    "fg": self.fg_color,
                    "bg": self.bg_color,
                    "bold": self.bold
                }
                self.cursor_col += 1

    def scroll_up(self):
        self.screen.pop(0)
        self.screen.append([{"char": " ", "fg": None, "bg": None, "bold": False} for _ in range(self.cols)])
        self.cursor_row = self.rows - 1

    def handle_csi(self, params, cmd):
        parts = [int(p) for p in params.split(';') if p.isdigit()]
        
        if cmd == 'A':
            n = parts[0] if parts else 1
            self.cursor_row = max(0, self.cursor_row - n)
        elif cmd == 'B':
            n = parts[0] if parts else 1
            self.cursor_row = min(self.rows - 1, self.cursor_row + n)
        elif cmd == 'C':
            n = parts[0] if parts else 1
            self.cursor_col = min(self.cols - 1, self.cursor_col + n)
        elif cmd == 'D':
            n = parts[0] if parts else 1
            self.cursor_col = max(0, self.cursor_col - n)
        elif cmd in ('H', 'f'):
            r = parts[0] - 1 if len(parts) > 0 else 0
            c = parts[1] - 1 if len(parts) > 1 else 0
            self.cursor_row = max(0, min(self.rows - 1, r))
            self.cursor_col = max(0, min(self.cols - 1, c))
        elif cmd == 'J':
            mode = parts[0] if parts else 0
            if mode == 2:
                self.clear()
        elif cmd == 'K':
            mode = parts[0] if parts else 0
            if mode == 0:
                for c in range(self.cursor_col, self.cols):
                    self.screen[self.cursor_row][c] = {"char": " ", "fg": None, "bg": None, "bold": False}
            elif mode == 1:
                for c in range(0, self.cursor_col + 1):
                    self.screen[self.cursor_row][c] = {"char": " ", "fg": None, "bg": None, "bold": False}
            elif mode == 2:
                self.screen[self.cursor_row] = [{"char": " ", "fg": None, "bg": None, "bold": False} for _ in range(self.cols)]
        elif cmd == 'm':
            if not params or params == '0':
                self.fg_color = None
                self.bg_color = None
                self.bold = False
            else:
                for part in params.split(';'):
                    if not part:
                        continue
                    try:
                        code = int(part)
                        if code == 0:
                            self.fg_color = None
                            self.bg_color = None
                            self.bold = False
                        elif code == 1:
                            self.bold = True
                        elif code in COLOR_MAP:
                            self.fg_color = COLOR_MAP[code]
                        elif code in BG_COLOR_MAP:
                            self.bg_color = BG_COLOR_MAP[code]
                    except ValueError:
                        pass

    def get_html(self):
        import html
        html_lines = []
        
        last_non_empty_row = 0
        for r in range(self.rows):
            has_content = any(cell["char"] != " " for cell in self.screen[r])
            if has_content:
                last_non_empty_row = r
                
        for r in range(last_non_empty_row + 1):
            line_html = ""
            current_seg = []
            current_style = None
            
            row_cells = self.screen[r]
            last_non_space_col = -1
            for c in range(self.cols - 1, -1, -1):
                if row_cells[c]["char"] != " ":
                    last_non_space_col = c
                    break
            
            for c in range(last_non_space_col + 1):
                cell = row_cells[c]
                style = (cell["fg"], cell["bg"], cell["bold"])
                if style != current_style:
                    if current_seg:
                        seg_text = html.escape("".join(current_seg))
                        fg, bg, bold = current_style
                        styles = []
                        if fg:
                            styles.append(f"color: {fg};")
                        if bg:
                            styles.append(f"background-color: {bg};")
                        if bold:
                            styles.append("font-weight: bold;")
                        if styles:
                            style_str = " ".join(styles)
                            line_html += f'<span style="{style_str}">{seg_text}</span>'
                        else:
                            line_html += seg_text
                        current_seg = []
                    current_style = style
                current_seg.append(cell["char"])
                
            if current_seg:
                seg_text = html.escape("".join(current_seg))
                fg, bg, bold = current_style
                styles = []
                if fg:
                    styles.append(f"color: {fg};")
                if bg:
                    styles.append(f"background-color: {bg};")
                if bold:
                    styles.append("font-weight: bold;")
                if styles:
                    style_str = " ".join(styles)
                    line_html += f'<span style="{style_str}">{seg_text}</span>'
                else:
                    line_html += seg_text
                    
            html_lines.append(line_html)
            
        body = "<br/>".join(html_lines)
        global DEFAULT_FG, DEFAULT_BG
        return (
            f'<div style="margin: 0; font-family: monospace; font-size: 13px; white-space: pre; '
            f'color: {DEFAULT_FG}; background-color: {DEFAULT_BG}; line-height: 1.2;">{body}</div>'
        )

# --- WORKER THREADS FOR GRPC STREAMING ---

class BuildWorker(QThread):
    log_received = Signal(str)
    finished_status = Signal(bool, str, list, list) # success, message, nodes, launchers

    def __init__(self, stub, workspace_path):
        super().__init__()
        self.stub = stub
        self.workspace_path = workspace_path

    def run(self):
        try:
            request = build_pb2.BuildRequest(
                workspace_path=self.workspace_path,
                symlink_install=True
            )
            response_stream = self.stub.BuildWorkspace(request)
            for event in response_stream:
                if event.HasField("log"):
                    self.log_received.emit(event.log.message)
                elif event.HasField("status"):
                    nodes = []
                    launchers = []
                    if "nodes" in event.status.details:
                        try:
                            nodes = json.loads(event.status.details["nodes"])
                        except Exception:
                            pass
                    if "launchers" in event.status.details:
                        try:
                            launchers = json.loads(event.status.details["launchers"])
                        except Exception:
                            pass
                    self.finished_status.emit(event.status.ok, event.status.message, nodes, launchers)
                    break
        except Exception as e:
            self.finished_status.emit(False, f"gRPC Error: {e}", [], [])


class NodeExecutionWorker(QThread):
    log_received = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, stub, package, executable, use_launch=False, launch_file=""):
        super().__init__()
        self.stub = stub
        self.package = package
        self.executable = executable
        self.use_launch = use_launch
        self.launch_file = launch_file
        self.running = True
        self.stream = None

    def run(self):
        try:
            req = execution_pb2.RunRequest(
                package=self.package,
                executable=self.executable,
                use_launch=self.use_launch,
                launch_file=self.launch_file
            )
            self.stream = self.stub.Run(req)
            for event in self.stream:
                if not self.running:
                    break
                if event.HasField("log"):
                    self.log_received.emit(event.log.message)
                elif event.HasField("status"):
                    self.finished.emit(event.status.ok, event.status.message)
                    break
        except Exception as e:
            self.finished.emit(False, str(e))

    def cancel(self):
        self.running = False
        if self.stream:
            try:
                self.stream.cancel()
            except Exception:
                pass


class CleanWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, stub):
        super().__init__()
        self.stub = stub

    def run(self):
        try:
            request = build_pb2.CleanRequest(
                clean_build=True,
                clean_install=True,
                clean_log=True
            )
            response = self.stub.CleanWorkspace(request)
            self.finished.emit(response.ok, response.message)
        except Exception as e:
            self.finished.emit(False, f"gRPC Error: {e}")


class BagRecordWorker(QThread):
    log_received = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, stub, output_path):
        super().__init__()
        self.stub = stub
        self.output_path = output_path
        self.stream = None

    def run(self):
        try:
            request = data_stream_pb2.RecordRequest(
                record_all=True,
                output_path=self.output_path
            )
            self.stream = self.stub.Record(request)
            for event in self.stream:
                if event.HasField("log"):
                    self.log_received.emit(event.log.message)
                elif event.HasField("status"):
                    self.finished.emit(event.status.ok, event.status.message)
                    break
        except Exception as e:
            self.finished.emit(False, f"gRPC Error: {e}")

    def cancel(self):
        if self.stream:
            try:
                self.stream.cancel()
            except Exception:
                pass


class BagPlayWorker(QThread):
    log_received = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, stub, path):
        super().__init__()
        self.stub = stub
        self.path = path
        self.stream = None

    def run(self):
        try:
            request = data_stream_pb2.PlayRequest(
                path=self.path
            )
            self.stream = self.stub.Play(request)
            for event in self.stream:
                if event.HasField("log"):
                    self.log_received.emit(event.log.message)
                elif event.HasField("status"):
                    self.finished.emit(event.status.ok, event.status.message)
                    break
        except Exception as e:
            self.finished.emit(False, f"gRPC Error: {e}")

    def cancel(self):
        if self.stream:
            try:
                self.stream.cancel()
            except Exception:
                pass


class ListTopicsWorker(QThread):
    topics_received = Signal(list)

    def __init__(self, stub):
        super().__init__()
        self.stub = stub

    def run(self):
        try:
            response = self.stub.ListTopics(types_pb2.Empty())
            topics = []
            for t in response.topics:
                topics.append({
                    'name': t.name,
                    'type': t.message_type,
                    'publishers': t.publisher_count,
                    'subscribers': t.subscriber_count
                })
            self.topics_received.emit(topics)
        except Exception:
            pass


class TopicSubscribeWorker(QThread):
    message_received = Signal(str, dict) # message text, meta map
    finished = Signal()

    def __init__(self, stub, topic, message_type):
        super().__init__()
        self.stub = stub
        self.topic = topic
        self.message_type = message_type
        self.stream = None

    def run(self):
        try:
            request = data_stream_pb2.SubscribeRequest(
                topic=self.topic,
                message_type=self.message_type
            )
            self.stream = self.stub.Subscribe(request)
            for msg in self.stream:
                info = msg.meta.get("info", "")
                echo = msg.meta.get("echo", "")
                self.message_received.emit(echo, {"info": info})
        except Exception:
            pass
        self.finished.emit()

    def cancel(self):
        if self.stream:
            try:
                self.stream.cancel()
            except Exception:
                pass


class CompilerController(QObject):
    def __init__(self, ide_controller):
        super().__init__()
        self.ide = ide_controller
        self.window = None
        self.ui = None
        
        self.spawned_tabs = {}
        self.original_icons = {}
        self.publisher_buttons = {}
        self.echo_tabs = {}
        self.dynamic_topics = {}
        self.pub_counters = {}
        self.sub_counters = {}
        self.emulators = {}
        self.active_node_workers = {}

        # Bag Recording and Playing states
        self.is_recording_bag = False
        self.is_playing_bag = False
        self.record_bag_worker = None
        self.play_bag_worker = None
        self.active_echo_workers = {}
        
        # Dynamic Nodes and Launchers widgets references
        self.dynamic_node_widgets = []
        self.dynamic_launcher_widgets = []

        # Periodic Topics Timer
        self.topics_timer = QTimer(self)
        self.topics_timer.timeout.connect(self.refresh_topics_list)

    def find_workspace_root(self):
        return getattr(self.ide, 'ws_path', None) or os.path.expanduser("~/Proyectos/rqtll")

    def bind(self, window):
        self.window = window
        self.ui = window.ui
        
        # Reset trackers
        self.spawned_tabs = {}
        self.original_icons = {}
        self.publisher_buttons = {}
        self.echo_tabs = {}
        self.dynamic_topics = {}
        self.pub_counters = {}
        self.sub_counters = {}
        self.active_echo_workers = {}
        self.dynamic_node_widgets = []
        self.dynamic_launcher_widgets = []
        self.emulators = {}
        self.active_node_workers = {}

        self.ui.tabWidget.clear()
        
        # Hide mockup items
        if hasattr(self.ui, 'LABELNode1') and self.ui.LABELNode1 is not None:
            self.ui.LABELNode1.setVisible(False)
        if hasattr(self.ui, 'BTNNode_1') and self.ui.BTNNode_1 is not None:
            self.ui.BTNNode_1.setVisible(False)
        if hasattr(self.ui, 'LABELLaunch1') and self.ui.LABELLaunch1 is not None:
            self.ui.LABELLaunch1.setVisible(False)
        if hasattr(self.ui, 'BTNLaunch_1') and self.ui.BTNLaunch_1 is not None:
            self.ui.BTNLaunch_1.setVisible(False)
        
        self.ui.tabWidget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.set_layout_visible(self.ui.verticalLayout_8, False)
        self.set_layout_visible(self.ui.verticalLayout_6, False)
        self.set_layout_visible(self.ui.LAYOUTTopic1, False)
        self.ui.BTNROSPlayDir.clicked.connect(self.select_ros_bag_dir)
        
        if hasattr(self.ui, 'BTNNode_1') and self.ui.BTNNode_1 is not None:
            self.ui.BTNNode_1.clicked.connect(self.on_btn_node_clicked)
        if hasattr(self.ui, 'BTNLaunch_1') and self.ui.BTNLaunch_1 is not None:
            self.ui.BTNLaunch_1.clicked.connect(self.on_btn_launch_clicked)
            
        self.ui.BTNPUBConfig.clicked.connect(self.toggle_layout_8)
        self.ui.BTNPUBConfig_1.clicked.connect(self.toggle_layout_6)

        self.ui.BTNMSGDir.clicked.connect(self.select_msg_file_0)
        self.ui.BTNMSGDir_1.clicked.connect(self.select_msg_file_1)
        
        self.ui.BTNPUBTopic.clicked.connect(self.on_btn_pub_topic_clicked)
        self.ui.BTNECHOTopic_1.clicked.connect(self.on_btn_echo_topic_clicked)
        self.ui.BTNPUBTopic_1.clicked.connect(self.on_btn_pub_topic_1_clicked)

        # Connect ROS Compiler and Bag Play buttons
        self.ui.BTNROSColcon.clicked.connect(self.on_btn_ros_colcon_clicked)
        self.ui.BTNROSCLean.clicked.connect(self.on_btn_ros_clean_clicked)
        self.ui.BTNROSBag.clicked.connect(self.on_btn_ros_bag_clicked)
        self.ui.BTNROSPlay.clicked.connect(self.on_btn_ros_play_clicked)

        # Call OpenWorkspace on backend to align paths
        ws_root = self.find_workspace_root()
        try:
            req = workspace_pb2.OpenWorkspaceRequest(path=ws_root)
            self.ide.root.workspace_stub.OpenWorkspace.future(req)
        except Exception:
            pass

        # Start periodic topic list retrieval
        self.topics_timer.start(5000)

    def set_layout_visible(self, layout, visible):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                item.widget().setVisible(visible)
            elif item.layout():
                self.set_layout_visible(item.layout(), visible)

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                elif item.layout() is not None:
                    self.clear_layout(item.layout())

    def delete_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                elif item.layout() is not None:
                    self.delete_layout(item.layout())
            layout.setParent(None)

    def select_ros_bag_dir(self):
        selected_dir = QFileDialog.getExistingDirectory(
            self.window, "Seleccionar Carpeta para ROS Bag", os.path.expanduser("~")
        )
        if not selected_dir:
            return
        
        home = os.path.expanduser("~")
        if selected_dir == home:
            self.ui.EDITROSPlay.setText("~")
        else:
            try:
                rel_path = os.path.relpath(selected_dir, home)
                if rel_path.startswith(".."):
                    self.ui.EDITROSPlay.setText(selected_dir)
                else:
                    self.ui.EDITROSPlay.setText(f"~/{rel_path}")
            except Exception:
                self.ui.EDITROSPlay.setText(selected_dir)

    def create_duplicate_tab(self, title, clone_label=True):
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        text_edit = QTextEdit(tab_widget)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        text_edit.setOverwriteMode(False)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        if clone_label:
            label_info = QLabel(tab_widget)
            label_info.setText("Bandwidth: 0 B/s \t\tPublicadores: 0\nFrecuencia: 0 hz\t\tSuscriptores: 0\nTipo: none")
            layout.addWidget(label_info)
        
        self.ui.tabWidget.addTab(tab_widget, title)
        self.ui.tabWidget.setCurrentWidget(tab_widget)
        return tab_widget

    def toggle_tab_for_button(self, button, get_title_func, disable_write=False, is_pub_topic=False, clear_fields_func=None, layout_to_hide=None, clone_label=True):
        if button in self.spawned_tabs:
            widget = self.spawned_tabs[button]
            idx = self.ui.tabWidget.indexOf(widget)
            if idx != -1:
                self.ui.tabWidget.removeTab(idx)
                widget.deleteLater()
            if button in self.original_icons:
                button.setIcon(self.original_icons[button])
                del self.original_icons[button]
            del self.spawned_tabs[button]
        else:
            title = get_title_func()
            if not title:
                return
            
            n = self.sub_counters[title] = self.sub_counters.get(title, 0) + 1
            indexed_title = f"{title} [SUB {n}]"
            
            self.original_icons[button] = button.icon()
            
            icon = QIcon()
            icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
            theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
            icon_path = _resolve_icon(icon_dirs, os.path.join('icons', 'close', 'default.svg'), theme=theme)
            icon.addFile(icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
            button.setIcon(icon)
            
            tab_widget = self.create_duplicate_tab(indexed_title, clone_label=clone_label)
            self.spawned_tabs[button] = tab_widget
            
            if is_pub_topic:
                if clear_fields_func:
                    clear_fields_func()
                if layout_to_hide:
                    self.set_layout_visible(layout_to_hide, False)

    def on_tab_close_requested(self, index):
        widget = self.ui.tabWidget.widget(index)
        if widget:
            if widget in self.publisher_buttons:
                self.close_specific_publisher(widget)
                return
            for topic_name, (tab_widget, btn_echo) in list(self.echo_tabs.items()):
                if tab_widget == widget:
                    self.close_echo_tab(topic_name, btn_echo)
                    return
            for button, (worker, spawned_widget) in list(self.active_node_workers.items()):
                if spawned_widget == widget:
                    worker.cancel()
                    worker.wait()
                    del self.active_node_workers[button]
                    if button in self.original_icons:
                        button.setIcon(self.original_icons[button])
                        del self.original_icons[button]
                    break
            for button, spawned_widget in list(self.spawned_tabs.items()):
                if spawned_widget == widget:
                    button.setIcon(self.original_icons[button])
                    del self.spawned_tabs[button]
                    del self.original_icons[button]
                    break
            self.ui.tabWidget.removeTab(index)
            widget.deleteLater()

    def on_btn_node_clicked(self):
        self.toggle_tab_for_button(
            button=self.ui.BTNNode_1,
            get_title_func=lambda: self.ui.LABELNode1.text().strip()
        )

    def on_btn_launch_clicked(self):
        self.toggle_tab_for_button(
            button=self.ui.BTNLaunch_1,
            get_title_func=lambda: self.ui.LABELLaunch1.text().strip(),
            clone_label=False
        )

    def on_btn_echo_topic_clicked(self):
        topic_name = self.ui.LABELTopic_1.text().strip() or "Tópico"
        self.toggle_echo_tab(topic_name, self.ui.BTNECHOTopic_1)

    def on_btn_pub_topic_1_clicked(self):
        topic_name = self.ui.LABELTopic_1.text().strip() or "Tópico"
        msg_type = self.ui.EDITMSGType.text().strip() or "std_msgs/msg/String"
        msg_content = self.ui.EDITMSGContent_1.toPlainText().strip()
        self.spawn_publisher_for_topic(topic_name, self.ui.LAYOUTTopic1, self.ui.BTNPUBConfig_1, msg_type, msg_content)
        self.ui.EDITMSGContent_1.clear()
        self.set_layout_visible(self.ui.verticalLayout_6, False)

    # --- TOPICS PUBLISHER AND ECHO LIFECYCLE ---

    def spawn_publisher_for_topic(self, topic_name, layout_topic, btn_config, msg_type=None, msg_content=None):
        n = self.pub_counters[topic_name] = self.pub_counters.get(topic_name, 0) + 1
        indexed_title = f"{topic_name} [PUB {n}]"
        
        tab_widget = self.create_duplicate_tab(indexed_title, clone_label=True)
        
        new_pub_btn = QPushButton()
        icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
        theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
        
        pub_icon = QIcon()
        pub_path = _resolve_icon(icon_dirs, os.path.join('icons', 'close', 'default.svg'), theme=theme)
        pub_icon.addFile(pub_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        new_pub_btn.setIcon(pub_icon)
        new_pub_btn.setFixedSize(btn_config.size())
        new_pub_btn.setCursor(btn_config.cursor())
        
        idx = layout_topic.indexOf(btn_config)
        layout_topic.insertWidget(idx, new_pub_btn)
        
        new_pub_btn.clicked.connect(lambda: self.close_specific_publisher(tab_widget))
        
        self.publisher_buttons[tab_widget] = (new_pub_btn, layout_topic, topic_name)

        # Publish once via gRPC
        actual_type = msg_type or "std_msgs/msg/String"
        actual_content = msg_content or "{}"
        try:
            req = data_stream_pb2.PublishRequest(
                topic=topic_name,
                message_type=actual_type,
                data=actual_content.encode('utf-8')
            )
            self.ide.root.data_stream_stub.Publish.future(req)
            text_edit = tab_widget.findChild(QTextEdit)
            if text_edit:
                text_edit.append(f"[{topic_name}] Message published once:\n{actual_content}\n")
        except Exception as e:
            text_edit = tab_widget.findChild(QTextEdit)
            if text_edit:
                text_edit.append(f"Error publishing: {e}\n")

    def close_specific_publisher(self, tab_widget):
        if tab_widget in self.publisher_buttons:
            new_pub_btn, layout_topic, topic_name = self.publisher_buttons[tab_widget]
            
            idx = self.ui.tabWidget.indexOf(tab_widget)
            if idx != -1:
                self.ui.tabWidget.removeTab(idx)
            tab_widget.deleteLater()
            
            layout_topic.removeWidget(new_pub_btn)
            new_pub_btn.deleteLater()
            
            del self.publisher_buttons[tab_widget]
            
            self.check_and_remove_topic(topic_name)

    def toggle_echo_tab(self, topic_name, btn_echo):
        if topic_name in self.echo_tabs:
            self.close_echo_tab(topic_name, btn_echo)
        else:
            self.open_echo_tab(topic_name, btn_echo)

    def open_echo_tab(self, topic_name, btn_echo):
        n = self.sub_counters[topic_name] = self.sub_counters.get(topic_name, 0) + 1
        indexed_title = f"{topic_name} [SUB {n}]"
        
        tab_widget = self.create_duplicate_tab(indexed_title, clone_label=True)
        self.echo_tabs[topic_name] = (tab_widget, btn_echo)
        
        icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
        theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
        close_icon = QIcon()
        close_path = _resolve_icon(icon_dirs, os.path.join('icons', 'close', 'default.svg'), theme=theme)
        close_icon.addFile(close_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        btn_echo.setIcon(close_icon)

        # Retrieve topic type from dynamic_topics if exist, or assume generic
        msg_type = "std_msgs/msg/String"
        if topic_name in self.dynamic_topics:
            msg_type = self.dynamic_topics[topic_name]['edit_msg_type'].text().strip()

        # Start background stream subscription
        worker = TopicSubscribeWorker(self.ide.root.data_stream_stub, topic_name, msg_type)
        text_edit = tab_widget.findChild(QTextEdit)
        label_info = tab_widget.findChild(QLabel)

        def handle_message(msg_content, meta):
            try:
                if text_edit and msg_content:
                    text_edit.append(msg_content + "\n")
                if label_info and meta.get("info"):
                    # Parse publishers/subscribers
                    pub_cnt = 0
                    sub_cnt = 0
                    bw = "---"
                    hz = "---"
                    #print(meta["info"])
                    for line in meta["info"].splitlines():
                        if "Publisher count:" in line:
                            pub_cnt = line.split(":")[-1].strip()
                        elif "Subscription count:" in line or "Subscriber count:" in line:
                            sub_cnt = line.split(":")[-1].strip()
                        elif "/s from" in line:
                            # get from first position to '/s'
                            bw = line.split("/s")[0]
                        elif "average rate:" in line:
                            hz = line.split(":")[-1].strip()
                    label_info.setText(f"Bandwidth: {bw} \t\tPublicadores: {pub_cnt}\nFrecuencia: {hz} hz\t\tSuscriptores: {sub_cnt}\nTipo: {msg_type}")
            except RuntimeError:
                worker.cancel()

        worker.message_received.connect(handle_message)
        worker.start()
        self.active_echo_workers[topic_name] = worker

    def close_echo_tab(self, topic_name, btn_echo=None):
        if topic_name in self.echo_tabs:
            tab_widget, original_btn_echo = self.echo_tabs[topic_name]
            btn = btn_echo or original_btn_echo
            
            idx = self.ui.tabWidget.indexOf(tab_widget)
            if idx != -1:
                self.ui.tabWidget.removeTab(idx)
            tab_widget.deleteLater()
            
            icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
            theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
            echo_icon = QIcon()
            echo_path = _resolve_icon(icon_dirs, os.path.join('icons', 'arrows', 'down.svg'), theme=theme)
            echo_icon.addFile(echo_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
            btn.setIcon(echo_icon)
            
            del self.echo_tabs[topic_name]

            if topic_name in self.active_echo_workers:
                self.active_echo_workers[topic_name].cancel()
                self.active_echo_workers[topic_name].wait()
                del self.active_echo_workers[topic_name]
            
            self.check_and_remove_topic(topic_name)

    def check_and_remove_topic(self, topic_name):
        if topic_name in self.dynamic_topics:
            topic_info = self.dynamic_topics[topic_name]
            
            has_active_pubs = False
            for pub_btn, layout, t_name in self.publisher_buttons.values():
                if t_name == topic_name:
                    has_active_pubs = True
                    break
            
            has_active_echo = (topic_name in self.echo_tabs)
            
            if not has_active_pubs and not has_active_echo:
                self.delete_layout(topic_info['layout_topic'])
                self.delete_layout(topic_info['layout_v6'])
                del self.dynamic_topics[topic_name]

    # --- DYNAMIC TOPICS HANDLING ---

    def on_btn_pub_topic_clicked(self):
        topic_text = self.ui.EDITNEWTopic.text().strip() or "new-topic"
        topic_name = topic_text if topic_text.startswith("/") else "/" + topic_text.replace(" ", "-")
        
        if topic_name not in self.dynamic_topics:
            self.create_dynamic_topic_layouts(topic_name)
            
        topic_info = self.dynamic_topics[topic_name]
        msg_type = topic_info['edit_msg_type'].text().strip() or "std_msgs/msg/String"
        msg_content = self.ui.EDITMSGContent.toPlainText().strip()
        self.spawn_publisher_for_topic(topic_name, topic_info['layout_topic'], topic_info['btn_config'], msg_type, msg_content)
        
        self.ui.EDITNEWTopic.clear()
        if hasattr(self.ui, 'EDITMSGType'):
            self.ui.EDITMSGType.clear()
        self.ui.EDITMSGContent.clear()
        self.set_layout_visible(self.ui.verticalLayout_8, False)

    def create_dynamic_topic_layouts(self, topic_name):
        icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
        theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
        
        echo_icon = QIcon()
        echo_path = _resolve_icon(icon_dirs, os.path.join('icons', 'arrows', 'down.svg'), theme=theme)
        echo_icon.addFile(echo_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        
        settings_icon = QIcon()
        settings_path = _resolve_icon(icon_dirs, os.path.join('icons', 'settings', 'default.svg'), theme=theme)
        settings_icon.addFile(settings_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        
        folder_icon = QIcon()
        folder_path = _resolve_icon(icon_dirs, os.path.join('icons', 'folder', 'default.svg'), theme=theme)
        folder_icon.addFile(folder_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        
        pub_icon = QIcon()
        pub_path = _resolve_icon(icon_dirs, os.path.join('icons', 'arrows', 'up.svg'), theme=theme)
        pub_icon.addFile(pub_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)

        layout_topic_n = QHBoxLayout()
        label_topic_n = QLabel(topic_name)
        label_topic_n.setStyleSheet(self.ui.LABELTopic_1.styleSheet())
        layout_topic_n.addWidget(label_topic_n)
        
        btn_echo_n = QPushButton()
        btn_echo_n.setIcon(echo_icon)
        btn_echo_n.setFixedSize(self.ui.BTNECHOTopic_1.size())
        btn_echo_n.setCursor(self.ui.BTNECHOTopic_1.cursor())
        layout_topic_n.addWidget(btn_echo_n)
        
        btn_config_n = QPushButton()
        btn_config_n.setIcon(settings_icon)
        btn_config_n.setFixedSize(self.ui.BTNPUBConfig_1.size())
        btn_config_n.setCursor(self.ui.BTNPUBConfig_1.cursor())
        layout_topic_n.addWidget(btn_config_n)
        
        v_layout_6_n = QVBoxLayout()
        h_layout_2_n = QHBoxLayout()
        lbl_type = QLabel("Tipo:")
        edit_msg_type = QLineEdit()
        edit_msg_type.setText(self.ui.EDITMSGType.text())
        h_layout_2_n.addWidget(lbl_type)
        h_layout_2_n.addWidget(edit_msg_type)
        v_layout_6_n.addLayout(h_layout_2_n)
        
        lbl_content = QLabel("Contenido:")
        v_layout_6_n.addWidget(lbl_content)
        
        h_layout_8_n = QHBoxLayout()
        lbl_msg = QLabel("Mensaje:")
        btn_msg_dir = QPushButton()
        btn_msg_dir.setIcon(folder_icon)
        btn_msg_dir.setFixedSize(self.ui.BTNMSGDir.size())
        h_layout_8_n.addWidget(lbl_msg)
        h_layout_8_n.addWidget(btn_msg_dir)
        v_layout_6_n.addLayout(h_layout_8_n)
        
        edit_msg_content = QTextEdit()
        edit_msg_content.setPlainText(self.ui.EDITMSGContent.toPlainText())
        v_layout_6_n.addWidget(edit_msg_content)
        
        btn_pub_n = QPushButton("Publicar mensaje")
        btn_pub_n.setIcon(pub_icon)
        btn_pub_n.setFixedHeight(32)
        v_layout_6_n.addWidget(btn_pub_n)
        
        insert_idx = self.ui.verticalLayout.count() - 1
        for i in range(self.ui.verticalLayout.count()):
            item = self.ui.verticalLayout.itemAt(i)
            if item.spacerItem():
                insert_idx = i
                break
        
        self.ui.verticalLayout.insertLayout(insert_idx, layout_topic_n)
        self.ui.verticalLayout.insertLayout(insert_idx + 1, v_layout_6_n)
        
        self.set_layout_visible(v_layout_6_n, False)
        
        self.dynamic_topics[topic_name] = {
            'layout_topic': layout_topic_n,
            'layout_v6': v_layout_6_n,
            'btn_echo': btn_echo_n,
            'btn_config': btn_config_n,
            'edit_msg_content': edit_msg_content,
            'edit_msg_type': edit_msg_type
        }
        
        # Connect actions
        btn_echo_n.clicked.connect(lambda: self.toggle_echo_tab(topic_name, btn_echo_n))
        btn_config_n.clicked.connect(lambda: self.set_layout_visible(v_layout_6_n, not edit_msg_content.isVisible()))
        btn_msg_dir.clicked.connect(lambda: self.select_msg_file_for_edit(edit_msg_content))
        btn_pub_n.clicked.connect(lambda: self.spawn_publisher_from_layout(topic_name, layout_topic_n, btn_config_n, edit_msg_content, edit_msg_type, v_layout_6_n))

    def spawn_publisher_from_layout(self, topic_name, layout_topic, btn_config, edit_msg_content, edit_msg_type, layout_v6):
        msg_type = edit_msg_type.text().strip() or "std_msgs/msg/String"
        msg_content = edit_msg_content.toPlainText().strip()
        self.spawn_publisher_for_topic(topic_name, layout_topic, btn_config, msg_type, msg_content)
        edit_msg_content.clear()
        self.set_layout_visible(layout_v6, False)

    def select_msg_file_for_edit(self, edit_widget):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, "Abrir archivo JSON", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    edit_widget.setPlainText(f.read())
            except Exception as e:
                pass

    def toggle_layout_8(self):
        is_visible = self.ui.EDITMSGContent.isVisible()
        self.set_layout_visible(self.ui.verticalLayout_8, not is_visible)

    def toggle_layout_6(self):
        is_visible = self.ui.EDITMSGContent_1.isVisible()
        self.set_layout_visible(self.ui.verticalLayout_6, not is_visible)

    def select_msg_file_0(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, "Abrir archivo JSON", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.ui.EDITMSGContent.setPlainText(content)
            except Exception as e:
                pass

    def select_msg_file_1(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, "Abrir archivo JSON", os.path.expanduser("~"), "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.ui.EDITMSGContent_1.setPlainText(content)
            except Exception as e:
                pass

    # --- COMPILER BACKEND GRPC HANDLERS ---

    def notify_user(self, title, msg, icon='dialog-information'):
        now = time.time()
        if hasattr(self, 'last_notify_time'):
            if now - self.last_notify_time < 0.5:
                return
        self.last_notify_time = now
        
        cmd = ['notify-send', '--app-name', 'RQTLL IDE', '--print-id', '--icon', icon, title, msg]
        if hasattr(self.ide.root, 'current_notify_id') and self.ide.root.current_notify_id:
            cmd.extend(['--replace-id', self.ide.root.current_notify_id.decode('utf-8').strip() if isinstance(self.ide.root.current_notify_id, bytes) else self.ide.root.current_notify_id.strip()])
            
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        self.ide.root.current_notify_id, _ = process.communicate()

    def on_btn_ros_colcon_clicked(self):
        ws_root = self.find_workspace_root()
        self.build_worker = BuildWorker(self.ide.root.build_stub, ws_root)
        
        def on_finished(success, message, nodes, launchers):
            if success:
                self.populate_nodes(nodes)
                self.populate_launchers(launchers)

        self.build_worker.finished_status.connect(on_finished)
        self.build_worker.start()

    def populate_nodes(self, nodes_list):
        for w in self.dynamic_node_widgets:
            w.deleteLater()
        self.dynamic_node_widgets.clear()

        for node_name in nodes_list:
            if "/" in node_name:
                pkg, exe = node_name.split("/", 1)
            else:
                pkg, exe = "unknown_package", node_name

            lbl = QLabel(exe)
            lbl.setStyleSheet(self.ui.LABELNode1.styleSheet())
            lbl.setFont(self.ui.LABELNode1.font())
            
            btn = QPushButton()
            btn.setIcon(self.ui.BTNNode_1.icon())
            btn.setFixedSize(self.ui.BTNNode_1.size())
            btn.setCursor(self.ui.BTNNode_1.cursor())
            
            btn.clicked.connect(lambda checked=False, p=pkg, e=exe, b=btn: self.toggle_node_execution(
                button=b,
                pkg=p,
                exe=e,
                use_launch=False
            ))
            
            row = self.ui.LAYOUTNodes.rowCount()
            self.ui.LAYOUTNodes.addWidget(lbl, row, 0)
            self.ui.LAYOUTNodes.addWidget(btn, row, 1)
            self.dynamic_node_widgets.extend([lbl, btn])

    def populate_launchers(self, launchers_list):
        for w in self.dynamic_launcher_widgets:
            w.deleteLater()
        self.dynamic_launcher_widgets.clear()

        for launch_name in launchers_list:
            if "/" in launch_name:
                pkg, exe = launch_name.split("/", 1)
            else:
                pkg, exe = "unknown_package", launch_name

            lbl = QLabel(exe)
            lbl.setStyleSheet(self.ui.LABELLaunch1.styleSheet())
            lbl.setFont(self.ui.LABELLaunch1.font())
            
            btn = QPushButton()
            btn.setIcon(self.ui.BTNLaunch_1.icon())
            btn.setFixedSize(self.ui.BTNLaunch_1.size())
            btn.setCursor(self.ui.BTNLaunch_1.cursor())
            
            btn.clicked.connect(lambda checked=False, p=pkg, e=exe, b=btn: self.toggle_node_execution(
                button=b,
                pkg=p,
                exe=e,
                use_launch=True
            ))
            
            row = self.ui.LAYOUTLanchers.rowCount()
            self.ui.LAYOUTLanchers.addWidget(lbl, row, 0)
            self.ui.LAYOUTLanchers.addWidget(btn, row, 1)
            self.dynamic_launcher_widgets.extend([lbl, btn])

    def toggle_node_execution(self, button, pkg, exe, use_launch=False):
        if not hasattr(self, 'active_node_workers'):
            self.active_node_workers = {}
        if button in self.active_node_workers:
            worker, tab_widget = self.active_node_workers[button]
            worker.cancel()
            worker.wait()
            del self.active_node_workers[button]
            if button in self.original_icons:
                button.setIcon(self.original_icons[button])
                del self.original_icons[button]
            self.close_tab_widget(tab_widget)
        else:
            self.original_icons[button] = button.icon()
            
            icon = QIcon()
            icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
            theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
            icon_path = _resolve_icon(icon_dirs, os.path.join('icons', 'close', 'default.svg'), theme=theme)
            icon.addFile(icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
            button.setIcon(icon)

            title = exe
            n = self.sub_counters.get(title, 0) + 1
            self.sub_counters[title] = n
            indexed_title = f"{title} [SUB {n}]"

            tab_widget = self.create_duplicate_tab(indexed_title, clone_label=False)
            text_edit = tab_widget.findChild(QTextEdit)
            if use_launch:
                text_edit.append(f"Starting ros2 launch {pkg} {exe}...\n")
                worker = NodeExecutionWorker(self.ide.root.node_execution_stub, pkg, "", use_launch=True, launch_file=exe)
            else:
                text_edit.append(f"Starting ros2 run {pkg} {exe}...\n")
                worker = NodeExecutionWorker(self.ide.root.node_execution_stub, pkg, exe)

            worker.log_received.connect(lambda log: self.append_log_to_edit(text_edit, log))
            
            def on_finished(success, message):
                self.append_log_to_edit(text_edit, f"\nProcess stopped: {message}\n")
                if button in self.active_node_workers:
                    del self.active_node_workers[button]
                if button in self.original_icons:
                    button.setIcon(self.original_icons[button])
                    del self.original_icons[button]

            worker.finished.connect(on_finished)
            self.active_node_workers[button] = (worker, tab_widget)
            worker.start()

    def on_btn_ros_clean_clicked(self):
        self.clean_worker = CleanWorker(self.ide.root.build_stub)
        
        def on_finished(success, message):
            if success:
                self.notify_user("RQTLL IDE", "El espacio de trabajo se ha limpiado correctamente.", "dialog-information")
            else:
                self.notify_user("RQTLL Error", f"Error al limpiar: {message}", "dialog-error")

        self.clean_worker.finished.connect(on_finished)
        self.clean_worker.start()

    def on_btn_ros_bag_clicked(self):
        btn = self.ui.BTNROSBag
        if self.is_recording_bag:
            if self.record_bag_worker:
                self.record_bag_worker.cancel()
                self.record_bag_worker.wait()
                self.record_bag_worker = None
            self.is_recording_bag = False
            if btn in self.original_icons:
                btn.setIcon(self.original_icons[btn])
                del self.original_icons[btn]
        else:
            self.is_recording_bag = True
            self.original_icons[btn] = btn.icon()
            
            icon = QIcon()
            icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
            theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
            icon_path = _resolve_icon(icon_dirs, os.path.join('icons', 'close', 'default.svg'), theme=theme)
            icon.addFile(icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
            btn.setIcon(icon)

            n = self.sub_counters.get("ros2 bag record", 0) + 1
            self.sub_counters["ros2 bag record"] = n
            title = f"ros2 bag record [SUB {n}]"

            tab_widget = self.create_duplicate_tab(title, clone_label=False)
            text_edit = tab_widget.findChild(QTextEdit)
            text_edit.append("Starting ros2 bag record...\n")

            out_path = self.ui.EDITROSPlay.text().strip()
            if out_path.startswith("~"):
                out_path = out_path.replace("~", os.path.expanduser("~"), 1)

            self.record_bag_worker = BagRecordWorker(self.ide.root.data_stream_stub, out_path)
            self.record_bag_worker.log_received.connect(lambda log: self.append_log_to_edit(text_edit, log))
            
            def on_finished(success, message):
                self.append_log_to_edit(text_edit, f"\nRecording stopped: {message}\n")
                self.is_recording_bag = False
                if btn in self.original_icons:
                    btn.setIcon(self.original_icons[btn])
                    del self.original_icons[btn]
                QTimer.singleShot(300000, lambda: self.close_tab_widget(tab_widget))

            self.record_bag_worker.finished.connect(on_finished)
            self.record_bag_worker.start()

    def on_btn_ros_play_clicked(self):
        btn = self.ui.BTNROSPlay
        if self.is_playing_bag:
            if self.play_bag_worker:
                self.play_bag_worker.cancel()
                self.play_bag_worker.wait()
                self.play_bag_worker = None
            self.is_playing_bag = False
            if btn in self.original_icons:
                btn.setIcon(self.original_icons[btn])
                del self.original_icons[btn]
        else:
            self.is_playing_bag = True
            self.original_icons[btn] = btn.icon()
            
            icon = QIcon()
            icon_dirs = getattr(self.window, '_initial_icon_dirs', self.ide.root.icon_dirs)
            theme = getattr(self.window, '_initial_theme', self.ide.root.theme)
            icon_path = _resolve_icon(icon_dirs, os.path.join('icons', 'close', 'default.svg'), theme=theme)
            icon.addFile(icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
            btn.setIcon(icon)

            n = self.sub_counters.get("ros2 bag play", 0) + 1
            self.sub_counters["ros2 bag play"] = n
            title = f"ros2 bag play [SUB {n}]"

            tab_widget = self.create_duplicate_tab(title, clone_label=False)
            text_edit = tab_widget.findChild(QTextEdit)
            text_edit.append("Starting ros2 bag play...\n")

            in_path = self.ui.EDITROSPlay.text().strip()
            if in_path.startswith("~"):
                in_path = in_path.replace("~", os.path.expanduser("~"), 1)

            self.play_bag_worker = BagPlayWorker(self.ide.root.data_stream_stub, in_path)
            self.play_bag_worker.log_received.connect(lambda log: self.append_log_to_edit(text_edit, log))
            
            def on_finished(success, message):
                self.append_log_to_edit(text_edit, f"\nPlayback stopped: {message}\n")
                self.is_playing_bag = False
                if btn in self.original_icons:
                    btn.setIcon(self.original_icons[btn])
                    del self.original_icons[btn]
                QTimer.singleShot(300000, lambda: self.close_tab_widget(tab_widget))

            self.play_bag_worker.finished.connect(on_finished)
            self.play_bag_worker.start()

    def close_tab_widget(self, widget):
        if widget:
            if hasattr(self, 'emulators') and widget in self.emulators:
                del self.emulators[widget]
            idx = self.ui.tabWidget.indexOf(widget)
            if idx != -1:
                self.ui.tabWidget.removeTab(idx)
                widget.deleteLater()

    def append_log_to_edit(self, text_edit, raw_text):
        try:
            if not hasattr(self, 'emulators'):
                self.emulators = {}
            if text_edit not in self.emulators:
                self.emulators[text_edit] = TerminalEmulator()
            self.emulators[text_edit].write(raw_text)
            text_edit.setHtml(self.emulators[text_edit].get_html())
            cursor = text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            text_edit.setTextCursor(cursor)
        except RuntimeError:
            pass

    def refresh_topics_list(self):
        self.list_topics_worker = ListTopicsWorker(self.ide.root.introspection_stub)
        
        def on_topics_received(topics):
            for t in topics:
                # Ignore parameter and rosout topics for a clean view
                if t['name'] in ["/parameter_events", "/rosout"]:
                    continue
                if t['name'] not in self.dynamic_topics:
                    self.create_dynamic_topic_layouts(t['name'])
                
                info = self.dynamic_topics[t['name']]
                info['edit_msg_type'].setText(t['type'])
                # If we have an active echo tab or pub tab, we can update label stats here too
                
        self.list_topics_worker.topics_received.connect(on_topics_received)
        self.list_topics_worker.start()
