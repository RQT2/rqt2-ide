import os
import re

from PySide6.QtCore import QObject, QThread, QTimer, Qt, QEvent, Signal, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QSizePolicy,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QGraphicsItem,
)
from PySide6.QtGui import QTextCursor
from PySide6.QtSvg import QSvgGenerator

try:
    from external.rqtll_widgets.utils.icon_loader import _resolve_icon
    from external.rqtll_widgets.utils.graph import BaseNode, NodeGraph
except Exception:
    try:
        from rqtll_widgets.utils.icon_loader import _resolve_icon
        from rqtll_widgets.utils.NodeGraphPySide import BaseNode, NodeGraph
    except Exception:
        def _resolve_icon(icon_dirs, path, theme=None):
            return path

import data_stream_pb2
import introspection_pb2
import types_pb2


class RosNode(BaseNode):
    __identifier__ = "rqtll.graph"
    NODE_NAME = "ROS Node"

    def __init__(self):
        super().__init__()
        self.set_color(0, 144, 255)
        self.text_color = (255, 255, 255, 230)
        self.create_property("rqtll_kind", "ros")
        self.create_property("rqtll_full_name", "")


class RosTopic(BaseNode):
    __identifier__ = "rqtll.graph"
    NODE_NAME = "ROS Topic"

    def __init__(self):
        super().__init__()
        self.set_color(6, 137, 137)
        self.text_color = (255, 255, 255, 230)
        self.create_property("rqtll_kind", "topic")
        self.create_property("rqtll_topic_name", "")
        self.create_property("rqtll_message_type", "unknown")


class GraphFetchWorker(QThread):
    graph_ready = Signal(object, object)
    error = Signal(str)

    def __init__(self, stub):
        super().__init__()
        self.stub = stub

    def run(self):
        try:
            graph_response = self.stub.GetGraph(types_pb2.Empty())
            topic_response = self.stub.ListTopics(types_pb2.Empty())
            self.graph_ready.emit(graph_response.nodes, topic_response.topics)
        except Exception as exc:
            self.error.emit(str(exc))


class TopicMetricsWorker(QThread):
    metrics_ready = Signal(str, str, str, str)
    error = Signal(str)

    def __init__(self, stub, topic_name):
        super().__init__()
        self.stub = stub
        self.topic_name = topic_name

    def run(self):
        try:
            request = introspection_pb2.TopicMetricsRequest(topic_name=self.topic_name)
            response = self.stub.GetTopicMetrics(request)
            self.metrics_ready.emit(
                self.topic_name,
                response.message_type or "unknown",
                response.hz or "Inactivo",
                response.bw or "---",
            )
        except Exception as exc:
            self.error.emit(str(exc))


class TopicSubscriptionWorker(QThread):
    message_received = Signal(object)

    def __init__(self, stub, topic_name, message_type):
        super().__init__()
        self.stub = stub
        self.topic_name = topic_name
        self.message_type = message_type
        self.stream = None
        self.running = True

    def run(self):
        try:
            request = data_stream_pb2.SubscribeRequest(
                topic=self.topic_name,
                message_type=self.message_type,
            )
            self.stream = self.stub.Subscribe(request)
            for response in self.stream:
                if not self.running:
                    break
                self.message_received.emit(response)
        except Exception:
            pass
        finally:
            self.cancel()

    def cancel(self):
        self.running = False
        if self.stream:
            try:
                self.stream.cancel()
            except Exception:
                pass


