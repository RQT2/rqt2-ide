import os
import json
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLineEdit,
                               QPushButton, QLabel, QFrame, QTableWidget,
                               QTableWidgetItem, QHeaderView, QTextEdit)
from PySide6.QtGui import QColor, QFont, QKeySequence, QTextCursor, QPalette, QTextDocument
from PySide6.QtCore import Qt, QSize, QEvent

class ThemeableOverlay(QFrame):
    def __init__(self, parent, theme_name="dark"):
        super().__init__(parent)
        self.theme_name = "dark" if "dark" in theme_name.lower() else "light"
        self.load_palette()

        try:
            from external.rqtll_widgets.utils.theme_manager import get_theme_manager
        except Exception:
            try:
                from rqtll_widgets.utils.theme_manager import get_theme_manager
            except Exception:
                def get_theme_manager():
                    return None

        _theme_manager = get_theme_manager()
        if _theme_manager is not None:
            _theme_manager.themeChanged.connect(self.update_theme)

    def update_theme(self, theme_name):
        self.theme_name = "dark" if "dark" in theme_name.lower() else "light"
        self.load_palette()

    def load_palette(self):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        palette_path = os.path.join(base_path, "external", "rqtll_components", "styles", "palette.json")
        
        # Default styling colors
        self.bg_color = "#121212" if self.theme_name == "dark" else "#eaeaea"
        self.text_color = "#ffffff" if self.theme_name == "dark" else "#000000"
        self.accent_color = "#0090ff"
        self.border_color = "#3e3e42" if self.theme_name == "dark" else "#cccccc"
        self.input_bg = "#1e1e1e" if self.theme_name == "dark" else "#ffffff"

        if os.path.exists(palette_path):
            try:
                with open(palette_path, "r") as f:
                    data = json.load(f)
                    theme_colors = data.get("themes", {}).get(self.theme_name, {})
                    if theme_colors:
                        self.accent_color = theme_colors.get("accent", self.accent_color)
                        self.text_color = theme_colors.get("color", self.text_color)
                        if self.theme_name == "dark":
                            self.bg_color = "#121212"
                            self.border_color = "#3e3e42"
                            self.input_bg = "#1e1e1e"
                        else:
                            self.bg_color = "#ffffff"
                            self.border_color = "#cccccc"
                            self.input_bg = "#ffffff"
            except Exception as e:
                print(f"Error loading colors in dialogs: {e}")

        # Set styling sheet
        self.setStyleSheet(f"""
            ThemeableOverlay {{
                background-color: {self.bg_color};
                border: 1px solid {self.border_color};
                border-radius: 6px;
            }}
            QLineEdit {{
                background-color: {self.input_bg};
                color: {self.text_color};
                border: 1px solid {self.border_color};
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.accent_color};
            }}
            QPushButton {{
                background-color: {self.accent_color};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3aa3ff;
            }}
            QLabel {{
                color: {self.text_color};
                font-size: 11px;
                border: none;
                background: transparent;
            }}
        """)


