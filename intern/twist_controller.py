import os, json
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QPushButton

import data_stream_pb2

class TwistController(QObject):
    def __init__(self, ide_controller):
        super().__init__()
        self.ide = ide_controller
        self.window = None
        self.ui = None
        
        # Default Key Bindings
        self.key_bindings = {
            "linear_x_pos": Qt.Key_W,
            "linear_x_neg": Qt.Key_S,
            "linear_y_pos": Qt.Key_A,
            "linear_y_neg": Qt.Key_D,
            "linear_z_pos": Qt.Key_R,
            "linear_z_neg": Qt.Key_F,
            "angular_x_pos": Qt.Key_Y,
            "angular_x_neg": Qt.Key_H,
            "angular_y_pos": Qt.Key_I,
            "angular_y_neg": Qt.Key_K,
            "angular_z_pos": Qt.Key_J,
            "angular_z_neg": Qt.Key_L,
            "linear_speed_inc": Qt.Key_E,
            "linear_speed_dec": Qt.Key_Q,
            "angular_speed_inc": Qt.Key_U,
            "angular_speed_dec": Qt.Key_O,
            "stop": Qt.Key_Space
        }

    def bind(self, window):
        self.window = window
        self.ui = window.ui
        
        # Install event filter to capture keyboard globally in this window
        self.window.installEventFilter(self)
        
        # Load custom keybindings from workspace if exists
        self.load_bindings()
        
        # Initialize speed settings
        self.linear_speed = 0.5
        self.angular_speed = 1.0
        self.pressed_actions = set()
        
        self.is_editing_mode = False
        self.selected_action_to_bind = None
        
        # Setup UI buttons mappings
        self.action_buttons = {
            "linear_x_pos": self.ui.BTNFN1,
            "linear_x_neg": self.ui.BTNFN3,
            "linear_y_pos": self.ui.BTNFN2,
            "linear_y_neg": self.ui.BTNFN4,
            "linear_z_pos": self.ui.BTNFN5,
            "linear_z_neg": self.ui.BTNFN6,
            "angular_x_pos": self.ui.BTNFN5_2,
            "angular_x_neg": self.ui.BTNFN6_2,
            "angular_y_pos": self.ui.BTNFN1_2,
            "angular_y_neg": self.ui.BTNFN3_2,
            "angular_z_pos": self.ui.BTNFN2_2,
            "angular_z_neg": self.ui.BTNFN4_2,
            "linear_speed_inc": self.ui.BTNFN7,
            "linear_speed_dec": self.ui.BTNFN8,
            "angular_speed_inc": self.ui.BTNFN9,
            "angular_speed_dec": self.ui.BTNFN10,
            "stop": self.ui.BTNFN
        }
        
        # Update text labels of buttons based on current keybindings
        self.update_button_texts()
        
        # Connect mouse events for buttons
        for action_name, button in self.action_buttons.items():
            if action_name in [
                "linear_x_pos", "linear_x_neg", "linear_y_pos", "linear_y_neg",
                "linear_z_pos", "linear_z_neg", "angular_x_pos", "angular_x_neg",
                "angular_y_pos", "angular_y_neg", "angular_z_pos", "angular_z_neg"
            ]:
                # Use lambda default parameters to bind correct action name
                button.pressed.connect(lambda act=action_name: self.on_button_pressed(act))
                button.released.connect(lambda act=action_name: self.on_button_released(act))
            else:
                button.clicked.connect(lambda checked=False, act=action_name: self.on_button_clicked(act))
                
        # Connect edit button
        self.ui.BTNEdit.clicked.connect(self.on_edit_clicked)
        
        # Initialize label text
        self.ui.LABELInfo2.setText("Vel. lineal: 0.00. Vel angular: 0.00.")

    def get_key_display_name(self, key_code):
        if key_code == Qt.Key_Space:
            return "Espacio"
        name = QKeySequence(key_code).toString()
        return name if name else str(key_code)

    def update_button_texts(self):
        for action_name, button in self.action_buttons.items():
            key_code = self.key_bindings[action_name]
            button.setText(self.get_key_display_name(key_code))

    def load_bindings(self):
        path = os.path.join(self.ide.ws_path, ".rqtll_keybindings.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    for action, key_code in data.items():
                        if action in self.key_bindings:
                            self.key_bindings[action] = key_code
            except Exception as e:
                print(f"Error loading keybindings: {e}")

    def save_bindings(self):
        path = os.path.join(self.ide.ws_path, ".rqtll_keybindings.json")
        try:
            with open(path, "w") as f:
                json.dump(self.key_bindings, f)
        except Exception as e:
            print(f"Error saving keybindings: {e}")

    def on_edit_clicked(self):
        if not self.is_editing_mode:
            self.is_editing_mode = True
            self.ui.BTNEdit.setText("Finalizar edición")
            # Highlight editing state
            self.ui.BTNEdit.setStyleSheet("background-color: #f39c12; color: white;")
        else:
            self.is_editing_mode = False
            self.selected_action_to_bind = None
            self.ui.BTNEdit.setText("Editar botones")
            self.ui.BTNEdit.setStyleSheet("")
            self.update_button_texts()
            self.save_bindings()

    def on_button_clicked(self, action_name):
        if self.is_editing_mode:
            self.selected_action_to_bind = action_name
            # Clear all text and set selected button to prompt wait
            self.update_button_texts()
            self.action_buttons[action_name].setText("?")
        else:
            if action_name in ["linear_speed_inc", "linear_speed_dec", "angular_speed_inc", "angular_speed_dec"]:
                self.on_speed_action(action_name)
            elif action_name == "stop":
                self.on_stop_clicked()

    def on_button_pressed(self, action_name):
        if self.is_editing_mode:
            self.on_button_clicked(action_name)
            return
        self.on_action_pressed(action_name)

    def on_button_released(self, action_name):
        if self.is_editing_mode:
            return
        self.on_action_released(action_name)

    def on_action_pressed(self, action_name):
        self.pressed_actions.add(action_name)
        # Visual feedback: set button to pressed state
        if action_name in self.action_buttons:
            self.action_buttons[action_name].setDown(True)
        self.send_twist_message()

    def on_action_released(self, action_name):
        if action_name in self.pressed_actions:
            self.pressed_actions.remove(action_name)
        # Visual feedback: set button to released state
        if action_name in self.action_buttons:
            self.action_buttons[action_name].setDown(False)
        self.send_twist_message()

    def on_stop_clicked(self):
        self.pressed_actions.clear()
        # Reset all button states
        for button in self.action_buttons.values():
            button.setDown(False)
        self.send_twist_message()

    def on_speed_action(self, action_name):
        if action_name == "linear_speed_inc":
            self.linear_speed += 0.5
        elif action_name == "linear_speed_dec":
            self.linear_speed = max(0.0, self.linear_speed - 0.5)
        elif action_name == "angular_speed_inc":
            self.angular_speed += 0.5
        elif action_name == "angular_speed_dec":
            self.angular_speed = max(0.0, self.angular_speed - 0.5)
        
        # Update display label showing the configured limits
        self.ui.LABELInfo2.setText(f"Vel. lineal: {self.linear_speed:.1f}. Vel angular: {self.angular_speed:.1f}.")

    def bind_key(self, action_name, key_code):
        # Update key binding
        self.key_bindings[action_name] = key_code
        self.selected_action_to_bind = None
        self.update_button_texts()

    def handle_key_event(self, key_code, is_press):
        # Find which action maps to this key code
        for action_name, bound_key in self.key_bindings.items():
            if bound_key == key_code:
                if is_press:
                    if action_name in [
                        "linear_x_pos", "linear_x_neg", "linear_y_pos", "linear_y_neg",
                        "linear_z_pos", "linear_z_neg", "angular_x_pos", "angular_x_neg",
                        "angular_y_pos", "angular_y_neg", "angular_z_pos", "angular_z_neg"
                    ]:
                        self.on_action_pressed(action_name)
                    elif action_name in ["linear_speed_inc", "linear_speed_dec", "angular_speed_inc", "angular_speed_dec"]:
                        self.on_speed_action(action_name)
                        if action_name in self.action_buttons:
                            self.action_buttons[action_name].setDown(True)
                    elif action_name == "stop":
                        self.on_stop_clicked()
                        if action_name in self.action_buttons:
                            self.action_buttons[action_name].setDown(True)
                else:
                    if action_name in [
                        "linear_x_pos", "linear_x_neg", "linear_y_pos", "linear_y_neg",
                        "linear_z_pos", "linear_z_neg", "angular_x_pos", "angular_x_neg",
                        "angular_y_pos", "angular_y_neg", "angular_z_pos", "angular_z_neg"
                    ]:
                        self.on_action_released(action_name)
                    elif action_name in ["linear_speed_inc", "linear_speed_dec", "angular_speed_inc", "angular_speed_dec", "stop"]:
                        if action_name in self.action_buttons:
                            self.action_buttons[action_name].setDown(False)
                return True
        return False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if self.is_editing_mode and self.selected_action_to_bind:
                self.bind_key(self.selected_action_to_bind, event.key())
                return True
            if not event.isAutoRepeat():
                if self.handle_key_event(event.key(), is_press=True):
                    return True
        elif event.type() == QEvent.Type.KeyRelease:
            if not event.isAutoRepeat():
                if self.handle_key_event(event.key(), is_press=False):
                    return True
        return super().eventFilter(obj, event)

    def send_twist_message(self):
        # Calculate velocities
        linear_x = 0.0
        if "linear_x_pos" in self.pressed_actions:
            linear_x = self.linear_speed
        elif "linear_x_neg" in self.pressed_actions:
            linear_x = -self.linear_speed
            
        linear_y = 0.0
        if "linear_y_pos" in self.pressed_actions:
            linear_y = self.linear_speed
        elif "linear_y_neg" in self.pressed_actions:
            linear_y = -self.linear_speed
            
        linear_z = 0.0
        if "linear_z_pos" in self.pressed_actions:
            linear_z = self.linear_speed
        elif "linear_z_neg" in self.pressed_actions:
            linear_z = -self.linear_speed
            
        angular_x = 0.0
        if "angular_x_pos" in self.pressed_actions:
            angular_x = self.angular_speed
        elif "angular_x_neg" in self.pressed_actions:
            angular_x = -self.angular_speed
            
        angular_y = 0.0
        if "angular_y_pos" in self.pressed_actions:
            angular_y = self.angular_speed
        elif "angular_y_neg" in self.pressed_actions:
            angular_y = -self.angular_speed
            
        angular_z = 0.0
        if "angular_z_pos" in self.pressed_actions:
            angular_z = self.angular_speed
        elif "angular_z_neg" in self.pressed_actions:
            angular_z = -self.angular_speed

        # Format Twist message as JSON string
        twist_data = {
            "linear": {"x": linear_x, "y": linear_y, "z": linear_z},
            "angular": {"x": angular_x, "y": angular_y, "z": angular_z}
        }
        json_str = json.dumps(twist_data)
        
        # Publish request to the backend
        try:
            topic = self.ui.lineEdit_2.text().strip() or "cmd_vel"
            req = data_stream_pb2.PublishRequest(
                topic=topic,
                message_type="geometry_msgs/msg/Twist",
                encoding="json",
                data=json_str.encode('utf-8')
            )
            self.ide.root.data_stream_stub.Publish(req)
        except Exception as e:
            # Silent fallback if service is not ready yet
            pass
