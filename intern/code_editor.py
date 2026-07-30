import os
import codecs
import subprocess
from PySide6.QtCore import QObject, Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import QTreeWidgetItem, QStyle, QWidget, QVBoxLayout, QTextEdit, QMessageBox, QFileDialog
from PySide6.QtGui import QIcon, QTextCursor, QKeySequence, QShortcut, QFont
import file_system_pb2
import terminal_pb2
import types_pb2
from .compiler import TerminalEmulator

class FileTreeLoaderThread(QThread):
    files_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, stub, path):
        super().__init__()
        self.stub = stub
        self.path = path

    def run(self):
        try:
            req = file_system_pb2.PathRequest(path=self.path, recursive=False)
            res = self.stub.List(req)
            self.files_loaded.emit(list(res.entries))
        except Exception as e:
            self.error_occurred.emit(str(e))

class FolderLoaderThread(QThread):
    folder_loaded = Signal(list, object)
    error_occurred = Signal(str, object)

    def __init__(self, stub, path, item):
        super().__init__()
        self.stub = stub
        self.path = path
        self.item = item

    def run(self):
        try:
            req = file_system_pb2.PathRequest(path=self.path, recursive=False)
            res = self.stub.List(req)
            self.folder_loaded.emit(list(res.entries), self.item)
        except Exception as e:
            self.error_occurred.emit(str(e), self.item)

class TerminalOutputThread(QThread):
    output_received = Signal(str)
    session_finished = Signal()

    def __init__(self, stub, session_id):
        super().__init__()
        self.stub = stub
        self.session_id = session_id
        self.is_running = True

    def run(self):
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        try:
            req = terminal_pb2.AttachRequest(session_id=self.session_id)
            response_stream = self.stub.Attach(req)
            for output in response_stream:
                if not self.is_running:
                    break
                text = decoder.decode(output.data, final=False)
                self.output_received.emit(text)
        except Exception as e:
            print(f"Error in terminal output thread: {e}")
        finally:
            self.session_finished.emit()

    def stop(self):
        self.is_running = False

class TerminalStarterThread(QThread):
    started = Signal(str)
    error = Signal(str)

    def __init__(self, stub, cwd):
        super().__init__()
        self.stub = stub
        self.cwd = cwd

    def run(self):
        try:
            req = terminal_pb2.StartTerminalRequest(cwd=self.cwd)
            res = self.stub.Start(req)
            self.started.emit(res.session_id)
        except Exception as e:
            self.error.emit(str(e))

class ROSIntrospectionThread(QThread):
    counts_updated = Signal(int, int)

    def __init__(self, stub):
        super().__init__()
        self.stub = stub
        self.is_running = True

    def run(self):
        empty_req = types_pb2.Empty()
        while self.is_running:
            try:
                res_nodes = self.stub.ListNodes(empty_req)
                nodes_count = len(res_nodes.nodes)
                
                res_topics = self.stub.ListTopics(empty_req)
                topics_count = len(res_topics.topics)
                
                self.counts_updated.emit(nodes_count, topics_count)
            except Exception as e:
                print(f"Error in ROSIntrospectionThread: {e}")
                
            for _ in range(30):
                if not self.is_running:
                    break
                self.msleep(100)

    def stop(self):
        self.is_running = False

