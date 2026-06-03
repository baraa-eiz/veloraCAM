from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QGroupBox, QGridLayout, QLineEdit, QComboBox, QCheckBox, QMessageBox
)


class OperationStackWidget(QWidget):
    """
    CAM Operations Stack controller.
    Provides drag/button-based reordering, lock controls, inline parameters editors,
    and visual dirty-caching warnings.
    """
    operation_changed = Signal()  # Fired whenever operations are modified
    compile_clicked = Signal(int) # Emits operation index to compile, or -1 for all
    
    def __init__(self, parent=None, tool_library=None):
        super().__init__(parent)
        self.tool_library = tool_library
        self.project = None
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Left Side: List of operations
        self.list_group = QGroupBox("Active Operations Stack")
        self.list_layout = QVBoxLayout(self.list_group)
        
        self.op_list = QListWidget()
        self.op_list.setDragEnabled(True)
        self.op_list.setAcceptDrops(True)
        self.op_list.setDropIndicatorShown(True)
        self.op_list.setDefaultDropAction(Qt.MoveAction)
        self.op_list.currentRowChanged.connect(self.load_operation_details)
        self.op_list.model().rowsMoved.connect(self.handle_drag_reorder)
        self.list_layout.addWidget(self.op_list)
        
        # List controls row
        self.ctrl_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Add Op")
        self.btn_del = QPushButton("Delete")
        self.btn_dup = QPushButton("Duplicate")
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        
        # Style buttons
        self.btn_add.setStyleSheet("background-color: #007acc; color: white;")
        self.btn_del.setStyleSheet("background-color: #5a2a2d;")
        
        self.ctrl_layout.addWidget(self.btn_add)
        self.ctrl_layout.addWidget(self.btn_dup)
        self.ctrl_layout.addWidget(self.btn_del)
        self.ctrl_layout.addWidget(self.btn_up)
        self.ctrl_layout.addWidget(self.btn_down)
        self.list_layout.addLayout(self.ctrl_layout)
        
        self.layout.addWidget(self.list_group, 4)
        
        # Right Side: Parameter Editor Panel
        self.editor_group = QGroupBox("Selected Operation Parameters")
        self.edit_layout = QVBoxLayout(self.editor_group)
        
        self.grid = QGridLayout()
        self.edit_layout.addLayout(self.grid)
        
        # Parameter fields
        self.grid.addWidget(QLabel("Operation Name:"), 0, 0)
        self.op_name = QLineEdit()
        self.grid.addWidget(self.op_name, 0, 1)
        
        self.grid.addWidget(QLabel("Operation Type:"), 1, 0)
        self.op_type = QComboBox()
        self.grid.addWidget(self.op_type, 1, 1)
        
        self.grid.addWidget(QLabel("Active Tool:"), 2, 0)
        self.op_tool = QComboBox()
        self.grid.addWidget(self.op_tool, 2, 1)
        
        self.grid.addWidget(QLabel("Feed Rate XY (mm/min):"), 3, 0)
        self.feed_xy = QLineEdit()
        self.grid.addWidget(self.feed_xy, 3, 1)
        
        self.grid.addWidget(QLabel("Feed Rate Z (mm/min):"), 4, 0)
        self.feed_z = QLineEdit()
        self.grid.addWidget(self.feed_z, 4, 1)
        
        self.grid.addWidget(QLabel("Spindle Speed (RPM):"), 5, 0)
        self.spindle = QLineEdit()
        self.grid.addWidget(self.spindle, 5, 1)
        
        self.grid.addWidget(QLabel("Stepover Vector (mm):"), 6, 0)
        self.stepover = QLineEdit()
        self.grid.addWidget(self.stepover, 6, 1)
        
        self.grid.addWidget(QLabel("Stepdown/Depth (mm):"), 7, 0)
        self.stepdown = QLineEdit()
        self.grid.addWidget(self.stepdown, 7, 1)
        
        self.grid.addWidget(QLabel("Stock Allowance (mm):"), 8, 0)
        self.allowance = QLineEdit()
        self.grid.addWidget(self.allowance, 8, 1)
        
        self.grid.addWidget(QLabel("Target Depth (mm):"), 9, 0)
        self.tgt_depth = QLineEdit()
        self.grid.addWidget(self.tgt_depth, 9, 1)
        
        self.grid.addWidget(QLabel("Safe Clearance Z (mm):"), 10, 0)
        self.safe_z = QLineEdit()
        self.grid.addWidget(self.safe_z, 10, 1)
        
        self.grid.addWidget(QLabel("Raster Direction:"), 11, 0)
        self.raster_direction = QComboBox()
        self.raster_direction.addItems(["Raster X", "Raster Y"])
        self.grid.addWidget(self.raster_direction, 11, 1)
        
        # Checkboxes
        self.chk_enabled = QCheckBox("Enable Operation in G-code export")
        self.chk_locked = QCheckBox("Lock operation (protect from recompiles)")
        self.edit_layout.addWidget(self.chk_enabled)
        self.edit_layout.addWidget(self.chk_locked)
        
        # Save parameter changes button
        self.btn_save = QPushButton("Apply Parameter Changes")
        self.btn_save.setStyleSheet("background-color: #2a5a3d; color: white;")
        self.btn_save.clicked.connect(self.save_current_details)
        self.edit_layout.addWidget(self.btn_save)
        
        # Compile individual operation button
        self.btn_compile_op = QPushButton("Recompile Selected Op Only")
        self.btn_compile_op.setStyleSheet("background-color: #4a5d6e;")
        self.btn_compile_op.clicked.connect(self.trigger_op_compile)
        self.edit_layout.addWidget(self.btn_compile_op)
        
        self.layout.addWidget(self.editor_group, 6)
        
        # Connect list editing buttons
        self.btn_add.clicked.connect(self.add_operation)
        self.btn_del.clicked.connect(self.delete_operation)
        self.btn_dup.clicked.connect(self.duplicate_operation)
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down.clicked.connect(self.move_down)
        
        self.refresh_tool_dropdown()

    def set_project(self, project):
        self.project = project
        self.refresh_list()

    def refresh_tool_dropdown(self):
        self.op_tool.clear()
        if self.tool_library:
            for t in self.tool_library.tools:
                self.op_tool.addItem(f"{t['name']} ({t['id']})", t["id"])

    def refresh_list(self):
        """Redraws the list items based on the project's operation sequence."""
        self.op_list.clear()
        if not self.project:
            return
            
        for idx, op in enumerate(self.project.operations):
            name = op.get("name", "Operation")
            op_type = op.get("type", "CAM")
            tool_id = op.get("tool_id", "")
            enabled = op.get("enabled", True)
            locked = op.get("locked", False)
            dirty = op.get("dirty", True)
            
            status = " [MODIFIED]" if dirty else " [READY]"
            if locked:
                status += " 🔒"
                
            prefix = "☑ " if enabled else "☐ "
            
            item = QListWidgetItem(f"{prefix}{idx+1}. {name} ({op_type}){status}")
            if not enabled:
                item.setForeground(Qt.gray)
            elif dirty:
                item.setForeground(QColor("#ffb703"))  # Amber color for dirty
                
            self.op_list.addItem(item)
            
        if self.project.operations:
            self.op_list.setCurrentRow(0)

    def load_operation_details(self, row):
        """Populates form inputs with parameters from selected operation."""
        if not self.project or row < 0 or row >= len(self.project.operations):
            self.editor_group.setEnabled(False)
            return
            
        self.editor_group.setEnabled(True)
        op = self.project.operations[row]
        
        self.op_name.setText(op.get("name", ""))
        
        # Populate operation type combos based on module types
        self.op_type.clear()
        m_type = self.project.module_type
        if m_type == "Stone Relief":
            self.op_type.addItems(["Raster Roughing", "Finishing Raster", "Cross Finishing"])
        elif m_type == "Wood Relief":
            self.op_type.addItems(["Raster Roughing", "Ball Nose Finishing", "Edge Cleanup"])
        elif m_type == "Wood V-Carve":
            self.op_type.addItems(["Flat Clearing", "V-Carve Detailing"])
        elif m_type == "ACP Panels":
            self.op_type.addItems(["V-Groove Bending", "Contour Cutout"])
            
        self.op_type.setCurrentText(op.get("type", ""))
        
        # Select active tool in combo
        tool_id = op.get("tool_id", "")
        t_idx = self.op_tool.findData(tool_id)
        if t_idx >= 0:
            self.op_tool.setCurrentIndex(t_idx)
            
        self.feed_xy.setText(str(op.get("feed_xy", 2000.0)))
        self.feed_z.setText(str(op.get("feed_z", 1000.0)))
        self.spindle.setText(str(op.get("spindle_speed", 18000)))
        self.stepover.setText(str(op.get("stepover", 1.0)))
        self.stepdown.setText(str(op.get("stepdown", 1.0)))
        self.allowance.setText(str(op.get("stock_allowance", 0.0)))
        self.tgt_depth.setText(str(op.get("max_depth", 10.0)))
        self.safe_z.setText(str(op.get("safe_z", 15.0)))
        self.raster_direction.setCurrentText(op.get("raster_direction", "Raster X"))
        
        self.chk_enabled.setChecked(op.get("enabled", True))
        self.chk_locked.setChecked(op.get("locked", False))

    def save_current_details(self):
        """Saves values from panel inputs back into the active operation dictionary."""
        row = self.op_list.currentRow()
        if not self.project or row < 0 or row >= len(self.project.operations):
            return
            
        op = self.project.operations[row]
        
        # Trigger undo snapshot
        self.project.save_snapshot()
        
        try:
            op["name"] = self.op_name.text().strip() or "Unnamed Op"
            op["type"] = self.op_type.currentText()
            op["tool_id"] = self.op_tool.currentData()
            
            op["feed_xy"] = float(self.feed_xy.text())
            op["feed_z"] = float(self.feed_z.text())
            op["spindle_speed"] = int(float(self.spindle.text()))
            op["stepover"] = float(self.stepover.text())
            op["stepdown"] = float(self.stepdown.text())
            op["stock_allowance"] = float(self.allowance.text())
            op["max_depth"] = float(self.tgt_depth.text())
            op["safe_z"] = float(self.safe_z.text())
            op["raster_direction"] = self.raster_direction.currentText()
            
            op["enabled"] = self.chk_enabled.isChecked()
            op["locked"] = self.chk_locked.isChecked()
            
            # Setting parameters marks this operation as modified (dirty)
            op["dirty"] = True
            
            self.refresh_list()
            self.op_list.setCurrentRow(row)
            self.operation_changed.emit()
            
        except ValueError:
            QMessageBox.critical(self, "Invalid Inputs", "Please ensure speed and dimensions parameters are numerical.")

    def trigger_op_compile(self):
        row = self.op_list.currentRow()
        if row >= 0:
            self.compile_clicked.emit(row)

    def add_operation(self):
        if not self.project:
            return
        self.project.save_snapshot()
        
        # Create standard generic operation
        new_op = {
            "name": "Custom Operational Pass",
            "type": "Raster Roughing" if self.project.module_type != "Wood V-Carve" else "Flat Clearing",
            "enabled": True,
            "tool_id": "T2",
            "feed_xy": 2500.0,
            "feed_z": 1000.0,
            "feed_plunge": 500.0,
            "spindle_speed": 18000,
            "stepover": 2.0,
            "stepdown": 2.0,
            "max_depth": self.project.max_depth,
            "stock_allowance": 0.5,
            "safe_z": 15.0,
            "raster_direction": "Raster X",
            "locked": False,
            "dirty": True
        }
        self.project.operations.append(new_op)
        self.refresh_list()
        self.op_list.setCurrentRow(len(self.project.operations) - 1)
        self.operation_changed.emit()

    def delete_operation(self):
        row = self.op_list.currentRow()
        if not self.project or row < 0 or row >= len(self.project.operations):
            return
        self.project.save_snapshot()
        self.project.operations.pop(row)
        self.refresh_list()
        self.operation_changed.emit()

    def duplicate_operation(self):
        row = self.op_list.currentRow()
        if not self.project or row < 0 or row >= len(self.project.operations):
            return
        self.project.save_snapshot()
        dup = dict(self.project.operations[row])
        dup["name"] += " (Copy)"
        dup["dirty"] = True
        self.project.operations.insert(row + 1, dup)
        self.refresh_list()
        self.op_list.setCurrentRow(row + 1)
        self.operation_changed.emit()

    def move_up(self):
        row = self.op_list.currentRow()
        if not self.project or row <= 0:
            return
        self.project.save_snapshot()
        self.project.operations[row], self.project.operations[row-1] = \
            self.project.operations[row-1], self.project.operations[row]
        self.refresh_list()
        self.op_list.setCurrentRow(row - 1)
        self.operation_changed.emit()

    def move_down(self):
        row = self.op_list.currentRow()
        if not self.project or row < 0 or row >= len(self.project.operations) - 1:
            return
        self.project.save_snapshot()
        self.project.operations[row], self.project.operations[row+1] = \
            self.project.operations[row+1], self.project.operations[row]
        self.refresh_list()
        self.op_list.setCurrentRow(row + 1)
        self.operation_changed.emit()

    def handle_drag_reorder(self, parent, start, end, destination, row):
        """Fires when items are drag-n-drop reordered in QListWidget."""
        if not self.project:
            return
        # Simple list reload to match visual state
        self.project.save_snapshot()
        new_ops = []
        for idx in range(self.op_list.count()):
            # Read index from old operation
            item_text = self.op_list.item(idx).text()
            # Extract number prefix e.g. "☑ 2." -> index 1
            parts = item_text.split(".")
            old_num = int(parts[0].replace("☑", "").replace("☐", "").strip())
            new_ops.append(self.project.operations[old_num - 1])
            
        self.project.operations = new_ops
        self.refresh_list()
        self.operation_changed.emit()