class DataViewerPanel(QFrame):
    def __init__(self, parent=None, theme_name="dark"):
        super().__init__(parent)
        self.theme_name = "dark" if "dark" in str(theme_name).lower() else "light"
        self.setObjectName("DataViewerPanel")
        self.setFixedWidth(200)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.title_label = QLabel("Tópico")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.body = QTextEdit(self)
        self.body.setReadOnly(True)
        self.body.setMinimumHeight(180)
        self.body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.body)

        self.load_palette()

    def load_palette(self):
        import json
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        palette_path = os.path.join(base_path, "external", "rqtll_components", "styles", "palette.json")

        bg_color = "#1e1e1e" if self.theme_name == "dark" else "#ffffff"
        text_color = "#ffffff" if self.theme_name == "dark" else "#000000"
        border_color = "#3e3e42" if self.theme_name == "dark" else "#cccccc"
        text_bg = "#121212" if self.theme_name == "dark" else "#f5f5f5"

        if os.path.exists(palette_path):
            try:
                with open(palette_path, "r") as f:
                    data = json.load(f)
                    theme_colors = data.get("themes", {}).get(self.theme_name, {})
                    if theme_colors:
                        bg_color = theme_colors.get("background", bg_color)
                        text_color = theme_colors.get("color", text_color)
                        border_color = theme_colors.get("disabled-color", border_color)
            except Exception:
                pass

        self.setStyleSheet(f"""
            QFrame#DataViewerPanel {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
                font-weight: bold;
                background: transparent;
                border: none;
            }}
            QTextEdit {{
                background-color: {text_bg};
                border-radius: 4px;
                color: {text_color};
            }}
        """)

    def set_message(self, title, body):
        lines = title.splitlines()
        topic_name = lines[0]
        if len(lines) > 1:
            msg_type = lines[1]
            short_type = msg_type.split("/")[-1] if "/" in msg_type else msg_type
            self.title_label.setText(f"{topic_name}\n{short_type}")
        else:
            self.title_label.setText(topic_name)

        self.body.setPlainText(body)
        self.body.moveCursor(QTextCursor.MoveOperation.Start)


class GraphControlsPanel(QFrame):
    def __init__(self, parent=None, icon_dirs=None, theme=None):
        super().__init__(parent)
        self.icon_dirs = icon_dirs or []
        self.theme = theme
        self.theme_name = "dark" if "dark" in str(theme).lower() else "light"
        self.setObjectName("GraphControlsPanel")
        self.setFixedHeight(38)
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.save_button = QPushButton(self)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setFixedSize(26, 26)

        self.center_button = QPushButton(self)
        self.center_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.center_button.setFixedSize(26, 26)

        layout.addWidget(self.save_button)
        layout.addWidget(self.center_button)
        self.load_palette()

    def load_palette(self):
        import json
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        palette_path = os.path.join(base_path, "external", "rqtll_components", "styles", "palette.json")

        bg_color = "#1e1e1e" if self.theme_name == "dark" else "#ffffff"
        border_color = "#3e3e42" if self.theme_name == "dark" else "#cccccc"
        hover_bg = "#2e2e2e" if self.theme_name == "dark" else "#e1e1e1"

        if os.path.exists(palette_path):
            try:
                with open(palette_path, "r") as f:
                    data = json.load(f)
                    theme_colors = data.get("themes", {}).get(self.theme_name, {})
                    if theme_colors:
                        bg_color = theme_colors.get("background", bg_color)
                        border_color = theme_colors.get("disabled-color", border_color)
            except Exception:
                pass

        self.setStyleSheet(f"""
            QFrame#GraphControlsPanel {{
                background-color: {bg_color};
                border-radius: 6px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """)

    def set_icons(self):
        save_icon = _resolve_icon(self.icon_dirs, os.path.join("icons", "folder", "default.svg"), theme=self.theme)
        center_icon = _resolve_icon(self.icon_dirs, os.path.join("icons", "maximize", "click.svg"), theme=self.theme)
        self.save_button.setIcon(_icon_from_path(save_icon))
        self.center_button.setIcon(_icon_from_path(center_icon))


def _icon_from_path(path):
    from PySide6.QtGui import QIcon

    icon = QIcon()
    if path:
        icon.addFile(path)
    return icon


