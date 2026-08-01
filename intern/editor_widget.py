import os
import json
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PySide6.QtGui import (QPainter, QTextFormat, QColor, QTextCursor, QFont,
                           QPen, QKeySequence)
from PySide6.QtCore import Qt, QRect, QSize, Signal

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditorWidget(QPlainTextEdit):
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self.theme_name = "dark" if "dark" in theme.lower() else "light"
        
        self.line_number_area = LineNumberArea(self)
        self.extra_cursors = []
        self.collapsed_blocks = set()

        self.load_palette()

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.on_cursor_position_changed)

        self.update_line_number_area_width(0)

        self.search_query = ""

        import os
        from PySide6.QtGui import QFontDatabase
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fonts_dir = os.path.join(base_path, "external", "rqtll_components", "assets", "fonts", "Ubuntu_Mono_Nerd_Font")
        if os.path.exists(fonts_dir):
            for file in os.listdir(fonts_dir):
                if file.endswith(".ttf"):
                    QFontDatabase.addApplicationFont(os.path.join(fonts_dir, file))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("UbuntuMono Nerd Font Mono")
        font.setPointSize(11)
        self.setFont(font)
        self.update_tab_stop_width()

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

    def load_palette(self):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        palette_path = os.path.join(base_path, "external", "rqtll_components", "styles", "palette.json")
        
        self.bg_color = QColor("#1e1e1e")
        self.text_color = QColor("#ffffff")
        self.accent_color = QColor("#0090ff")
        self.gutter_bg = QColor("#252526")
        self.gutter_text = QColor("#858585")
        self.current_line_bg = QColor("#2d2d30")
        self.guide_color = QColor("#3c3c3c")
        
        self.current_search_bg = QColor("#0090ff")
        self.current_search_fg = QColor("#000000")
        self.other_search_bg = QColor("#444444")
        self.other_search_fg = QColor("#ffffff")
        self.bracket_bg = QColor("#505050")
        self.bracket_fg = QColor("#ffffff")

        if self.theme_name == "light":
            self.bg_color = QColor("#f5f5f5")
            self.text_color = QColor("#000000")
            self.gutter_bg = QColor("#eaeaea")
            self.gutter_text = QColor("#7a7a7a")
            self.current_line_bg = QColor("#e8e8e8")
            self.guide_color = QColor("#c8c8c8")
            
            self.other_search_bg = QColor("#d0d0d0")
            self.other_search_fg = QColor("#000000")
            self.bracket_bg = QColor("#bbdefb")
            self.bracket_fg = QColor("#000000")

        if os.path.exists(palette_path):
            try:
                with open(palette_path, "r") as f:
                    data = json.load(f)
                    theme_colors = data.get("themes", {}).get(self.theme_name, {})
                    if theme_colors:
                        self.bg_color = QColor(theme_colors.get("background", self.bg_color.name()))
                        self.text_color = QColor(theme_colors.get("color", self.text_color.name()))
                        self.accent_color = QColor(theme_colors.get("accent", self.accent_color.name()))
                        self.gutter_text = QColor(theme_colors.get("disabled-color", self.gutter_text.name()))
                        
                        self.current_search_bg = self.accent_color
                        
                        if self.theme_name == "dark":
                            self.gutter_bg = QColor("#181818")
                            self.current_line_bg = QColor("#282828")
                            self.guide_color = QColor("#2d2d2d")
                        else:
                            self.gutter_bg = QColor("#eaeaea")
                            self.current_line_bg = QColor("#e0e0e0")
                            self.guide_color = QColor("#d3d3d3")
            except Exception as e:
                print(f"Error loading colors in editor: {e}")

        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {self.bg_color.name()};
                color: {self.text_color.name()};
                font-family: 'UbuntuMono Nerd Font Mono', 'Ubuntu Mono', 'Ubuntu Sans Mono', monospace;
                border: none;
            }}
        """)

    def update_theme(self, theme_name):
        parent = self.parentWidget()
        if parent:
            parent.is_loading = True

        self.theme_name = "dark" if "dark" in theme_name.lower() else "light"
        self.load_palette()
        self.update_tab_stop_width()
        if hasattr(self, "highlighter") and self.highlighter:
            self.highlighter.theme = self.theme_name
            self.highlighter.load_colors()
            self.highlighter.setup_rules()
            self.highlighter.rehighlight()
        self.line_number_area.update()
        self.on_cursor_position_changed()

        if parent:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(250, lambda: setattr(parent, "is_loading", False) if parent else None)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            font = self.font()
            size = font.pointSize()
            if delta > 0:
                font.setPointSize(size + 1)
            else:
                font.setPointSize(max(6, size - 1))
            self.setFont(font)
            self.line_number_area.setFont(font)
            self.update_tab_stop_width()
            self.update_line_number_area_width(0)
            event.accept()
        else:
            super().wheelEvent(event)

    def line_number_area_width(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num /= 10
            digits += 1
        space = 24 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    # --- LINE HIGHLIGHT & BRACKET MATCHING ---

    def on_cursor_position_changed(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self.current_line_bg)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

            self.match_brackets(extra_selections)

            self.match_xml_tags(extra_selections)

            if self.search_query:
                query = self.search_query
                doc = self.document()
                curr = doc.find(query)
                cursor = self.textCursor()
                curr_pos = cursor.position()
                
                while not curr.isNull():
                    sel = QTextEdit.ExtraSelection()
                    is_current = (curr.selectionStart() <= curr_pos <= curr.selectionEnd()) or (curr.selectedText() == cursor.selectedText() and abs(curr.position() - cursor.position()) < len(query) + 2)
                    
                    if is_current:
                        sel.format.setBackground(self.current_search_bg)
                        sel.format.setForeground(self.current_search_fg)
                    else:
                        sel.format.setBackground(self.other_search_bg)
                        sel.format.setForeground(self.other_search_fg)
                    
                    sel.cursor = curr
                    extra_selections.append(sel)
                    curr = doc.find(query, curr)

        self.setExtraSelections(extra_selections)

    def match_brackets(self, extra_selections):
        cursor = self.textCursor()
        doc = self.document()
        pos = cursor.position()
        text = doc.toPlainText()

        if not text:
            return

        bracket_pos = -1
        char_pairs = {
            '(': ')', ')': '(',
            '[': ']', ']': '[',
            '{': '}', '}': '{'
        }

        if pos > 0 and text[pos - 1] in char_pairs:
            bracket_pos = pos - 1
        elif pos < len(text) and text[pos] in char_pairs:
            bracket_pos = pos

        if bracket_pos == -1:
            return

        char = text[bracket_pos]
        matching_char = char_pairs[char]
        direction = 1 if char in '([{' else -1

        stack = 1
        search_pos = bracket_pos + direction
        
        while 0 <= search_pos < len(text):
            curr_char = text[search_pos]
            if curr_char == char:
                stack += 1
            elif curr_char == matching_char:
                stack -= 1

            if stack == 0:
                f1 = QTextEdit.ExtraSelection()
                f1.format.setBackground(self.bracket_bg)
                f1.format.setForeground(self.bracket_fg)
                f1.cursor = self.textCursor()
                f1.cursor.setPosition(bracket_pos)
                f1.cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                extra_selections.append(f1)

                f2 = QTextEdit.ExtraSelection()
                f2.format.setBackground(self.bracket_bg)
                f2.format.setForeground(self.bracket_fg)
                f2.cursor = self.textCursor()
                f2.cursor.setPosition(search_pos)
                f2.cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
                extra_selections.append(f2)
                break
            
            search_pos += direction

    def match_xml_tags(self, extra_selections):
        file_ext = ""
        if hasattr(self, "highlighter") and self.highlighter:
            file_ext = self.highlighter.file_ext
            
        xml_exts = {'xml', 'xacro', 'sdf', 'dae', 'urdf', 'html'}
        if file_ext not in xml_exts:
            return

        cursor = self.textCursor()
        pos = cursor.position()
        text = self.document().toPlainText()
        
        if not text:
            return

        start_idx = text.rfind('<', 0, pos)
        if start_idx != -1:
            end_idx = text.find('>', start_idx)
            if end_idx != -1 and start_idx <= pos <= end_idx + 1:
                tag_content = text[start_idx+1 : end_idx].strip()
                if not tag_content:
                    return
                
                if tag_content.endswith('/') or tag_content.startswith('?'):
                    return
                
                is_closing = tag_content.startswith('/')
                tag_name = tag_content[1:].split()[0] if is_closing else tag_content.split()[0]
                
                match_pos = -1
                if not is_closing:
                    stack = 1
                    search_idx = end_idx + 1
                    while True:
                        next_open = text.find('<' + tag_name, search_idx)
                        next_close = text.find('</' + tag_name + '>', search_idx)
                        
                        if next_open == -1 and next_close == -1:
                            break
                            
                        if next_open != -1 and (next_close == -1 or next_open < next_close):
                            tag_end = text.find('>', next_open)
                            if tag_end != -1 and text[tag_end-1] != '/':
                                stack += 1
                            search_idx = next_open + 1
                        else:
                            stack -= 1
                            if stack == 0:
                                match_pos = next_close
                                break
                            search_idx = next_close + 1
                else:
                    stack = 1
                    search_idx = start_idx - 1
                    while search_idx >= 0:
                        next_open = text.rfind('<' + tag_name, 0, search_idx)
                        next_close = text.rfind('</' + tag_name + '>', 0, search_idx)
                        
                        if next_open == -1 and next_close == -1:
                            break
                            
                        if next_close != -1 and (next_open == -1 or next_close > next_open):
                            stack += 1
                            search_idx = next_close - 1
                        else:
                            tag_end = text.find('>', next_open)
                            if tag_end != -1 and text[tag_end-1] != '/':
                                stack -= 1
                                if stack == 0:
                                    match_pos = next_open
                                    break
                            search_idx = next_open - 1
                            
                if match_pos != -1:
                    f1 = QTextEdit.ExtraSelection()
                    f1.format.setBackground(self.bracket_bg)
                    f1.format.setForeground(self.bracket_fg)
                    f1.cursor = self.textCursor()
                    f1.cursor.setPosition(start_idx)
                    f1.cursor.setPosition(end_idx + 1, QTextCursor.MoveMode.KeepAnchor)
                    extra_selections.append(f1)

                    f2 = QTextEdit.ExtraSelection()
                    f2.format.setBackground(self.bracket_bg)
                    f2.format.setForeground(self.bracket_fg)
                    f2.cursor = self.textCursor()
                    f2.cursor.setPosition(match_pos)
                    match_end = text.find('>', match_pos)
                    if match_end != -1:
                        f2.cursor.setPosition(match_end + 1, QTextCursor.MoveMode.KeepAnchor)
                    extra_selections.append(f2)

    def keyPressEvent(self, event):
        key = event.key()
        cursor = self.textCursor()
        text = event.text()

        if text == ">":
            line_text = cursor.block().text()[:cursor.positionInBlock()]
            idx = line_text.rfind("<")
            if idx != -1 and not line_text[idx:].startswith("</") and not line_text.endswith("/"):
                tag_part = line_text[idx+1:].strip()
                tag_name = tag_part.split()[0] if tag_part else ""
                if tag_name and not tag_name.endswith(">"):
                    cursor.beginEditBlock()
                    cursor.insertText(f"></{tag_name}>")
                    cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(tag_name) + 3)
                    cursor.endEditBlock()
                    self.setTextCursor(cursor)
                    return

        pairs = {
            '"': '"', "'": "'",
            '(': ')', '[': ']', '{': '}',
            '<': '>'
        }

        if key == Qt.Key_Backspace:
            pos = cursor.position()
            doc_text = self.document().toPlainText()
            if pos > 0 and pos < len(doc_text):
                prev_char = doc_text[pos - 1]
                next_char = doc_text[pos]
                if prev_char + next_char in ['""', "''", '()', '[]', '{}', '<>']:
                    cursor.beginEditBlock()
                    cursor.deleteChar()
                    cursor.deletePreviousChar()
                    cursor.endEditBlock()
                    return

        if text in pairs:
            closing = pairs[text]
            cursor.beginEditBlock()
            cursor.insertText(text + closing)
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 1)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            block = cursor.block()
            line_text = block.text()
            
            indent = ""
            for c in line_text:
                if c.isspace():
                    indent += c
                else:
                    break
            
            stripped = line_text.strip()
            extra_indent = ""
            if stripped.endswith(":") or stripped.endswith("{") or stripped.endswith("<"):
                extra_indent = "    "
                
            cursor.beginEditBlock()
            cursor.insertText("\n" + indent + extra_indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return

        if self.extra_cursors:
            is_printable = text.isprintable() and len(text) > 0
            cursor.beginEditBlock()
            for c in self.extra_cursors:
                if key == Qt.Key_Backspace:
                    c.deletePreviousChar()
                elif key == Qt.Key_Delete:
                    c.deleteChar()
                elif key in (Qt.Key_Return, Qt.Key_Enter):
                    c.insertText("\n")
                elif key == Qt.Key_Left:
                    c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 1)
                elif key == Qt.Key_Right:
                    c.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, 1)
                elif key == Qt.Key_Up:
                    c.movePosition(QTextCursor.MoveOperation.Up, QTextCursor.MoveMode.MoveAnchor, 1)
                elif key == Qt.Key_Down:
                    c.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, 1)
                elif is_printable:
                    c.insertText(text)
            cursor.endEditBlock()
            self.viewport().update()

        super().keyPressEvent(event)

    # --- MULTICURSOR ---

    def mousePressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.AltModifier:
            pos = self.cursorForPosition(event.pos())
            self.extra_cursors.append(pos)
            self.viewport().update()
        else:
            self.extra_cursors.clear()
            super().mousePressEvent(event)

    def update_tab_stop_width(self):
        char_width = self.fontMetrics().horizontalAdvance(' ')
        self.setTabStopDistance(4 * char_width)


    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.setFont(self.font())
        painter.fillRect(event.rect(), self.gutter_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.gutter_text)
                
                is_folding_start = self.check_folding_start(block)
                if is_folding_start:
                    is_collapsed = block_number in self.collapsed_blocks
                    symbol = "+" if is_collapsed else "-"
                    painter.drawText(
                        4, top, self.line_number_area.width() - 8, self.fontMetrics().height(),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        symbol
                    )
                
                painter.drawText(
                    0, top, self.line_number_area.width() - 16, self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    number
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self.viewport())
        painter.setPen(QPen(self.guide_color, 1, Qt.PenStyle.SolidLine))
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        block_x = self.blockBoundingGeometry(block).translated(self.contentOffset()).left()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                indent_spaces = 0
                for c in block.text():
                    if c == ' ':
                        indent_spaces += 1
                    elif c == '\t':
                        indent_spaces += 4
                    else:
                        break
                
                if indent_spaces > 0:
                    layout = block.layout()
                    if layout.lineCount() > 0:
                        line = layout.lineAt(0)
                        for level in range(4, indent_spaces, 4):
                            try:
                                x_pos = round(block_x + line.cursorToX(level)[0])
                                painter.drawLine(x_pos, top, x_pos, bottom)
                            except Exception:
                                pass

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())

        painter.setPen(self.text_color)
        for c in self.extra_cursors:
            cursor_rect = self.cursorRect(c)
            painter.drawLine(cursor_rect.left(), cursor_rect.top(), cursor_rect.left(), cursor_rect.bottom())


    def check_folding_start(self, block):
        if block.text().strip() == "":
            return False
            
        next_block = block.next()
        while next_block.isValid() and next_block.text().strip() == "":
            next_block = next_block.next()
            
        if not next_block.isValid():
            return False
            
        block_indent = self.get_indent_level(block.text())
        next_indent = self.get_indent_level(next_block.text())
        return next_indent > block_indent

    def get_indent_level(self, text):
        indent = 0
        for c in text:
            if c == ' ':
                indent += 1
            elif c == '\t':
                indent += 4
            else:
                break
        return indent

    def mouseDoubleClickEvent(self, event):
        if event.position().x() < self.line_number_area_width():
            pos = event.position().y()
            block = self.firstVisibleBlock()
            top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number = block.blockNumber()
            
            while block.isValid():
                if top <= pos <= bottom:
                    self.toggle_fold(block_number)
                    break
                block = block.next()
                top = bottom
                bottom = top + round(self.blockBoundingRect(block).height())
                block_number += 1
        else:
            super().mouseDoubleClickEvent(event)

    def toggle_fold(self, block_num):
        block = self.document().findBlockByNumber(block_num)
        if not block.isValid() or not self.check_folding_start(block):
            return

        if block_num in self.collapsed_blocks:
            self.collapsed_blocks.remove(block_num)
            self.set_block_visibility(block_num, True)
        else:
            self.collapsed_blocks.add(block_num)
            self.set_block_visibility(block_num, False)
            
        self.update()
        self.line_number_area.update()

    def set_block_visibility(self, start_block_num, visible):
        doc = self.document()
        start_block = doc.findBlockByNumber(start_block_num)
        start_indent = self.get_indent_level(start_block.text())
        
        curr_block = start_block.next()
        while curr_block.isValid():
            curr_text = curr_block.text()
            if curr_text.strip() != "":
                curr_indent = self.get_indent_level(curr_text)
                if curr_indent <= start_indent:
                    break
                    
            curr_block.setVisible(visible)
            curr_num = curr_block.blockNumber()
            if not visible:
                pass
            else:
                if curr_num in self.collapsed_blocks:
                    self.skip_nested_collapsed(curr_block)
                    curr_block = curr_block.next()
                    continue
                    
            curr_block = curr_block.next()
            
        self.document().markContentsDirty(start_block.position(), doc.characterCount() - start_block.position())

    def skip_nested_collapsed(self, block):
        start_indent = self.get_indent_level(block.text())
        curr_block = block.next()
        while curr_block.isValid():
            curr_text = curr_block.text()
            if curr_text.strip() != "":
                curr_indent = self.get_indent_level(curr_text)
                if curr_indent <= start_indent:
                    break
            curr_block.setVisible(False)
            curr_block = curr_block.next()