class FindPanel(ThemeableOverlay):
    def __init__(self, parent, editor, theme_name="dark", icon_dirs=None):
        super().__init__(parent, theme_name)
        self.editor = editor
        self.icon_dirs = icon_dirs

        # Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(6)

        # Search field
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Buscar...")
        self.search_input.textChanged.connect(self.search_text)
        self.layout.addWidget(self.search_input)

        # Prev button
        self.btn_prev = QPushButton("", self)
        self.btn_prev.setToolTip("Anterior")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setFixedSize(22, 22)
        self.btn_prev.clicked.connect(self.prev_match)
        self.layout.addWidget(self.btn_prev)

        # Next button
        self.btn_next = QPushButton("", self)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setToolTip("Siguiente")
        self.btn_next.setFixedSize(22, 22)
        self.btn_next.clicked.connect(self.next_match)
        self.layout.addWidget(self.btn_next)

        # Label count
        self.label_count = QLabel("0/0", self)
        self.layout.addWidget(self.label_count)

        self.load_icons()
        self.adjust_position()
        self.hide()

    def update_theme(self, theme_name):
        super().update_theme(theme_name)
        self.load_icons()

    def load_icons(self):
        try:
            from external.rqtll_widgets.utils.icon_loader import load_qicon
        except ImportError:
            try:
                from rqtll_widgets.utils.icon_loader import load_qicon
            except ImportError:
                def load_qicon(path, icon_dirs=None):
                    from PySide6.QtGui import QIcon
                    return QIcon()
        
        self.btn_prev.setIcon(load_qicon(os.path.join('arrows', 'left.svg'), self.icon_dirs))
        self.btn_next.setIcon(load_qicon(os.path.join('arrows', 'right.svg'), self.icon_dirs))

    def adjust_position(self):
        # Place in the top right of the parent
        parent_rect = self.parentWidget().rect()
        w = 260
        h = 36
        self.setGeometry(parent_rect.right() - w - 24, parent_rect.top() + 12, w, h)

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self.search_text()

    def hideEvent(self, event):
        self.editor.search_query = ""
        self.editor.on_cursor_position_changed()
        super().hideEvent(event)

    def search_text(self):
        query = self.search_input.text()
        self.editor.search_query = query
        self.editor.on_cursor_position_changed()
        if not query:
            self.label_count.setText("0/0")
            return
            
        doc = self.editor.document()
        # Find all occurrences
        matches = []
        curr = doc.find(query)
        while not curr.isNull():
            matches.append(curr)
            curr = doc.find(query, curr)
            
        if not matches:
            self.label_count.setText("0/0")
            return

        # Find which match we are currently on
        cursor = self.editor.textCursor()
        curr_idx = 0
        for idx, match in enumerate(matches):
            if match.position() >= cursor.position():
                curr_idx = idx
                break
        else:
            curr_idx = len(matches) - 1
            
        self.label_count.setText(f"{curr_idx + 1}/{len(matches)}")

    def next_match(self):
        query = self.search_input.text()
        if query:
            self.editor.find(query)
            self.search_text()

    def prev_match(self):
        query = self.search_input.text()
        if query:
            self.editor.find(query, QTextDocument.FindFlag.FindBackward)
            self.search_text()


class ReplacePanel(ThemeableOverlay):
    def __init__(self, parent, editor, theme_name="dark", icon_dirs=None):
        super().__init__(parent, theme_name)
        self.editor = editor
        self.icon_dirs = icon_dirs

        # Layout
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(6, 6, 6, 6)
        self.v_layout.setSpacing(6)

        # Row 1: Search
        self.row1 = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Buscar...")
        self.search_input.textChanged.connect(self.search_text)
        self.row1.addWidget(self.search_input)

        self.btn_prev = QPushButton("", self)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setFixedSize(22, 22)
        self.btn_prev.clicked.connect(self.prev_match)
        self.row1.addWidget(self.btn_prev)

        self.btn_next = QPushButton("", self)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setFixedSize(22, 22)
        self.btn_next.clicked.connect(self.next_match)
        self.row1.addWidget(self.btn_next)

        self.label_count = QLabel("0/0", self)
        self.row1.addWidget(self.label_count)
        self.v_layout.addLayout(self.row1)

        # Row 2: Replace
        self.row2 = QHBoxLayout()
        self.replace_input = QLineEdit(self)
        self.replace_input.setPlaceholderText("Reemplazar con...")
        self.row2.addWidget(self.replace_input)

        self.btn_replace = QPushButton("Reemplazar", self)
        self.btn_replace.clicked.connect(self.replace_one)
        self.row2.addWidget(self.btn_replace)

        self.btn_replace_all = QPushButton("Todo", self)
        self.btn_replace_all.clicked.connect(self.replace_all)
        self.row2.addWidget(self.btn_replace_all)
        self.v_layout.addLayout(self.row2)

        self.load_icons()
        self.adjust_position()
        self.hide()

    def update_theme(self, theme_name):
        super().update_theme(theme_name)
        self.load_icons()

    def load_icons(self):
        try:
            from external.rqtll_widgets.utils.icon_loader import load_qicon
        except ImportError:
            try:
                from rqtll_widgets.utils.icon_loader import load_qicon
            except ImportError:
                def load_qicon(path, icon_dirs=None):
                    from PySide6.QtGui import QIcon
                    return QIcon()
        
        self.btn_prev.setIcon(load_qicon(os.path.join('arrows', 'left.svg'), self.icon_dirs))
        self.btn_next.setIcon(load_qicon(os.path.join('arrows', 'right.svg'), self.icon_dirs))

    def adjust_position(self):
        parent_rect = self.parentWidget().rect()
        w = 340
        h = 72
        self.setGeometry(parent_rect.right() - w - 24, parent_rect.top() + 12, w, h)

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self.search_text()

    def hideEvent(self, event):
        self.editor.search_query = ""
        self.editor.on_cursor_position_changed()
        super().hideEvent(event)

    def search_text(self):
        query = self.search_input.text()
        self.editor.search_query = query
        self.editor.on_cursor_position_changed()
        if not query:
            self.label_count.setText("0/0")
            return
            
        doc = self.editor.document()
        matches = []
        curr = doc.find(query)
        while not curr.isNull():
            matches.append(curr)
            curr = doc.find(query, curr)
            
        if not matches:
            self.label_count.setText("0/0")
            return

        cursor = self.editor.textCursor()
        curr_idx = 0
        for idx, match in enumerate(matches):
            if match.position() >= cursor.position():
                curr_idx = idx
                break
        else:
            curr_idx = len(matches) - 1
            
        self.label_count.setText(f"{curr_idx + 1}/{len(matches)}")

    def next_match(self):
        query = self.search_input.text()
        if query:
            self.editor.find(query)
            self.search_text()

    def prev_match(self):
        query = self.search_input.text()
        if query:
            self.editor.find(query, QTextDocument.FindFlag.FindBackward)
            self.search_text()

    def replace_one(self):
        cursor = self.editor.textCursor()
        query = self.search_input.text()
        replace_text = self.replace_input.text()
        
        if query and cursor.selectedText() == query:
            cursor.insertText(replace_text)
            self.editor.find(query)
            self.search_text()
        else:
            # If not already selected, find the next one first
            self.next_match()

    def replace_all(self):
        query = self.search_input.text()
        replace_text = self.replace_input.text()
        if not query:
            return

        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        
        # Start from beginning
        self.editor.moveCursor(QTextCursor.MoveOperation.Start)
        while self.editor.find(query):
            self.editor.textCursor().insertText(replace_text)
            
        cursor.endEditBlock()
        self.search_text()