class NodesVisualizerController(QObject):
    def __init__(self, ide_controller):
        super().__init__()
        self.ide = ide_controller
        self.window = None
        self.ui = None
        self.graph = None
        self.graph_widget = None
        self.overlay = None
        self.graph_worker = None
        self.metrics_workers = {}
        self.subscription_worker = None
        self.graph_generation = 0
        self.saved_positions = {}
        self.topic_nodes = {}
        self.ros_nodes = {}
        self.node_metadata = {}
        self.active_topic_name = None
        self.active_topic_type = None
        self.bound_frame = None
        self.controls_panel = None
        self.viewer = None
        self._initial_center_pending = False
        self.metrics = {
			"message_type": "unknown",
			"hz": "Inactivo",
			"bw": "---"
		}
        self.topic_metrics_cache = {}

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2500)
        self.refresh_timer.timeout.connect(self.update_graph)

    def bind(self, window):
        self.window = window
        self.ui = window.ui

        if self.graph is None:
            self.graph = NodeGraph()
            self.graph.theme_name = "dark" if "dark" in str(getattr(self.ide.root, "theme", "dark")).lower() else "light"
            self.graph.register_nodes([RosNode, RosTopic])
            self.graph.node_selected.connect(self.on_node_selected)

        self.viewer = self.graph.viewer()
        self._disable_graph_connection_editing()
        try:
            self.viewer.moved_nodes.connect(self._on_nodes_moved)
        except Exception:
            pass

        try:
            from external.rqtll_widgets.utils.theme_manager import get_theme_manager
        except ImportError:
            try:
                from rqtll_widgets.utils.theme_manager import get_theme_manager
            except ImportError:
                def get_theme_manager():
                    return None
        _theme_manager = get_theme_manager()
        if _theme_manager:
            try:
                _theme_manager.themeChanged.disconnect(self.update_theme)
            except Exception:
                pass
            _theme_manager.themeChanged.connect(self.update_theme)

        self.graph_widget = self.graph.widget
        self.graph_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        frame_layout = self.ui.frame.layout()
        if frame_layout is None:
            frame_layout = QVBoxLayout(self.ui.frame)
            frame_layout.setContentsMargins(0, 0, 0, 0)
            frame_layout.setSpacing(0)

        if frame_layout.indexOf(self.graph_widget) == -1:
            frame_layout.addWidget(self.graph_widget)

        self.graph_widget.show()

        if self.controls_panel is None:
            self.controls_panel = GraphControlsPanel(
                self.ui.frame,
                icon_dirs=getattr(self.ide.root, "icon_dirs", []),
                theme=getattr(self.ide.root, "theme", None),
            )
            self.controls_panel.set_icons()
            self.controls_panel.save_button.clicked.connect(self.save_graph_image)
            self.controls_panel.center_button.clicked.connect(self.center_graph)
        else:
            self.controls_panel.setParent(self.ui.frame)

        if self.overlay is None:
            self.overlay = DataViewerPanel(self.ui.frame, theme_name=getattr(self.ide.root, "theme", "dark"))
        else:
            self.overlay.setParent(self.ui.frame)

        if self.bound_frame is not self.ui.frame:
            if self.bound_frame is not None:
                self.bound_frame.removeEventFilter(self)
            self.bound_frame = self.ui.frame
            self.bound_frame.installEventFilter(self)

        self._position_controls()
        self._position_overlay()

        self.controls_panel.show()
        self.controls_panel.raise_()
        self.overlay.show()
        self.overlay.raise_()

        self.window.destroyed.connect(self.cleanup)
        self.refresh_timer.start()
        self.update_graph()

    def update_theme(self, theme_name):
        theme_str = "dark" if "dark" in theme_name.lower() else "light"
        if self.graph:
            self.graph.theme_name = theme_str
        if self.controls_panel:
            self.controls_panel.theme_name = theme_str
            self.controls_panel.theme = theme_name
            self.controls_panel.load_palette()
            self.controls_panel.set_icons()
        if self.overlay:
            self.overlay.theme_name = theme_str
            self.overlay.load_palette()

    def eventFilter(self, obj, event):
        if obj is self.bound_frame and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._position_controls()
            self._position_overlay()
        return super().eventFilter(obj, event)

    def on_show(self):
        self.refresh_timer.start()
        self._position_controls()
        self._position_overlay()
        self.update_graph()

    def on_hide(self):
        self.refresh_timer.stop()
        self._stop_subscription()
        if self.overlay:
            self.overlay.hide()

    def cleanup(self):
        self.refresh_timer.stop()
        self._stop_subscription()
        for worker in list(self.metrics_workers.values()):
            try:
                worker.wait(1500)
            except Exception:
                pass
        self.metrics_workers.clear()
        if self.graph_worker and self.graph_worker.isRunning():
            try:
                self.graph_worker.wait(1500)
            except Exception:
                pass

    def update_graph(self):
        if self.graph is None or (self.graph_worker and self.graph_worker.isRunning()):
            return

        self.graph_generation += 1
        generation = self.graph_generation
        self.graph_worker = GraphFetchWorker(self.ide.root.introspection_stub)
        self.graph_worker.graph_ready.connect(lambda nodes, topics: self._apply_graph(nodes, topics, generation))
        self.graph_worker.error.connect(lambda error: self._show_error(error, generation))
        self.graph_worker.start()

    def _apply_graph(self, nodes, topics, generation):
        if generation != self.graph_generation or self.graph is None:
            return

        self._cancel_metric_workers()
        self.graph.clear_session()
        self.topic_nodes = {}
        self.ros_nodes = {}
        self.node_metadata = {}
        self.viewer = self.graph.viewer()
        self._disable_graph_connection_editing()
        try:
            self.viewer.moved_nodes.connect(self._on_nodes_moved)
        except Exception:
            pass

        topic_names = set()
        topic_types = {}

        for topic in topics or []:
            topic_name = (topic.name or "").strip()
            if topic_name:
                topic_names.add(topic_name)
                topic_types[topic_name] = topic.message_type or "unknown"

        for node_ext in nodes:
            node_info = node_ext.node
            if node_info is None:
                continue

            full_name = self._full_node_name(node_info)
            node_key = self._node_key("ros", full_name)
            ros_node = self.graph.create_node(
                RosNode.type_,
                name=full_name,
                selected=False,
                color="#0090ff",
                text_color="#f0f7ff",
            )
            ros_node.set_name(full_name)
            ros_node.model.set_property("rqtll_kind", "ros")
            ros_node.model.set_property("rqtll_full_name", full_name)

            pub_ports = {}
            sub_ports = {}
            for topic_name in sorted(set(node_ext.publications)):
                pub_ports[topic_name] = ros_node.add_output(topic_name, multi_output=True)
                topic_names.add(topic_name)
            for topic_name in sorted(set(node_ext.subscriptions)):
                sub_ports[topic_name] = ros_node.add_input(topic_name, multi_input=True)
                topic_names.add(topic_name)

            self.ros_nodes[full_name] = {
                "node": ros_node,
                "publications": pub_ports,
                "subscriptions": sub_ports,
                "key": node_key,
            }
            self.node_metadata[ros_node.id] = {"kind": "ros", "name": full_name, "key": node_key}

        for topic_name in sorted(topic_names):
            topic_key = self._node_key("topic", topic_name)
            
            msg_type = topic_types.get(topic_name) or "unknown"
            
            cached = self.topic_metrics_cache.get(topic_name)
            if cached:
                if not cached.get("message_type") or cached.get("message_type") == "unknown":
                    cached["message_type"] = msg_type
                else:
                    msg_type = cached.get("message_type")
                hz = cached.get("hz") or "Inactivo"
                bw = cached.get("bw") or "---"
            else:
                hz = "Inactivo"
                bw = "---"
                self.topic_metrics_cache[topic_name] = {
                    "message_type": msg_type,
                    "hz": hz,
                    "bw": bw
                }
            label = f"{topic_name}\n{msg_type}"

            topic_node = self.graph.create_node(
                RosTopic.type_,
                name=label,
                selected=False,
                color="#068989",
                text_color="#f4ffff",
            )
            topic_node.set_name(label)
            topic_node.model.set_property("rqtll_kind", "topic")
            topic_node.model.set_property("rqtll_topic_name", topic_name)
            topic_node.model.set_property("rqtll_message_type", msg_type)

            publishers_port = topic_node.add_input("publishers", multi_input=True)
            subscribers_port = topic_node.add_output("subscribers", multi_output=True)

            self.topic_nodes[topic_name] = {
                "node": topic_node,
                "publishers": publishers_port,
                "subscribers": subscribers_port,
                "message_type": msg_type,
                "hz": hz,
                "bw": bw,
                "key": topic_key,
            }
            self.node_metadata[topic_node.id] = {"kind": "topic", "name": topic_name, "key": topic_key}
            self._start_metric_worker(topic_name, generation)

        for node_ext in nodes:
            node_info = node_ext.node
            if node_info is None:
                continue

            full_name = self._full_node_name(node_info)
            ros_entry = self.ros_nodes.get(full_name)
            if ros_entry is None:
                continue

            for topic_name, output_port in ros_entry["publications"].items():
                topic_entry = self.topic_nodes.get(topic_name)
                if topic_entry is not None:
                    output_port.connect_to(topic_entry["publishers"])

            for topic_name, input_port in ros_entry["subscriptions"].items():
                topic_entry = self.topic_nodes.get(topic_name)
                if topic_entry is not None:
                    topic_entry["subscribers"].connect_to(input_port)

        self._restore_node_positions()
        if self._initial_center_pending:
            try:
                self.center_graph()
            finally:
                self._initial_center_pending = False

        if self.active_topic_name and self.active_topic_name not in self.topic_nodes:
            self._stop_subscription()

        self._position_controls()
        self._position_overlay()

    def _start_metric_worker(self, topic_name, generation):
        worker = TopicMetricsWorker(self.ide.root.introspection_stub, topic_name)
        worker.metrics_ready.connect(
            lambda name, message_type, hz, bw: self._apply_topic_metrics(name, message_type, hz, bw, generation)
        )
        worker.error.connect(lambda error: self._show_metric_error(topic_name, error, generation))
        worker.finished.connect(lambda w=worker, name=topic_name: self._clear_metric_worker(name, w))
        self.metrics_workers[topic_name] = worker
        worker.start()

    def _apply_topic_metrics(self, topic_name, message_type, hz, bw, generation):
        if generation != self.graph_generation:
            return

        cached = self.topic_metrics_cache.get(topic_name) or {}
        final_message_type = message_type
        if not final_message_type or final_message_type == "unknown":
            final_message_type = cached.get("message_type") or "unknown"

        # Hysteresis / value smoothing for hz metric
        final_hz = hz or "Inactivo"
        inactive_hz_count = cached.get("inactive_hz_count", 0)
        
        if final_hz == "Inactivo":
            last_valid_hz = cached.get("last_valid_hz")
            if last_valid_hz and inactive_hz_count < 3:
                final_hz = last_valid_hz
                inactive_hz_count += 1
            else:
                final_hz = "Inactivo"
                inactive_hz_count = 0
        else:
            inactive_hz_count = 0
            cached["last_valid_hz"] = final_hz

        # Hysteresis / value smoothing for bw metric
        final_bw = bw or "---"
        inactive_bw_count = cached.get("inactive_bw_count", 0)
        
        if final_bw == "---":
            last_valid_bw = cached.get("last_valid_bw")
            if last_valid_bw and inactive_bw_count < 3:
                final_bw = last_valid_bw
                inactive_bw_count += 1
            else:
                final_bw = "---"
                inactive_bw_count = 0
        else:
            inactive_bw_count = 0
            cached["last_valid_bw"] = final_bw

        self.topic_metrics_cache[topic_name] = {
            "message_type": final_message_type,
            "hz": final_hz,
            "bw": final_bw,
            "last_valid_hz": cached.get("last_valid_hz"),
            "last_valid_bw": cached.get("last_valid_bw"),
            "inactive_hz_count": inactive_hz_count,
            "inactive_bw_count": inactive_bw_count,
        }

        entry = self.topic_nodes.get(topic_name)
        if entry is None:
            return

        entry["message_type"] = final_message_type
        entry["hz"] = final_hz
        entry["bw"] = final_bw

        node = entry["node"]
        label = f"{topic_name}\n{final_message_type}"
        node.set_name(label)
        node.model.set_property("rqtll_message_type", final_message_type)
        self._persist_node_position(entry["key"], node)

    def _show_error(self, error, generation):
        if generation != self.graph_generation:
            return
        if self.overlay:
            self.overlay.set_message("Grafo de ROS 2", f"No se pudo actualizar el grafo:\n{error}")

    def _show_metric_error(self, topic_name, error, generation):
        if generation != self.graph_generation:
            return
        entry = self.topic_nodes.get(topic_name)
        if entry is None:
            return
        entry["message_type"] = entry.get("message_type") or "unknown"
        entry["hz"] = entry.get("hz") or "Inactivo"
        entry["bw"] = entry.get("bw") or "---"

    def on_node_selected(self, node):
        if node is None:
            return

        metadata = self.node_metadata.get(node.id, {})
        if metadata.get("kind") != "topic":
            return

        topic_name = metadata.get("name", node.name())
        topic_entry = self.topic_nodes.get(topic_name)
        if topic_entry is None:
            return

        self._stop_subscription()
        self.active_topic_name = topic_name
        self.active_topic_type = topic_entry.get("message_type") or "unknown"

        if self.overlay:
            title = topic_name
            if self.active_topic_type and self.active_topic_type != "unknown":
                title = f"{title}\n{self.active_topic_type}"
            self.overlay.set_message(title, "Esperando datos...")
            self._position_overlay()

        self.subscription_worker = TopicSubscriptionWorker(
            self.ide.root.data_stream_stub,
            topic_name,
            self.active_topic_type,
        )
        self.subscription_worker.message_received.connect(
            lambda response: self._handle_topic_message(topic_name, response)
        )
        self.subscription_worker.start()

    def _handle_topic_message(self, topic_name, response):
        message_type = getattr(response, "message_type", None) or self.active_topic_type or "unknown"
        payload = getattr(response, "data", b"") or b""
        meta = getattr(response, "meta", {}) or {}
        text = meta.get("echo", "")
        
        if not text and not payload:
            return

        if not text and payload:
            try:
                text = payload.decode("utf-8", errors="replace")
            except Exception:
                text = ""

        formatted = self._format_message(message_type, text, payload)
        title = f"{topic_name}"
        if message_type and message_type != "unknown":
            title = f"{title}\n{message_type}"

        if self.overlay:
            self.overlay.set_message(title, formatted)
            self._position_overlay()

    def _node_key(self, kind, name):
        return f"{kind}:{name}"

    def _disable_graph_connection_editing(self):
        if self.viewer is None:
            return

        self.viewer.pipe_slicing = False

        def _noop(*args, **kwargs):
            return None

        self.viewer.start_live_connection = _noop
        self.viewer.apply_live_connection = _noop
        self.viewer.end_live_connection = _noop
        self.viewer._on_pipes_sliced = _noop

    def _persist_node_position(self, key, node):
        try:
            x, y = node.pos()
            self.saved_positions[key] = [float(x), float(y)]
        except Exception:
            pass

    def _on_node_created(self, node):
        metadata = self.node_metadata.get(node.id)
        if not metadata:
            return
        key = metadata.get("key")
        if not key:
            return
        self._place_node(node, key)

    def _on_nodes_deleted(self, node_ids):
        for node_id in node_ids or []:
            metadata = self.node_metadata.pop(node_id, None)
            if metadata and metadata.get("kind") == "topic":
                topic_name = metadata.get("name")
                if topic_name == self.active_topic_name:
                    self._stop_subscription()

    def _restore_node_positions(self):
        occupied = []
        ordered_items = []

        for key, entry in self.ros_nodes.items():
            ordered_items.append((entry["key"], entry["node"], "ros"))
        for key, entry in self.topic_nodes.items():
            ordered_items.append((entry["key"], entry["node"], "topic"))

        ordered_items.sort(key=lambda item: (0 if item[2] == "ros" else 1, item[0]))

        for key, node, kind in ordered_items:
            self._place_node(node, key, kind=kind, occupied=occupied)

    def _place_node(self, node, key, kind=None, occupied=None):
        occupied = occupied if occupied is not None else []
        kind = kind or (self.node_metadata.get(node.id, {}) or {}).get("kind", "topic")

        preferred = self.saved_positions.get(key)
        width = max(220.0, float(getattr(node.view, "width", 260.0) or 260.0))
        height = max(120.0, float(getattr(node.view, "height", 120.0) or 120.0))
        size = (width, height)

        if preferred is None:
            preferred = self._initial_position_for(kind, len(occupied))

        candidate = self._find_free_position(tuple(preferred), size, occupied)
        node.set_pos(candidate[0], candidate[1])
        self.saved_positions[key] = [float(candidate[0]), float(candidate[1])]
        occupied.append(QRectF(candidate[0], candidate[1], width, height))

    def _initial_position_for(self, kind, index):
        column = 0 if kind == "ros" else 1
        x = 80 + (column * 420)
        y = 60 + (index * 150)
        return [float(x), float(y)]

    def _find_free_position(self, preferred, size, occupied):
        width, height = size
        step_x = 260.0
        step_y = 160.0
        max_radius = 8
        for radius in range(max_radius + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    candidate_x = preferred[0] + (dx * step_x)
                    candidate_y = preferred[1] + (dy * step_y)
                    candidate_rect = QRectF(candidate_x, candidate_y, width, height)
                    if not any(candidate_rect.intersects(rect) for rect in occupied):
                        return candidate_x, candidate_y
        return preferred

    def _persist_positions_from_viewer(self, moved_nodes):
        for node_view, _prev_pos in (moved_nodes or {}).items():
            metadata = self.node_metadata.get(node_view.id)
            if not metadata:
                continue
            key = metadata.get("key")
            if not key:
                continue
            try:
                current_pos = getattr(node_view, "xy_pos", None)
                if current_pos is None:
                    current_pos = self.graph.get_node_by_id(node_view.id).pos()
                self.saved_positions[key] = [float(current_pos[0]), float(current_pos[1])]
            except Exception:
                pass

    def _on_nodes_moved(self, moved_nodes):
        self._persist_positions_from_viewer(moved_nodes)

    def _position_controls(self):
        if self.controls_panel is None or self.bound_frame is None:
            return

        self.controls_panel.adjustSize()
        margin = 2
        x = margin
        y = margin
        self.controls_panel.move(x, y)
        self.controls_panel.show()
        self.controls_panel.raise_()

    def _format_message(self, message_type, text, payload):
        message_type_lower = (message_type or "").lower()

        cleaned = text.strip()
        if cleaned:
            return cleaned

        return f"[{message_type}] {len(payload)} bytes"

    def _extract_value(self, text, key_name):
        pattern = rf"{re.escape(key_name)}\s*:\s*([^\n]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _full_node_name(self, node_info):
        namespace = (node_info.namespace or "").strip()
        name = (node_info.name or "").strip().lstrip("/")
        if not namespace or namespace == "/":
            return f"/{name}"
        return f"/{namespace.strip('/').strip()}/{name}"

    def _cancel_metric_workers(self):
        self.metrics_workers.clear()

    def _clear_metric_worker(self, topic_name, worker):
        current_worker = self.metrics_workers.get(topic_name)
        if current_worker is worker:
            self.metrics_workers.pop(topic_name, None)

    def _stop_subscription(self):
        if self.subscription_worker is not None:
            try:
                self.subscription_worker.cancel()
                self.subscription_worker.wait(1500)
            except Exception:
                pass
            self.subscription_worker = None
        self.active_topic_name = None
        self.active_topic_type = None
        if self.overlay:
            self.overlay.set_message("Tópico", "")

    def _position_overlay(self):
        if self.overlay is None or self.bound_frame is None:
            return

        margin = 2
        width = 240
        self.overlay.setFixedWidth(width)
        self.overlay.adjustSize()
        overlay_height = max(350, self.bound_frame.height() - 2 * margin)
        self.overlay.setFixedHeight(overlay_height)

        x = max(margin, self.bound_frame.width() - width - margin)
        y = margin
        self.overlay.move(x, y)
        self.overlay.show()
        self.overlay.raise_()

    def center_graph(self):
        if self.graph is None:
            return
        try:
            self.graph.center_on(self.graph.all_nodes(), padding=160)
        except Exception:
            pass

    def save_graph_image(self):
        if self.graph is None or self.viewer is None:
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.window,
            "Guardar vista del grafo",
            os.path.expanduser("~/graph.png"),
            "PNG (*.png);;SVG (*.svg);;JPEG (*.jpg *.jpeg)",
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        if not ext:
            if "svg" in selected_filter.lower():
                file_path += ".svg"
                ext = ".svg"
            elif "jpg" in selected_filter.lower() or "jpeg" in selected_filter.lower():
                file_path += ".jpg"
                ext = ".jpg"
            else:
                file_path += ".png"
                ext = ".png"

        # Temporarily disable caching for all items in the scene to output vector representations
        saved_caches = {}
        scene = self.viewer.scene() if self.viewer else None
        if scene:
            for item in scene.items():
                orig_cache = item.cacheMode()
                if orig_cache != QGraphicsItem.CacheMode.NoCache:
                    saved_caches[item] = orig_cache
                    item.setCacheMode(QGraphicsItem.CacheMode.NoCache)

        try:
            if ext == ".svg":
                generator = QSvgGenerator()
                generator.setFileName(file_path)
                generator.setSize(self.viewer.viewport().size())
                generator.setViewBox(self.viewer.viewport().rect())
                generator.setTitle("RQTLL graph view")
                painter = QPainter(generator)
                self.viewer.render(painter)
                painter.end()
            else:
                image = QImage(self.viewer.viewport().size(), QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.transparent)
                painter = QPainter(image)
                self.viewer.render(painter)
                painter.end()
                image_format = "PNG" if ext == ".png" else "JPG"
                image.save(file_path, image_format)
        except Exception as exc:
            if self.overlay:
                self.overlay.set_message("Exportar grafo", f"No se pudo guardar la imagen:\n{exc}")
        finally:
            # Restore original cache modes
            for item, orig_cache in saved_caches.items():
                try:
                    item.setCacheMode(orig_cache)
                except Exception:
                    pass