class CodeEditorController(QObject):
    def __init__(self, ide_controller):
        super().__init__()
        self.ide = ide_controller
        self.loader_thread = None
        self.output_thread = None
        self.introspection_thread = None
        self.session_id = None
        self.starter_thread = None
        self.active_threads = []
        self.shortcuts = []

    def bind(self, window):
        self.window = window
        self.ui = window.ui
        
        # Connect file explorer events
        self.ui.TREEFILEManage.itemExpanded.connect(self.on_item_expanded)
        self.ui.TREEFILEManage.clicked.connect(self.on_item_clicked)
        
        # Setup code tabs
        self.ui.TABCODETabs.clear()
        self.ui.TABCODETabs.tabCloseRequested.connect(self.close_code_tab)

        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Load file explorer
        self.load_file_tree()
        
        # Setup local terminal emulator
        self.setup_terminal()
        self.start_terminal_session()

        # Update project path label and count ROS nodes/topics
        self.update_path_label()
        self.start_introspection()
        
        # Clean up PTY process on window close/destruction
        self.window.destroyed.connect(self.cleanup)

    def load_file_tree(self):
        root_path = self.ide.ws_path
        if not root_path:
            return

        self.ui.TREEFILEManage.clear()
        self.ui.TREEFILEManage.setHeaderLabels(["Cargando archivos..."])

        self.loader_thread = FileTreeLoaderThread(self.ide.root.file_stub, root_path)
        self.loader_thread.files_loaded.connect(self.populate_tree)
        self.loader_thread.error_occurred.connect(self.on_load_error)
        self.loader_thread.start()

    def populate_tree(self, entries):
        try:
            root_path = self.ide.ws_path
            self.ui.TREEFILEManage.clear()
            self.ui.TREEFILEManage.setHeaderLabels(["Archivos"])

            sorted_entries = sorted(entries, key=lambda e: (not e.is_dir, e.path))

            dir_icon = self.window.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            file_icon = self.window.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)

            for entry in sorted_entries:
                path = entry.path
                if path == root_path:
                    continue

                new_item = QTreeWidgetItem(self.ui.TREEFILEManage)
                new_item.setText(0, os.path.basename(path))
                new_item.setData(0, Qt.ItemDataRole.UserRole, path)

                if entry.is_dir:
                    new_item.setIcon(0, dir_icon)
                    new_item.setData(0, Qt.ItemDataRole.UserRole + 1, False) # is_loaded = False
                    
                    dummy = QTreeWidgetItem(new_item)
                    dummy.setText(0, "Cargando...")
                else:
                    new_item.setIcon(0, file_icon)

        except Exception as e:
            print(f"Error populating root tree: {e}")

    def on_load_error(self, err_msg):
        self.ui.TREEFILEManage.clear()
        self.ui.TREEFILEManage.setHeaderLabels([f"Error al cargar: {err_msg}"])

    def on_item_expanded(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        is_loaded = item.data(0, Qt.ItemDataRole.UserRole + 1)

        if path and not is_loaded:
            item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
            
            while item.childCount() > 0:
                item.removeChild(item.child(0))

            loading_item = QTreeWidgetItem(item)
            loading_item.setText(0, "Cargando...")

            thread = FolderLoaderThread(self.ide.root.file_stub, path, item)
            thread.folder_loaded.connect(self.on_folder_loaded)
            thread.error_occurred.connect(self.on_folder_load_error)
            
            self.active_threads.append(thread)
            thread.finished.connect(lambda t=thread: self.active_threads.remove(t) if t in self.active_threads else None)
            thread.start()

    def on_folder_loaded(self, entries, item):
        try:
            while item.childCount() > 0:
                item.removeChild(item.child(0))

            sorted_entries = sorted(entries, key=lambda e: (not e.is_dir, e.path))

            dir_icon = self.window.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            file_icon = self.window.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)

            for entry in sorted_entries:
                child_item = QTreeWidgetItem(item)
                child_item.setText(0, os.path.basename(entry.path))
                child_item.setData(0, Qt.ItemDataRole.UserRole, entry.path)

                if entry.is_dir:
                    child_item.setIcon(0, dir_icon)
                    child_item.setData(0, Qt.ItemDataRole.UserRole + 1, False) # is_loaded = False
                    
                    dummy = QTreeWidgetItem(child_item)
                    dummy.setText(0, "Cargando...")
                else:
                    child_item.setIcon(0, file_icon)

        except Exception as e:
            print(f"Error populating expanded folder: {e}")

    def on_folder_load_error(self, err_msg, item):
        while item.childCount() > 0:
            item.removeChild(item.child(0))
        err_item = QTreeWidgetItem(item)
        err_item.setText(0, f"Error: {err_msg}")

    # --- STATUS BAR PATH & INTROSPECTION ---

    def update_path_label(self):
        path = self.ide.ws_path
        if not path:
            self.ui.statusdir.setText("")
            return

        home = os.environ.get("HOME", "")
        if home and path.startswith(home):
            display_path = "~" + path[len(home):]
        else:
            display_path = path
        self.ui.statusdir.setText(display_path)

    def start_introspection(self):
        self.introspection_thread = ROSIntrospectionThread(self.ide.root.introspection_stub)
        self.introspection_thread.counts_updated.connect(self.update_topics_count)
        self.introspection_thread.start()

    def update_topics_count(self, nodes_count, topics_count):
        self.ui.statustopics.setText(f"Nodos: {nodes_count} / Tópicos: {topics_count}")

    # --- TEXT EDITOR TABS & ACTIONS ---

    def setup_shortcuts(self):
        self.shortcuts.clear()

        # Ctrl+N (New File)
        s_new = QShortcut(QKeySequence("Ctrl+N"), self.window)
        s_new.activated.connect(self.new_file)
        self.shortcuts.append(s_new)

        # Ctrl+S (Save File)
        s_save = QShortcut(QKeySequence("Ctrl+S"), self.window)
        s_save.activated.connect(self.save_current_file)
        self.shortcuts.append(s_save)

        # Ctrl+Shift+S (Save As)
        s_save_as = QShortcut(QKeySequence("Ctrl+Shift+S"), self.window)
        s_save_as.activated.connect(self.save_current_file_as)
        self.shortcuts.append(s_save_as)

        # Ctrl+O (Open File)
        s_open = QShortcut(QKeySequence("Ctrl+O"), self.window)
        s_open.activated.connect(self.open_file_dialog)
        self.shortcuts.append(s_open)

        # Ctrl+W (Close Tab)
        s_close = QShortcut(QKeySequence("Ctrl+W"), self.window)
        s_close.activated.connect(self.close_current_tab)
        self.shortcuts.append(s_close)

    def on_item_clicked(self, index):
        item = self.ui.TREEFILEManage.itemFromIndex(index)
        if not item:
            return
            
        path = item.data(0, Qt.ItemDataRole.UserRole)
        is_dir = item.data(0, Qt.ItemDataRole.UserRole + 1) is not None
        
        if is_dir:
            item.setExpanded(not item.isExpanded())
        elif path:
            self.open_file_in_tab(path)

    def open_file_in_tab(self, path):
        # Check if already open in a tab
        for i in range(self.ui.TABCODETabs.count()):
            widget = self.ui.TABCODETabs.widget(i)
            if hasattr(widget, "file_path") and widget.file_path == path:
                if self.ui.TABCODETabs.currentIndex() == i:
                    self.close_code_tab(i)
                else:
                    self.ui.TABCODETabs.setCurrentIndex(i)
                return

        # Load file content
        try:
            req = file_system_pb2.ReadFileRequest(path=path)
            res = self.ide.root.file_stub.Read(req)
            
            if not res.status.ok:
                print(f"Error reading file: {res.status.message}")
                return
                
            if res.is_binary:
                content_str = "[Archivo binario no editable]"
            else:
                content_str = res.content.decode('utf-8', errors='replace')
                
            self.create_tab(path, content_str)
            
        except Exception as e:
            print(f"Error opening file {path}: {e}")

    def create_tab(self, path, content=""):
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        text_edit = QTextEdit(tab_widget)
        text_edit.setObjectName("EDITCODEditor")
        text_edit.setTabStopDistance(32.0)
        
        font = QFont("UbuntuMono Nerd Font Mono")
        font.setPointSize(11)
        text_edit.setFont(font)
        text_edit.setPlainText(content)
        
        layout.addWidget(text_edit)
        
        tab_widget.text_edit = text_edit
        tab_widget.file_path = path
        tab_widget.is_modified = False
        
        text_edit.textChanged.connect(lambda: self.on_text_changed(tab_widget))
        
        file_name = os.path.basename(path) if path else "Sin título"
        idx = self.ui.TABCODETabs.addTab(tab_widget, file_name)
        self.ui.TABCODETabs.setCurrentIndex(idx)

    def on_text_changed(self, tab_widget):
        if not tab_widget.is_modified:
            tab_widget.is_modified = True
            idx = self.ui.TABCODETabs.indexOf(tab_widget)
            if idx != -1:
                title = self.ui.TABCODETabs.tabText(idx)
                if not title.endswith("*"):
                    self.ui.TABCODETabs.setTabText(idx, title + "*")

    def close_current_tab(self):
        idx = self.ui.TABCODETabs.currentIndex()
        if idx != -1:
            self.close_code_tab(idx)

    def close_code_tab(self, idx):
        widget = self.ui.TABCODETabs.widget(idx)
        if not widget:
            return
            
        if widget.is_modified:
            reply = QMessageBox.question(
                self.window, 
                "Guardar cambios",
                f"El archivo '{self.ui.TABCODETabs.tabText(idx).rstrip('*')}' tiene cambios sin guardar. ¿Deseas guardarlos?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )
            
            if reply == QMessageBox.StandardButton.Save:
                if self.save_tab_file(widget):
                    self.ui.TABCODETabs.removeTab(idx)
            elif reply == QMessageBox.StandardButton.Discard:
                self.ui.TABCODETabs.removeTab(idx)
        else:
            self.ui.TABCODETabs.removeTab(idx)

    def new_file(self):
        self.create_tab(None, "")

    def save_current_file(self):
        idx = self.ui.TABCODETabs.currentIndex()
        if idx == -1:
            return
        widget = self.ui.TABCODETabs.widget(idx)
        self.save_tab_file(widget)

    def save_tab_file(self, widget) -> bool:
        if not widget:
            return False
            
        path = widget.file_path
        if not path:
            file_name, _ = QFileDialog.getSaveFileName(
                self.window,
                "Guardar archivo",
                self.ide.ws_path,
                "Todos los archivos (*)"
            )
            if not file_name:
                return False
            path = file_name
            widget.file_path = path

        try:
            content_bytes = widget.text_edit.toPlainText().encode('utf-8')
            req = file_system_pb2.WriteFileRequest(
                path=path,
                content=content_bytes,
                encoding="utf-8",
                create_dirs=True
            )
            res = self.ide.root.file_stub.Write(req)
            
            if res.ok:
                widget.is_modified = False
                idx = self.ui.TABCODETabs.indexOf(widget)
                if idx != -1:
                    self.ui.TABCODETabs.setTabText(idx, os.path.basename(path))
                
                self.load_file_tree()
                return True
            else:
                print(f"Error saving file: {res.message}")
                return False
        except Exception as e:
            print(f"Exception saving file: {e}")
            return False

    def save_current_file_as(self):
        idx = self.ui.TABCODETabs.currentIndex()
        if idx == -1:
            return
        widget = self.ui.TABCODETabs.widget(idx)
        if not widget:
            return
            
        default_name = widget.file_path or os.path.join(self.ide.ws_path, "Sin título")
        file_name, _ = QFileDialog.getSaveFileName(
            self.window,
            "Guardar como",
            default_name,
            "Todos los archivos (*)"
        )
        if not file_name:
            return
            
        try:
            content_bytes = widget.text_edit.toPlainText().encode('utf-8')
            req = file_system_pb2.WriteFileRequest(
                path=file_name,
                content=content_bytes,
                encoding="utf-8",
                create_dirs=True
            )
            res = self.ide.root.file_stub.Write(req)
            
            if res.ok:
                widget.file_path = file_name
                widget.is_modified = False
                self.ui.TABCODETabs.setTabText(idx, os.path.basename(file_name))
                self.load_file_tree()
        except Exception as e:
            print(f"Error in Save As: {e}")

    def open_file_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self.window,
            "Abrir archivo",
            self.ide.ws_path,
            "Todos los archivos (*)"
        )
        if file_name:
            self.open_file_in_tab(file_name)

    # --- TERMINAL EMULATOR INTEGRATION ---

    def setup_terminal(self):
        font = self.ui.EDITORTERMEditor.font()
        font.setFamily("UbuntuMono Nerd Font Mono")
        font.setStyleHint(font.StyleHint.Monospace)
        self.ui.EDITORTERMEditor.setFont(font)

        self.terminal = TerminalEmulator()
        self.ui.EDITORTERMEditor.keyPressEvent = self.handle_keypress

        # Timer to throttle UI refreshes
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh_terminal_view)
        self.pending_update = False

    def start_terminal_session(self):
        self.ui.EDITORTERMEditor.setHtml("<span style='color: gray;'>Iniciando terminal...</span>")
        self.starter_thread = TerminalStarterThread(self.ide.root.terminal_stub, self.ide.ws_path)
        self.starter_thread.started.connect(self.on_terminal_started)
        self.starter_thread.error.connect(self.on_terminal_start_error)
        self.starter_thread.start()

    def on_terminal_started(self, session_id):
        self.session_id = session_id
        self.ui.EDITORTERMEditor.clear()
        
        # Start stdout listener thread
        self.output_thread = TerminalOutputThread(self.ide.root.terminal_stub, self.session_id)
        self.output_thread.output_received.connect(self.append_to_terminal)
        self.output_thread.start()

    def on_terminal_start_error(self, err_msg):
        self.ui.EDITORTERMEditor.setHtml(f"<span style='color: red;'>Error al iniciar terminal: {err_msg}</span>")

    def append_to_terminal(self, text):
        self.terminal.write(text)
        if not self.pending_update:
            self.pending_update = True
            self.refresh_timer.start(30)

    def refresh_terminal_view(self):
        self.pending_update = False
        self.ui.EDITORTERMEditor.setHtml(self.terminal.get_html())
        
        cursor = self.ui.EDITORTERMEditor.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.ui.EDITORTERMEditor.setTextCursor(cursor)
        
        scrollbar = self.ui.EDITORTERMEditor.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def handle_keypress(self, event):
        text = event.text()
        if not text:
            key = event.key()
            if key == Qt.Key_Return or key == Qt.Key_Enter:
                text = "\r"
            elif key == Qt.Key_Backspace:
                text = "\x7f"
            elif key == Qt.Key_Tab:
                text = "\t"
            elif key == Qt.Key_Escape:
                text = "\x1b"
            elif key == Qt.Key_Up:
                text = "\x1b[A"
            elif key == Qt.Key_Down:
                text = "\x1b[B"
            elif key == Qt.Key_Right:
                text = "\x1b[C"
            elif key == Qt.Key_Left:
                text = "\x1b[D"
            elif key == Qt.Key_Delete:
                text = "\x1b[3~"
            else:
                return

        if self.session_id:
            try:
                req = terminal_pb2.TerminalInput(
                    session_id=self.session_id,
                    data=text.encode('utf-8')
                )
                self.ide.root.terminal_stub.SendInput(req)
            except Exception as e:
                print(f"Error sending terminal input: {e}")

    def cleanup(self):
        if hasattr(self, "output_thread") and self.output_thread:
            self.output_thread.stop()
        if hasattr(self, "introspection_thread") and self.introspection_thread:
            self.introspection_thread.stop()
            self.introspection_thread.wait()
        if hasattr(self, "starter_thread") and self.starter_thread:
            self.starter_thread.wait()
        if self.session_id:
            try:
                req = terminal_pb2.SessionRequest(session_id=self.session_id)
                self.ide.root.terminal_stub.Close(req)
            except Exception as e:
                print(f"Error closing terminal session: {e}")