class CommandPalettePanel(ThemeableOverlay):
    def __init__(self, parent, theme_name="dark"):
        super().__init__(parent, theme_name)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(12)

        # Table showing commands
        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Atajo de Teclado", "Descripción del Comando"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setShowGrid(False)
        self.style_table()
        
        self.table.verticalHeader().setVisible(False)
        self.layout.addWidget(self.table)

        # List of commands
        self.commands = [
            ("Ctrl + N", "Nuevo Archivo en Blanco"),
            ("Ctrl + O", "Abrir Archivo de Sistema"),
            ("Ctrl + S", "Guardar Archivo Actual"),
            ("Ctrl + Shift + S", "Guardar Archivo Como..."),
            ("Ctrl + W", "Cerrar Pestaña del Editor"),
            ("Ctrl + F", "Buscar en el Archivo Activo"),
            ("Ctrl + H", "Buscar y Reemplazar en el Archivo Activo"),
            ("Ctrl + ,", "Mostrar Paleta de Atajos / Cheatsheet"),
            ("Ctrl + /", "Comentar / Descomentar Línea de Código"),
            ("Ctrl + Up / Down", "Mover Línea Seleccionada Hacia Arriba / Abajo"),
            ("Ctrl + Scroll Rueda", "Aumentar / Reducir Tamaño de Letra"),
            ("Alt + Click", "Crear Múltiples Cursores (Edición Simultánea)"),
            ("Click Gutter x2", "Contraer / Expandir Bloque de Código (Folding)")
        ]
        
        self.populate_table()
        self.adjust_size()
        self.hide()

    def update_theme(self, theme_name):
        super().update_theme(theme_name)
        self.style_table()
        self.populate_table()

    def style_table(self):
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
            }}
            QHeaderView::section {{
                background-color: transparent;
                color: {self.text_color};
                padding: 4px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid {self.border_color};
            }}
            QTableWidget::item {{
                padding: 4px;
                color: {self.text_color};
                border-bottom: 1px solid {self.border_color}33;
            }}
        """)

    def populate_table(self):
        self.table.setRowCount(len(self.commands))
        for r, (shortcut, desc) in enumerate(self.commands):
            item_shortcut = QTableWidgetItem(shortcut)
            item_shortcut.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_shortcut.setFont(QFont("Monospace", 9, QFont.Weight.Bold))
            item_shortcut.setForeground(QColor(self.text_color))
            self.table.setItem(r, 0, item_shortcut)
            
            item_desc = QTableWidgetItem(desc)
            item_desc.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_desc.setForeground(QColor(self.text_color))
            self.table.setItem(r, 1, item_desc)

    def adjust_size(self):
        # Position centered
        parent_rect = self.parentWidget().rect()
        w = 700
        h = 460
        self.setGeometry(
            (parent_rect.width() - w) // 2,
            (parent_rect.height() - h) // 2,
            w, h
        )
