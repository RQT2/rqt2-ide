import os
import json
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression, Qt

class RosCodeHighlighter(QSyntaxHighlighter):
    def __init__(self, parent_document, file_ext, theme="dark", available_libs=None):
        super().__init__(parent_document)
        self.available_libs = available_libs
        name = file_ext.lower()
        if name == 'cmakelists.txt' or name == 'cmakelists':
            self.file_ext = 'cmakelists'
        elif '.' in name:
            self.file_ext = name.split('.')[-1]
        else:
            self.file_ext = name
        self.theme = "dark" if "dark" in theme.lower() else "light"
        self.load_colors()
        self.setup_rules()

    def load_colors(self):
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        palette_path = os.path.join(base_path, "external", "rqtll_components", "styles", "palette.json")
        
        self.colors = {
            "keyword": "#0090ff",
            "type": "#3fe1b0",
            "string": "#ffbd4f",
            "comment": "#7f8c8d",
            "number": "#fe4aa3",
            "tag": "#0090ff",
            "attr": "#ffbd4f",
            "function": "#3fe1b0"
        }
        
        if os.path.exists(palette_path):
            try:
                with open(palette_path, "r") as f:
                    data = json.load(f)
                    theme_colors = data.get("themes", {}).get(self.theme, {})
                    if theme_colors:
                        self.colors["keyword"] = theme_colors.get("green", self.colors["keyword"])
                        self.colors["type"] = theme_colors.get("accent", self.colors["type"])
                        self.colors["string"] = theme_colors.get("orange", self.colors["string"])
                        self.colors["comment"] = theme_colors.get("disabled-color", self.colors["comment"])
                        self.colors["number"] = theme_colors.get("purple", self.colors["number"])
                        self.colors["tag"] = theme_colors.get("accent", self.colors["tag"])
                        self.colors["attr"] = theme_colors.get("blue", self.colors["attr"])
                        self.colors["function"] = theme_colors.get("success", self.colors["function"])
            except Exception as e:
                print(f"Error loading palette colors: {e}")

    def setup_rules(self):
        self.highlighting_rules = []

        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(self.colors["keyword"]))
        self.keyword_format.setFontWeight(QFont.Weight.Bold)

        self.type_format = QTextCharFormat()
        self.type_format.setForeground(QColor(self.colors["type"]))

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor(self.colors["string"]))

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor(self.colors["comment"]))
        self.comment_format.setFontItalic(True)

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor(self.colors["number"]))

        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor(self.colors["function"]))
        self.function_format.setFontWeight(QFont.Weight.Bold)

        self.attr_format = QTextCharFormat()
        self.attr_format.setForeground(QColor(self.colors["attr"]))

        cpp_exts = {'cpp', 'hpp', 'h', 'c', 'ino', 'rs', 'proto'}
        xml_exts = {'xml', 'xacro', 'sdf', 'dae', 'urdf', 'launch', 'html'}
        yaml_exts = {'yaml', 'yml', 'toml', 'lock', 'gitignore', 'cfg', 'cmakelist', 'cmakelists'}
        shell_exts = {'sh', 'zsh', 'bash', 'ps1', 'fish'}
        ros_exts = {'msg', 'srv', 'action'}

        if self.file_ext in cpp_exts or self.file_ext == 'py':

            self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'), self.string_format))
            if self.file_ext == 'py':
                self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(?:\\.[^'\\]*)*'"), self.string_format))

            self.highlighting_rules.append((QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), self.number_format))

            # Function calls and definitions (word followed by open parenthesis)
            self.highlighting_rules.append((QRegularExpression(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\()"), self.function_format))
            # Capitalized words (Types / Classes)
            self.highlighting_rules.append((QRegularExpression(r"\b[A-Z][A-Za-z0-9_]*\b"), self.type_format))
            # Attributes/Properties (words following a dot)
            self.highlighting_rules.append((QRegularExpression(r"(?<=\.)[A-Za-z_][A-Za-z0-9_]*\b"), self.attr_format))
            # Namespaces (words before ::)
            self.highlighting_rules.append((QRegularExpression(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\:\:)"), self.type_format))

            if self.file_ext == 'py':
                # Python standard and common ROS libraries + discovered libraries
                py_libs = {"cv2", "os", "sys", "rclpy", "std_msgs", "sensor_msgs", "geometry_msgs", "math", "time", "numpy", "json"}
                if self.available_libs and "py" in self.available_libs:
                    py_libs.update(self.available_libs["py"])
                
                py_libs = [lib for lib in py_libs if lib]
                if py_libs:
                    pattern = r"\b(" + "|".join(py_libs) + r")\b"
                    self.highlighting_rules.append((QRegularExpression(pattern), self.keyword_format))
                
                keywords = [
                    r"\bdef\b", r"\bclass\b", r"\bimport\b", r"\bfrom\b", r"\bas\b",
                    r"\bif\b", r"\belif\b", r"\belse\b", r"\bfor\b", r"\bwhile\b",
                    r"\breturn\b", r"\btry\b", r"\bexcept\b", r"\bfinally\b",
                    r"\bwith\b", r"\bpass\b", r"\bbreak\b", r"\bcontinue\b",
                    r"\band\b", r"\bor\b", r"\bnot\b", r"\bin\b", r"\bis\b", r"\blambda\b",
                    r"\basync\b", r"\bawait\b", r"\byield\b", r"\bassert\b", r"\bglobal\b",
                    r"\bnonlocal\b"
                ]
            else:
                # C++/Arduino standard constants and libraries + discovered libraries
                cpp_libs = {"Serial", "INPUT", "OUTPUT", "HIGH", "LOW"}
                if self.available_libs:
                    if "cpp" in self.available_libs:
                        cpp_libs.update(self.available_libs["cpp"])
                    if "arduino" in self.available_libs:
                        cpp_libs.update(self.available_libs["arduino"])
                
                cpp_libs = [lib for lib in cpp_libs if lib]
                if cpp_libs:
                    pattern = r"\b(" + "|".join(cpp_libs) + r")\b"
                    self.highlighting_rules.append((QRegularExpression(pattern), self.keyword_format))

                keywords = [
                    r"\bclass\b", r"\bstruct\b", r"\bvoid\b", r"\bint\b", r"\bfloat\b",
                    r"\bdouble\b", r"\bchar\b", r"\bbool\b", r"\bif\b", r"\belse\b",
                    r"\bfor\b", r"\bwhile\b", r"\breturn\b", r"\bpublic\b", r"\bprivate\b",
                    r"\bprotected\b", r"\busing\b", r"\bnamespace\b", r"\btemplate\b",
                    r"\btypename\b", r"\bnew\b", r"\bdelete\b", r"\bconst\b", r"\bvirtual\b",
                    r"\bstatic\b", r"\bfn\b", r"\blet\b", r"\bmut\b", r"\bpub\b", r"\bimpl\b",
                    r"\buse\b", r"\btype\b", r"\basync\b", r"\bawait\b", r"\bmatch\b", r"\bself\b",
                    r"\bmod\b", r"\bextern\b", r"\bas\b", r"\bref\b", r"\btrait\b", r"\bwhere\b",
                    r"\bdyn\b"
                ]
            for kw in keywords:
                self.highlighting_rules.append((QRegularExpression(kw), self.keyword_format))

        elif self.file_ext in xml_exts:
            tag_format = QTextCharFormat()
            tag_format.setForeground(QColor(self.colors["tag"]))
            tag_format.setFontWeight(QFont.Weight.Bold)

            attr_format = QTextCharFormat()
            attr_format.setForeground(QColor(self.colors["attr"]))

            self.highlighting_rules.append((QRegularExpression(r'"[^"]*"'), self.string_format))
            self.highlighting_rules.append((QRegularExpression(r"\b[A-Za-z0-9_\-:]+(?=\=)"), attr_format))
            self.highlighting_rules.append((QRegularExpression(r"<[A-Za-z0-9_\-:/]+"), tag_format))
            self.highlighting_rules.append((QRegularExpression(r"</[A-Za-z0-9_\-:]+>"), tag_format))
            self.highlighting_rules.append((QRegularExpression(r"/?>"), tag_format))

        elif self.file_ext in yaml_exts or self.file_ext == 'json':
            if self.file_ext != 'json':
                self.highlighting_rules.append((QRegularExpression(r"#[^\n]*"), self.comment_format))

            self.highlighting_rules.append((QRegularExpression(r'"[^"]*"'), self.string_format))
            self.highlighting_rules.append((QRegularExpression(r"'[^']*'"), self.string_format))

            key_format = QTextCharFormat()
            key_format.setForeground(QColor(self.colors["keyword"]))
            key_format.setFontWeight(QFont.Weight.Bold)
            self.highlighting_rules.append((QRegularExpression(r"^[ \t]*[A-Za-z0-9_\-\.]+(?=\s*:)"), key_format))
            self.highlighting_rules.append((QRegularExpression(r"\b[A-Za-z0-9_\-\.]+(?=\s*=)"), key_format))

        elif self.file_ext in shell_exts:
            self.highlighting_rules.append((QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'), self.string_format))
            self.highlighting_rules.append((QRegularExpression(r"'[^'\\]*(?:\\.[^'\\]*)*'"), self.string_format))
            self.highlighting_rules.append((QRegularExpression(r"\b[0-9]+\b"), self.number_format))

            if self.file_ext == 'ps1':
                keywords = [
                    r"\bif\b", r"\belse\b", r"\belseif\b", r"\bfor\b", r"\bforeach\b",
                    r"\bwhile\b", r"\bdo\b", r"\buntil\b", r"\bswitch\b", r"\bcase\b",
                    r"\bdefault\b", r"\bfunction\b", r"\bfilter\b", r"\breturn\b", r"\bexit\b"
                ]
            else:
                keywords = [
                    r"\bif\b", r"\bthen\b", r"\belse\b", r"\belif\b", r"\bfi\b",
                    r"\bfor\b", r"\bin\b", r"\bdo\b", r"\bdone\b", r"\bwhile\b",
                    r"\bfunction\b", r"\breturn\b", r"\bexit\b", r"\becho\b"
                ]
            for kw in keywords:
                self.highlighting_rules.append((QRegularExpression(kw), self.keyword_format))

        elif self.file_ext == 'md':
            self.highlighting_rules.append((QRegularExpression(r"^#+.*"), self.keyword_format))
            self.highlighting_rules.append((QRegularExpression(r"\*\*.*?\*\*"), self.string_format))
            self.highlighting_rules.append((QRegularExpression(r"__.*?__"), self.string_format))
            self.highlighting_rules.append((QRegularExpression(r"\*.*?\*"), self.type_format))
            self.highlighting_rules.append((QRegularExpression(r"_.*?_"), self.type_format))
            self.highlighting_rules.append((QRegularExpression(r"^[ \t]*[\*\+\-]\s"), self.number_format))
            self.highlighting_rules.append((QRegularExpression(r"`[^`]+`"), self.type_format))

        elif self.file_ext in ros_exts:
            self.highlighting_rules.append((QRegularExpression(r"^---$"), self.keyword_format))
            ros_types = [
                r"\bbool\b", r"\bbyte\b", r"\bchar\b", r"\bfloat32\b", r"\bfloat64\b",
                r"\bint8\b", r"\buint8\b", r"\bint16\b", r"\buint16\b", r"\bint32\b",
                r"\buint32\b", r"\bint64\b", r"\buint64\b", r"\bstring\b", r"\bwstring\b",
                r"\bHeader\b"
            ]
            for rt in ros_types:
                self.highlighting_rules.append((QRegularExpression(rt), self.type_format))

    def highlightBlock(self, text):
        # 1. Detect single-line comment start (ignoring comments inside strings)
        comment_start = -1
        cpp_exts = {'cpp', 'hpp', 'h', 'c', 'ino', 'rs', 'proto', 'json'}
        xml_exts = {'xml', 'xacro', 'sdf', 'dae', 'urdf', 'launch', 'html'}
        comment_char = "#"
        if self.file_ext in cpp_exts:
            comment_char = "//"
        elif self.file_ext in xml_exts:
            comment_char = "<!--"
            
        in_string = None
        escaped = False
        i = 0
        while i < len(text):
            c = text[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if c == '\\':
                escaped = True
                i += 1
                continue
                
            if in_string:
                if c == in_string:
                    in_string = None
            else:
                if c in ('"', "'"):
                    in_string = c
                elif text[i:].startswith(comment_char):
                    comment_start = i
                    break
            i += 1

        # 2. Apply normal regex highlights (only if they don't intersect the comment)
        for pattern, fmt in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            match_iterator = expression.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                start = match.capturedStart()
                length = match.capturedLength()
                if comment_start != -1 and start >= comment_start:
                    continue
                self.setFormat(start, length, fmt)

        # 3. Apply single-line comment highlight
        if comment_start != -1:
            self.setFormat(comment_start, len(text) - comment_start, self.comment_format)

        # 4. Stateful multi-line comments
        self.setCurrentBlockState(0)

        if self.file_ext in cpp_exts:
            start_expr = QRegularExpression(r"/\*")
            end_expr = QRegularExpression(r"\*/")
            self.apply_stateful_multiline(text, start_expr, end_expr, 3, self.comment_format)
            
        elif self.file_ext == 'py':
            start_expr = QRegularExpression(r'"""')
            end_expr = QRegularExpression(r'"""')
            self.apply_stateful_multiline(text, start_expr, end_expr, 1, self.comment_format)
            start_expr2 = QRegularExpression(r"'''")
            end_expr2 = QRegularExpression(r"'''")
            self.apply_stateful_multiline(text, start_expr2, end_expr2, 2, self.comment_format)

        elif self.file_ext in xml_exts:
            start_expr = QRegularExpression(r"<!--")
            end_expr = QRegularExpression(r"-->")
            self.apply_stateful_multiline(text, start_expr, end_expr, 4, self.comment_format)

        elif self.file_ext == 'ps1':
            start_expr = QRegularExpression(r"<#")
            end_expr = QRegularExpression(r"#>")
            self.apply_stateful_multiline(text, start_expr, end_expr, 5, self.comment_format)

    def apply_stateful_multiline(self, text, start_expr, end_expr, state_id, fmt):
        start_index = 0
        state = self.previousBlockState()
        
        if state != state_id:
            state = 0
            
        if state == state_id:
            match = end_expr.match(text)
            if match.hasMatch():
                end_idx = match.capturedEnd()
                self.setFormat(0, end_idx, fmt)
                start_index = end_idx
                state = 0
            else:
                self.setFormat(0, len(text), fmt)
                self.setCurrentBlockState(state_id)
                
        if state == 0:
            match_start = start_expr.match(text, start_index)
            while match_start.hasMatch():
                s_idx = match_start.capturedStart()
                offset = 3 if state_id in (1, 2) else (4 if state_id == 4 else 2)
                match_end = end_expr.match(text, s_idx + offset)
                if match_end.hasMatch():
                    e_idx = match_end.capturedEnd()
                    self.setFormat(s_idx, e_idx - s_idx, fmt)
                    start_index = e_idx
                else:
                    self.setFormat(s_idx, len(text) - s_idx, fmt)
                    self.setCurrentBlockState(state_id)
                    break
                match_start = start_expr.match(text, start_index)
