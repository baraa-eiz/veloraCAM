import os
import time
from PIL import Image
import numpy as np

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QImage, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QFileDialog, QMessageBox, QGroupBox,
    QGridLayout, QLineEdit, QComboBox, QCheckBox, QProgressBar, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QTabWidget, QScrollArea
)

# Core imports
from core.settings import SettingsManager
from core.project import Project
from core.engine import CAMEngine
from core.writer import ModalWriter
from libraries.tools import ToolLibrary
from libraries.materials import MaterialLibrary
from libraries.machines import MachineLibrary
from postprocessors.post_processor import PostProcessor

# UI imports
from ui.canvas import CAMCanvas
from ui.operation_stack import OperationStackWidget
from ui.surface_opt_view import SurfaceOptimizationView
from ui.curve_comp_view import CurveCompensationView


# ==============================================================================
# PySide6 MULTI-THREADED CAM COMPILES WORKER
# ==============================================================================
class CAMCompileWorker(QThread):
    """
    Background worker thread calculating vectorized toolpaths in parallel
    without blocking the user interface.
    """
    op_progress = Signal(str, int)  # Emits current stage text and percentage
    log_signal = Signal(str)        # Emits text logs to the terminal box
    op_finished = Signal(int, list, dict)  # Emits op index, compiled moves, diagnostics

    def __init__(self, op_idx, op, heightmap_arr, project_params, module):
        super().__init__()
        self.op_idx = op_idx
        self.op = op
        self.heightmap_arr = heightmap_arr
        self.params = project_params
        self.module = module

    def run(self):
        try:
            start_t = time.time()
            self.log_signal.emit(f"[INFO] Compiling Toolpath for Op: '{self.op['name']}'...")
            
            # Compile toolpath moves
            moves = self.module.compile_toolpath(
                self.op, 
                self.heightmap_arr, 
                self.params, 
                progress_callback=self.on_progress
            )
            
            # If globally configured to swap X & Y axes for non-standard machines
            if self.params.get("swap_axes", False):
                moves = [(m[1], m[0], m[2], m[3]) for m in moves]
                
            elapsed = time.time() - start_t
            
            # Simple diagnostics
            g0_moves = sum(1 for m in moves if m[3] == "G00")
            g1_moves = sum(1 for m in moves if m[3] == "G01")
            
            stats = {
                "elapsed_time": elapsed,
                "g0_moves": g0_moves,
                "g1_moves": g1_moves,
                "total_points": len(moves)
            }
            
            self.log_signal.emit(f"[SUCCESS] Op Compiled in {elapsed:.2f}s! Total Coordinates: {len(moves)}")
            self.op_finished.emit(self.op_idx, moves, stats)
            
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Failed compiling op: {str(e)}")
            self.op_finished.emit(self.op_idx, [], {"error": str(e)})

    def on_progress(self, msg, percent):
        self.op_progress.emit(msg, percent)


class ToolEditorDialog(QDialog):
    def __init__(self, tool_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Tool: {tool_data.get('name', 'Unnamed')}")
        self.setMinimumWidth(800)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a22; color: #e0e0e0; }
            QLabel { color: #a0a0b0; font-weight: bold; }
            QLineEdit, QComboBox, QTextEdit { background-color: #24242d; border: 1px solid #363645; color: #e0e0e0; border-radius: 4px; padding: 4px; }
            QPushButton { background-color: #007acc; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #008be6; }
        """)
        
        self.tool_id = tool_data.get("id", "")
        
        main_layout = QVBoxLayout(self)
        
        # Grid layout for fields
        grid = QGridLayout()
        main_layout.addLayout(grid)
        
        # Helper to add inputs
        self.inputs = {}
        
        def add_field(label, key, val, row, col, is_combo=False, combo_items=None):
            lbl = QLabel(label)
            grid.addWidget(lbl, row, col * 2)
            if is_combo:
                cmb = QComboBox()
                cmb.addItems(combo_items or [])
                cmb.setCurrentText(str(val))
                grid.addWidget(cmb, row, col * 2 + 1)
                self.inputs[key] = cmb
            else:
                txt = QLineEdit(str(val))
                grid.addWidget(txt, row, col * 2 + 1)
                self.inputs[key] = txt
                
        # Basic parameters (Col 0)
        add_field("Tool Name:", "name", tool_data.get("name", ""), 0, 0)
        add_field("Tool Type:", "type", tool_data.get("type", "Flat End Mill"), 1, 0, is_combo=True, 
                  combo_items=["Flat End Mill", "Ball Nose", "V-Bit", "Tapered Ball Nose", "Tapered End Mill", "Single Flute cutter"])
        add_field("Tip Diameter (mm):", "tip_diameter", tool_data.get("tip_diameter", 3.0), 2, 0)
        add_field("Ball Radius (mm):", "ball_radius", tool_data.get("ball_radius", 0.0), 3, 0)
        add_field("Max Diameter (mm):", "max_diameter", tool_data.get("max_diameter", 6.0), 4, 0)
        add_field("Taper Angle (deg):", "taper_angle", tool_data.get("taper_angle", 0.0), 5, 0)
        add_field("Shank Diameter (mm):", "shank_diameter", tool_data.get("shank_diameter", 6.0), 6, 0)
        add_field("Max Depth (mm):", "max_depth", tool_data.get("max_depth", 25.0), 7, 0)
        
        # Advanced geometry (Col 1)
        add_field("Neck Diameter (mm):", "neck_diameter", tool_data.get("neck_diameter", tool_data.get("shank_diameter", 6.0)), 0, 1)
        add_field("Flute Length (mm):", "flute_length", tool_data.get("flute_length", tool_data.get("cutting_length", 15.0)), 1, 1)
        add_field("Stickout Length (mm):", "stickout_length", tool_data.get("stickout_length", tool_data.get("tool_length", 50.0) - 10.0), 2, 1)
        add_field("Overall Length (mm):", "overall_length", tool_data.get("overall_length", tool_data.get("tool_length", 50.0)), 3, 1)
        add_field("Safe Clearance (mm):", "safe_clearance_margin", tool_data.get("safe_clearance_margin", 1.0), 4, 1)
        add_field("Max Engagement (mm):", "max_engagement", tool_data.get("max_engagement", 1.5), 5, 1)
        add_field("Max Stepdown (mm):", "max_stepdown", tool_data.get("max_stepdown", 1.5), 6, 1)
        add_field("Max Wall Angle (deg):", "max_wall_angle", tool_data.get("max_wall_angle", 45.0), 7, 1)
        
        # Holder/Notes (Col 2)
        add_field("Min Feature Width (mm):", "min_feature_width", tool_data.get("min_feature_width", tool_data.get("tip_diameter", 3.0)), 0, 2)
        add_field("Holder Diameter (mm):", "holder_diameter", tool_data.get("holder_diameter", 20.0), 1, 2)
        add_field("Collet Diameter (mm):", "collet_diameter", tool_data.get("collet_diameter", 15.0), 2, 2)
        add_field("Holder Length (mm):", "holder_length", tool_data.get("holder_length", 40.0), 3, 2)
        
        # Add Notes field across Col 2
        lbl_notes = QLabel("Tool Notes:")
        grid.addWidget(lbl_notes, 4, 4)
        self.txt_notes = QTextEdit(tool_data.get("notes", ""))
        self.txt_notes.setMaximumHeight(80)
        grid.addWidget(self.txt_notes, 5, 4, 3, 2)
        
        # Buttons
        btns = QHBoxLayout()
        btn_ok = QPushButton("Save Tool Settings")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        main_layout.addLayout(btns)
        
    def get_tool_data(self):
        data = {
            "id": self.tool_id,
            "name": self.inputs["name"].text(),
            "type": self.inputs["type"].currentText(),
            "notes": self.txt_notes.toPlainText()
        }
        # Numeric parsing helper
        for key in ["tip_diameter", "ball_radius", "max_diameter", "taper_angle", 
                    "shank_diameter", "max_depth", "neck_diameter", "flute_length", 
                    "stickout_length", "overall_length", "safe_clearance_margin", 
                    "max_engagement", "max_stepdown", "max_wall_angle", "min_feature_width", 
                    "holder_diameter", "collet_diameter", "holder_length"]:
            try:
                data[key] = float(self.inputs[key].text())
            except ValueError:
                data[key] = 0.0
                
        # Maintain backwards compatibility mappings
        data["tool_length"] = data["overall_length"]
        data["cutting_length"] = data["flute_length"]
        return data


# ==============================================================================
# MAIN WINDOW CLASS
# ==============================================================================
class VeloraCNCMainWindow(QMainWindow):
    """
    Enterprise-Grade CNC workshop control suite and CAM compiler.
    Features elegant left-sidebar navigator, integrated tools catalog,
    and multi-tool G-code processing.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Velora CNC - Modular CAM Workshop")
        self.setMinimumSize(1150, 750)
        
        # 1. Load configuration and core models
        self.settings = SettingsManager()
        self.project = Project()
        self.tool_library = ToolLibrary()
        self.material_library = MaterialLibrary()
        self.machine_library = MachineLibrary()
        
        self.pil_image = None
        self.heightmap_arr = None
        self.processed_arr = None
        self.picker_mode = None
        self.compiled_toolpaths = {}  # op_idx -> list of (x,y,z,cmd)
        self.active_worker = None
        
        # Apply dark theme
        self.setup_theme()
        
        # 2. Main layout structures
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 3. Build sidebar navigation column
        self.build_sidebar()
        
        # 4. Build stacked workflow views
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget, 8)
        
        self.build_views()
        
        # 5. Build right-side Visual preview and audit panel
        self.build_preview_panel()
        
        # Connect currentRowChanged on operation list to update visual overlays
        self.stack_widget.op_list.currentRowChanged.connect(self.update_preprocessed_images)
        
        # Initialize default project and libraries
        self.new_project()
        self.check_autosave_recovery()

    def setup_theme(self):
        # Premium charcoal styling
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#16161d"))
        palette.setColor(QPalette.WindowText, QColor("#e0e0e6"))
        palette.setColor(QPalette.Base, QColor("#1e1e24"))
        palette.setColor(QPalette.AlternateBase, QColor("#24242d"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor("#ffffff"))
        palette.setColor(QPalette.Text, QColor("#e0e0e6"))
        palette.setColor(QPalette.Button, QColor("#323242"))
        palette.setColor(QPalette.ButtonText, QColor("#e0e0e6"))
        palette.setColor(QPalette.Highlight, QColor("#008be6"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)
        
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #e0e0e6;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #363645;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #20202a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #00d2ff;
            }
            QLineEdit, QComboBox {
                background-color: #1a1a20;
                border: 1px solid #363645;
                border-radius: 4px;
                padding: 5px;
                color: #f0f0f5;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #008be6;
            }
            QPushButton {
                background-color: #2b2b36;
                border: 1px solid #3a3a4c;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b3b4a;
                border: 1px solid #4a4a5e;
            }
            QTableWidget {
                background-color: #1a1a20;
                border: 1px solid #363645;
                gridline-color: #363645;
            }
            QHeaderView::section {
                background-color: #2a2a35;
                padding: 4px;
                border: 1px solid #363645;
                font-weight: bold;
            }
        """)

    def build_sidebar(self):
        self.sidebar = QWidget()
        self.sidebar.setStyleSheet("background-color: #111116; border-right: 1px solid #202028;")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 20, 10, 20)
        
        # Logo Card
        self.lbl_logo = QLabel("VELORA CNC")
        self.lbl_logo.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.lbl_logo.setStyleSheet("color: #00d2ff; margin-bottom: 20px;")
        self.lbl_logo.setAlignment(Qt.AlignCenter)
        self.sidebar_layout.addWidget(self.lbl_logo)
        
        # Navigation Buttons
        self.nav_buttons = []
        labels = [
            ("🏠 Dashboard", 0),
            ("🗿 Stone Relief", 1),
            ("🌲 Wood Relief", 2),
            ("✒ Wood V-Carve", 3),
            ("🏷 ACP Paneling", 4),
            ("🔧 Tool Library", 5),
            ("📁 Materials", 6),
            ("💻 Machine Config", 7),
            ("🎛 Surface Optimization", 8),
            ("🔄 Curved Base", 9),
            ("⚙ G-code Compile", 10)
        ]
        
        for name, view_idx in labels:
            btn = QPushButton(name)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 10px;
                    border: none;
                    background-color: transparent;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1e1e26;
                }
            """)
            btn.clicked.connect(lambda checked=False, idx=view_idx: self.switch_view(idx))
            self.sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)
            
        self.sidebar_layout.addStretch()
        
        # Autosave recovery indicator
        self.lbl_recovery = QLabel("Autosave: Active")
        self.lbl_recovery.setStyleSheet("color: #4f5f6f; font-size: 11px;")
        self.lbl_recovery.setAlignment(Qt.AlignCenter)
        self.sidebar_layout.addWidget(self.lbl_recovery)
        
        self.main_layout.addWidget(self.sidebar, 2)

    def build_views(self):
        # Create differentstacked panels
        # View 0: Dashboard Home
        self.view_home = QWidget()
        v_layout = QVBoxLayout(self.view_home)
        self.build_home_view(v_layout)
        self.stacked_widget.addWidget(self.view_home)
        
        # View 1: Stone Relief Panel
        self.view_stone = QWidget()
        v_layout = QVBoxLayout(self.view_stone)
        self.build_stone_view(v_layout)
        self.stacked_widget.addWidget(self.view_stone)
        
        # View 2: Wood Relief Panel
        self.view_wood = QWidget()
        v_layout = QVBoxLayout(self.view_wood)
        self.build_wood_view(v_layout)
        self.stacked_widget.addWidget(self.view_wood)
        
        # View 3: Wood V-Carve Panel
        self.view_vcarve = QWidget()
        v_layout = QVBoxLayout(self.view_vcarve)
        self.build_vcarve_view(v_layout)
        self.stacked_widget.addWidget(self.view_vcarve)
        
        # View 4: ACP Paneling Panel
        self.view_acp = QWidget()
        v_layout = QVBoxLayout(self.view_acp)
        self.build_acp_view(v_layout)
        self.stacked_widget.addWidget(self.view_acp)
        
        # View 5: Tool Library Panel
        self.view_tools = QWidget()
        v_layout = QVBoxLayout(self.view_tools)
        self.build_tools_view(v_layout)
        self.stacked_widget.addWidget(self.view_tools)
        
        # View 7: Materials Catalog
        self.view_materials = QWidget()
        v_layout = QVBoxLayout(self.view_materials)
        self.build_materials_view(v_layout)
        self.stacked_widget.addWidget(self.view_materials)
        
        # View 8: Machine Config Panel
        self.view_machine = QWidget()
        v_layout = QVBoxLayout(self.view_machine)
        self.build_machine_view(v_layout)
        self.stacked_widget.addWidget(self.view_machine)
        
        # View 8: Surface Optimization Panel
        self.view_opt = QWidget()
        v_layout = QVBoxLayout(self.view_opt)
        self.opt_view = SurfaceOptimizationView()
        self.opt_view.parameters_changed.connect(self.on_optimization_params_changed)
        v_layout.addWidget(self.opt_view)
        self.stacked_widget.addWidget(self.view_opt)
        
        # View 9: Curved Base Panel
        self.view_curve = QWidget()
        v_layout = QVBoxLayout(self.view_curve)
        self.curve_view = CurveCompensationView()
        self.curve_view.parameters_changed.connect(self.on_curve_params_changed)
        v_layout.addWidget(self.curve_view)
        self.stacked_widget.addWidget(self.view_curve)
        
        # View 10: G-code compile Panel
        self.view_compile = QWidget()
        v_layout = QVBoxLayout(self.view_compile)
        self.build_compile_view(v_layout)
        self.stacked_widget.addWidget(self.view_compile)

    def build_home_view(self, layout):
        grp = QGroupBox("Welcome to Velora CNC Professional")
        grid = QGridLayout(grp)
        
        lbl_info = QLabel(
            "Modular workshop suite converting displacement depthmaps into precision coordinates.\n"
            "Preload tool settings, build editable operations stacks, and export multiple G-codes."
        )
        lbl_info.setStyleSheet("font-size: 14px; margin-bottom: 20px;")
        grid.addWidget(lbl_info, 0, 0, 1, 2)
        
        btn_new = QPushButton("New Project")
        btn_new.setStyleSheet("background-color: #007acc; color: white;")
        btn_new.clicked.connect(self.new_project)
        grid.addWidget(btn_new, 1, 0)
        
        btn_load = QPushButton("Open Saved Project (.vproj)")
        btn_load.clicked.connect(self.load_project_file)
        grid.addWidget(btn_load, 1, 1)
        
        btn_save = QPushButton("Save Active Project")
        btn_save.clicked.connect(self.save_project_file)
        grid.addWidget(btn_save, 2, 0)
        
        btn_undo = QPushButton("Undo Revert (Ctrl+Z)")
        btn_undo.clicked.connect(self.trigger_undo)
        grid.addWidget(btn_undo, 3, 0)
        
        btn_redo = QPushButton("Redo Action (Ctrl+Y)")
        btn_redo.clicked.connect(self.trigger_redo)
        grid.addWidget(btn_redo, 3, 1)
        
        layout.addWidget(grp)
        layout.addStretch()

    def build_stone_view(self, layout):
        grp = QGroupBox("Stone Relief Milling Settings")
        grid = QGridLayout(grp)
        
        # Inputs config
        grid.addWidget(QLabel("Milling Material:"), 0, 0)
        self.cmb_stone_mat = QComboBox()
        self.cmb_stone_mat.addItems(["Soft Stone", "Hard Stone"])
        grid.addWidget(self.cmb_stone_mat, 0, 1)
        
        grid.addWidget(QLabel("Quality Style Preset:"), 1, 0)
        self.cmb_stone_style = QComboBox()
        self.cmb_stone_style.addItems(["Conservative", "Balanced", "Fast", "High Detail"])
        grid.addWidget(self.cmb_stone_style, 1, 1)
        
        btn_apply = QPushButton("Apply Stone preset Operations")
        btn_apply.setStyleSheet("background-color: #008be6; color: white;")
        btn_apply.clicked.connect(self.apply_stone_presets)
        grid.addWidget(btn_apply, 2, 0, 1, 2)
        
        layout.addWidget(grp)
        
        # Basic displacement settings
        grp_disp = QGroupBox("Displacement Scale Options")
        grid_disp = QGridLayout(grp_disp)
        
        grid_disp.addWidget(QLabel("Width Stock X (mm):"), 0, 0)
        self.txt_stock_x = QLineEdit("300")
        grid_disp.addWidget(self.txt_stock_x, 0, 1)
        
        grid_disp.addWidget(QLabel("Height Stock Y (mm):"), 1, 0)
        self.txt_stock_y = QLineEdit("300")
        grid_disp.addWidget(self.txt_stock_y, 1, 1)
        
        grid_disp.addWidget(QLabel("Max Relief Depth Z (mm):"), 2, 0)
        self.txt_depth_z = QLineEdit("15")
        grid_disp.addWidget(self.txt_depth_z, 2, 1)
        
        self.chk_aspect = QCheckBox("Lock Aspect Ratio")
        self.chk_aspect.setChecked(True)
        grid_disp.addWidget(self.chk_aspect, 3, 0)
        
        self.chk_invert = QCheckBox("Invert displacement map")
        grid_disp.addWidget(self.chk_invert, 3, 1)
        
        # Pick Base color button & label
        self.btn_pick_base = QPushButton("Pick Base Color")
        self.btn_pick_base.clicked.connect(self.start_pick_base)
        grid_disp.addWidget(self.btn_pick_base, 4, 0)
        
        self.lbl_base_color = QLabel("Base Color: [NONE]")
        self.lbl_base_color.setStyleSheet("color: #a0a0b0; font-weight: bold;")
        grid_disp.addWidget(self.lbl_base_color, 4, 1)
        
        self.btn_clear_base = QPushButton("Clear Base Color")
        self.btn_clear_base.clicked.connect(self.clear_base_color)
        grid_disp.addWidget(self.btn_clear_base, 5, 0, 1, 2)
        
        # Axis Orientation selection
        grid_disp.addWidget(QLabel("Axis Orientation:"), 6, 0)
        self.cmb_axis_orient = QComboBox()
        self.cmb_axis_orient.addItems(["Standard (X=X, Y=Y)", "Swap X & Y (Rotated 90°)"])
        self.cmb_axis_orient.currentIndexChanged.connect(self.on_axis_orientation_changed)
        grid_disp.addWidget(self.cmb_axis_orient, 6, 1)
        
        # Z Retract between passes option
        self.chk_retract = QCheckBox("Z Retract Between Passes")
        self.chk_retract.setChecked(True)
        self.chk_retract.stateChanged.connect(self.on_retract_changed)
        grid_disp.addWidget(self.chk_retract, 7, 0, 1, 2)
        
        layout.addWidget(grp_disp)
        layout.addStretch()

    def build_wood_view(self, layout):
        grp = QGroupBox("Wood Relief Milling Settings")
        grid = QGridLayout(grp)
        
        grid.addWidget(QLabel("Milling Material:"), 0, 0)
        self.cmb_wood_mat = QComboBox()
        self.cmb_wood_mat.addItems(["Soft Wood", "Hard Wood", "MDF"])
        grid.addWidget(self.cmb_wood_mat, 0, 1)
        
        grid.addWidget(QLabel("Quality Style Preset:"), 1, 0)
        self.cmb_wood_style = QComboBox()
        self.cmb_wood_style.addItems(["Conservative", "Balanced", "Fast", "High Detail"])
        grid.addWidget(self.cmb_wood_style, 1, 1)
        
        btn_apply = QPushButton("Apply Wood preset Operations")
        btn_apply.setStyleSheet("background-color: #008be6; color: white;")
        btn_apply.clicked.connect(self.apply_wood_presets)
        grid.addWidget(btn_apply, 2, 0, 1, 2)
        
        layout.addWidget(grp)
        layout.addStretch()

    def build_vcarve_view(self, layout):
        grp = QGroupBox("Wood V-Carve Settings")
        grid = QGridLayout(grp)
        
        grid.addWidget(QLabel("Milling Material:"), 0, 0)
        self.cmb_vc_mat = QComboBox()
        self.cmb_vc_mat.addItems(["Soft Wood", "Hard Wood"])
        grid.addWidget(self.cmb_vc_mat, 0, 1)
        
        grid.addWidget(QLabel("V-Bit Included Angle (deg):"), 1, 0)
        self.cmb_vc_angle = QComboBox()
        self.cmb_vc_angle.addItems(["30", "45", "60", "90"])
        self.cmb_vc_angle.setCurrentText("60")
        grid.addWidget(self.cmb_vc_angle, 1, 1)
        
        btn_apply = QPushButton("Apply V-Carve Operations")
        btn_apply.setStyleSheet("background-color: #008be6; color: white;")
        btn_apply.clicked.connect(self.apply_vcarve_presets)
        grid.addWidget(btn_apply, 2, 0, 1, 2)
        
        layout.addWidget(grp)
        layout.addStretch()

    def build_acp_view(self, layout):
        grp = QGroupBox("Alucobond ACP Panel Fabrication Settings")
        grid = QGridLayout(grp)
        
        grid.addWidget(QLabel("Composite Thickness (mm):"), 0, 0)
        self.txt_acp_thick = QLineEdit("4.0")
        grid.addWidget(self.txt_acp_thick, 0, 1)
        
        grid.addWidget(QLabel("Bending Remaining Backing (mm):"), 1, 0)
        self.txt_acp_backing = QLineEdit("0.8")
        grid.addWidget(self.txt_acp_backing, 1, 1)
        
        btn_apply = QPushButton("Apply ACP Grooving Operations")
        btn_apply.setStyleSheet("background-color: #008be6; color: white;")
        btn_apply.clicked.connect(self.apply_acp_presets)
        grid.addWidget(btn_apply, 2, 0, 1, 2)
        
        layout.addWidget(grp)
        layout.addStretch()

    def build_tools_view(self, layout):
        grp = QGroupBox("Tool Database Editor")
        grid = QVBoxLayout(grp)
        
        self.table_tools = QTableWidget()
        self.table_tools.setColumnCount(6)
        self.table_tools.setHorizontalHeaderLabels(["ID", "Name", "Type", "Tip Dia", "Taper Angle", "Cutting Len"])
        self.table_tools.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_tools.itemDoubleClicked.connect(self.on_tool_double_clicked)
        grid.addWidget(self.table_tools)
        
        # Tools control buttons
        row_btn = QHBoxLayout()
        btn_add = QPushButton("Add New Tool")
        btn_add.clicked.connect(self.add_library_tool)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(self.delete_library_tool)
        row_btn.addWidget(btn_add)
        row_btn.addWidget(btn_del)
        grid.addLayout(row_btn)
        
        layout.addWidget(grp)
        self.refresh_tools_table()

    def build_materials_view(self, layout):
        grp = QGroupBox("Materials Library Database (Read-only reference)")
        grid = QVBoxLayout(grp)
        
        self.table_mats = QTableWidget()
        self.table_mats.setColumnCount(5)
        self.table_mats.setHorizontalHeaderLabels(["Material", "Suggested Feed", "Suggested Plunge", "Spindle Speed", "Stepover Scale"])
        self.table_mats.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        grid.addWidget(self.table_mats)
        
        layout.addWidget(grp)
        self.refresh_materials_table()

    def build_machine_view(self, layout):
        grp = QGroupBox("CNC Machine Configurations")
        grid = QGridLayout(grp)
        
        grid.addWidget(QLabel("Active Machine Profile:"), 0, 0)
        self.cmb_mach_prof = QComboBox()
        self.cmb_mach_prof.addItems(self.machine_library.get_all_names())
        self.cmb_mach_prof.currentIndexChanged.connect(self.load_machine_settings)
        grid.addWidget(self.cmb_mach_prof, 0, 1)
        
        grid.addWidget(QLabel("Safe retract Z (mm):"), 1, 0)
        self.txt_mach_safez = QLineEdit("20")
        grid.addWidget(self.txt_mach_safez, 1, 1)
        
        grid.addWidget(QLabel("Travel Limits X max (mm):"), 2, 0)
        self.txt_mach_xmax = QLineEdit("1200")
        grid.addWidget(self.txt_mach_xmax, 2, 1)
        
        grid.addWidget(QLabel("Travel Limits Y max (mm):"), 3, 0)
        self.txt_mach_ymax = QLineEdit("2400")
        grid.addWidget(self.txt_mach_ymax, 3, 1)
        
        grid.addWidget(QLabel("Default post-processor:"), 4, 0)
        self.cmb_mach_post = QComboBox()
        self.cmb_mach_post.addItems(["Mach3", "GRBL", "NCStudio", "Generic ISO"])
        grid.addWidget(self.cmb_mach_post, 4, 1)
        
        layout.addWidget(grp)
        layout.addStretch()

    def build_compile_view(self, layout):
        grp = QGroupBox("Compile Job & Export G-code Files")
        grid = QGridLayout(grp)
        
        grid.addWidget(QLabel("Export Compilation Mode:"), 0, 0)
        self.cmb_exp_mode = QComboBox()
        self.cmb_exp_mode.addItems(["Single File with Pause (Mode A)", "Separate Files per Tool (Mode B)", "Separate Files per Operation (Mode C)"])
        grid.addWidget(self.cmb_exp_mode, 0, 1)
        
        grid.addWidget(QLabel("Toolpath Geometry Mode:"), 1, 0)
        self.cmb_geom_mode = QComboBox()
        self.cmb_geom_mode.addItems(["Legacy Thin-Tool Mode", "True Tool Geometry Aware"])
        self.cmb_geom_mode.currentIndexChanged.connect(self.on_geometry_mode_changed)
        grid.addWidget(self.cmb_geom_mode, 1, 1)
        
        grid.addWidget(QLabel("Post Processor Standard:"), 2, 0)
        self.cmb_post_std = QComboBox()
        self.cmb_post_std.addItems(["Mach3", "GRBL", "NCStudio", "Generic ISO"])
        grid.addWidget(self.cmb_post_std, 2, 1)
        
        self.chk_cv_mode = QCheckBox("Force Continuous Velocity (G64)")
        self.chk_cv_mode.setChecked(True)
        grid.addWidget(self.chk_cv_mode, 3, 0, 1, 2)
        
        btn_compile = QPushButton("Compile All Operations & Export")
        btn_compile.setStyleSheet("background-color: #2a5a3d; color: white; font-size: 14px; padding: 10px;")
        btn_compile.clicked.connect(self.compile_all_operations)
        grid.addWidget(btn_compile, 4, 0, 1, 2)
        
        layout.addWidget(grp)
        
        # Statistics Diagnostics group
        self.grp_diag = QGroupBox("Machining Diagnostics Audit")
        v_diag = QVBoxLayout(self.grp_diag)
        self.lbl_stats = QLabel("Total travel time: N/A\nCoordinates: N/A\nSpindle pauses: N/A")
        v_diag.addWidget(self.lbl_stats)
        layout.addWidget(self.grp_diag)
        
        layout.addStretch()

    def build_preview_panel(self):
        self.preview_panel = QWidget()
        self.preview_panel.setStyleSheet("background-color: #1a1a22; border-left: 1px solid #202028;")
        self.preview_layout = QVBoxLayout(self.preview_panel)
        self.preview_layout.setContentsMargins(15, 15, 15, 15)
        
        # Loaded Image panel
        self.lbl_image_status = QLabel("Heightmap Depth: [NONE]")
        self.lbl_image_status.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.preview_layout.addWidget(self.lbl_image_status)
        
        btn_load_img = QPushButton("📂 Load Depthmap Image")
        btn_load_img.clicked.connect(self.load_heightmap_image)
        self.preview_layout.addWidget(btn_load_img)
        
        # Visual interactive simulator and preprocessed image tabs
        self.canvas = CAMCanvas()
        self.canvas.clicked_pos.connect(self.on_canvas_clicked)
        
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setStyleSheet("""
            QTabWidget::panel { border: 1px solid #363645; background-color: #1a1a22; }
            QTabBar::tab { background-color: #24242d; border: 1px solid #363645; padding: 6px 12px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #1a1a22; color: #00d2ff; border-bottom-color: #1a1a22; }
        """)
        
        # 3D Toolpath Simulator
        self.preview_tabs.addTab(self.canvas, "🔍 3D Toolpath")
        
        # Original Image Tab
        self.scroll_orig = QScrollArea()
        self.lbl_preview_orig = QLabel("No Heightmap Loaded")
        self.lbl_preview_orig.setAlignment(Qt.AlignCenter)
        self.lbl_preview_orig.setStyleSheet("background-color: #0b0b0f;")
        self.scroll_orig.setWidget(self.lbl_preview_orig)
        self.scroll_orig.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_orig, "🖼 Original")
        
        # Detected Base Tab
        self.scroll_base = QScrollArea()
        self.lbl_preview_base = QLabel("No Base Detected")
        self.lbl_preview_base.setAlignment(Qt.AlignCenter)
        self.lbl_preview_base.setStyleSheet("background-color: #0b0b0f;")
        self.scroll_base.setWidget(self.lbl_preview_base)
        self.scroll_base.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_base, "🎯 Detected Base")
        
        # Flattened Result Tab
        self.scroll_flat = QScrollArea()
        self.lbl_preview_flat = QLabel("No Optimization Processed")
        self.lbl_preview_flat.setAlignment(Qt.AlignCenter)
        self.lbl_preview_flat.setStyleSheet("background-color: #0b0b0f;")
        self.scroll_flat.setWidget(self.lbl_preview_flat)
        self.scroll_flat.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_flat, "✨ Flattened Result")
        
        # Difference View Tab
        self.scroll_diff = QScrollArea()
        self.lbl_preview_diff = QLabel("No Difference Calculated")
        self.lbl_preview_diff.setAlignment(Qt.AlignCenter)
        self.lbl_preview_diff.setStyleSheet("background-color: #0b0b0f;")
        self.scroll_diff.setWidget(self.lbl_preview_diff)
        self.scroll_diff.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_diff, "📊 Difference View")
        
        # Reachability Map Tab
        self.scroll_reach = QScrollArea()
        self.lbl_preview_reach = QLabel("No Reachability Map Calculated")
        self.lbl_preview_reach.setAlignment(Qt.AlignCenter)
        self.lbl_preview_reach.setStyleSheet("background-color: #0b0b0f;")
        self.scroll_reach.setWidget(self.lbl_preview_reach)
        self.scroll_reach.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_reach, "🟢 Reachability Map")
        
        # Machined Surface Tab
        self.scroll_machined = QScrollArea()
        self.lbl_preview_machined = QLabel("No Machined Surface Simulation Calculated")
        self.lbl_preview_machined.setAlignment(Qt.AlignCenter)
        self.lbl_preview_machined.setStyleSheet("background-color: #0b0b0f;")
        self.scroll_machined.setWidget(self.lbl_preview_machined)
        self.scroll_machined.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_machined, "🛠 Machined Surface")
        
        # Tool Warnings Tab
        self.scroll_warnings = QScrollArea()
        self.txt_warnings = QTextEdit()
        self.txt_warnings.setReadOnly(True)
        self.txt_warnings.setStyleSheet("background-color: #0b0b0f; color: #ff5555; font-family: Consolas; font-size: 11px;")
        self.scroll_warnings.setWidget(self.txt_warnings)
        self.scroll_warnings.setWidgetResizable(True)
        self.preview_tabs.addTab(self.scroll_warnings, "⚠️ Tool Warnings")
        
        self.preview_layout.addWidget(self.preview_tabs, 5)
        
        # Operations stack editing component
        self.stack_widget = OperationStackWidget(tool_library=self.tool_library)
        self.stack_widget.operation_changed.connect(self.on_operations_changed)
        self.stack_widget.compile_clicked.connect(self.compile_single_operation)
        self.preview_layout.addWidget(self.stack_widget, 4)
        
        # Real-time operator logs
        self.preview_layout.addWidget(QLabel("Workshop System Logs:"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(100)
        self.console.setStyleSheet("background-color: #0b0b0f; color: #a0a0b0; border-radius: 4px;")
        self.preview_layout.addWidget(self.console)
        
        # Work Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.preview_layout.addWidget(self.progress_bar)
        
        self.main_layout.addWidget(self.preview_panel, 6)

    # ==============================================================================
    # CORE ACTIONS / CONTROLLERS
    # ==============================================================================
    def switch_view(self, index):
        self.stacked_widget.setCurrentIndex(index)
        
        # Highlight active navigation button
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setStyleSheet("text-align: left; padding: 10px; background-color: #1e1e26; border-radius: 6px; color: #00d2ff;")
            else:
                btn.setStyleSheet("text-align: left; padding: 10px; background-color: transparent; border-radius: 6px;")

    def new_project(self):
        self.project = Project()
        self.compiled_toolpaths.clear()
        self.stack_widget.set_project(self.project)
        self.canvas.set_toolpaths([])
        self.refresh_base_color_ui()
        if hasattr(self, "opt_view"):
            self.opt_view.set_project(self.project)
        if hasattr(self, "curve_view"):
            self.curve_view.set_project(self.project)
        self.update_preprocessed_images()
        self.log("[INFO] Started fresh new CAM project.")
        if hasattr(self, "cmb_geom_mode"):
            self.cmb_geom_mode.setCurrentIndex(0)
        self.canvas.set_stock_dimensions(self.project.stock_x, self.project.stock_y)

    def load_heightmap_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Grayscale Heightmap Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
            
        try:
            self.project.image_path = path
            self.pil_image = Image.open(path)
            self.lbl_image_status.setText(f"Heightmap Depth: {os.path.basename(path)} ({self.pil_image.width}x{self.pil_image.height})")
            
            # Keep heightmap gray and load to canvas
            self.heightmap_arr = np.array(self.pil_image.convert("L"))
            self.canvas.set_heightmap(self.pil_image)
            self.log(f"[SUCCESS] Loaded image heightmap: {os.path.basename(path)}")
            self.update_preprocessed_images()
            self.project.save_snapshot()
            
        except Exception as e:
            QMessageBox.critical(self, "Loading Error", f"Failed loading image: {str(e)}")

    def start_pick_base(self):
        if self.heightmap_arr is None:
            QMessageBox.warning(self, "No Heightmap", "Please load a heightmap image first before picking base color!")
            return
        self.picker_mode = "base"
        self.btn_pick_base.setText("Click visual canvas...")
        self.btn_pick_base.setStyleSheet("background-color: #005999; border: 1px solid #00ffaa; color: white;")
        self.canvas.setCursor(Qt.CrossCursor)
        self.log("[INFO] Click on the visual canvas displacement overlay to select the Base reference color.")

    def clear_base_color(self):
        self.project.base_color = None
        self.refresh_base_color_ui()
        if hasattr(self, "opt_view"):
            self.opt_view.set_project(self.project)
        if hasattr(self, "curve_view"):
            self.curve_view.set_project(self.project)
        self.update_preprocessed_images()
        self.log("[INFO] Cleared base color reference floor.")
        self.project.save_snapshot()
        for op in self.project.operations:
            op["dirty"] = True
        self.stack_widget.refresh_list()

    def on_canvas_clicked(self, x, y, button):
        if getattr(self, "picker_mode", None) != "base":
            return
            
        if self.heightmap_arr is None:
            return
            
        w, h = self.canvas.width(), self.canvas.height()
        margin = 30
        draw_w = w - 2 * margin
        draw_h = h - 2 * margin
        
        scale_x = draw_w / self.project.stock_x
        scale_y = draw_h / self.project.stock_y
        scale = min(scale_x, scale_y)
        
        off_x = margin + (draw_w - self.project.stock_x * scale) / 2.0
        off_y = margin + (draw_h - self.project.stock_y * scale) / 2.0
        
        cx = x - off_x
        cy = y - off_y
        
        stock_w_pixels = self.project.stock_x * scale
        stock_h_pixels = self.project.stock_y * scale
        
        if 0 <= cx < stock_w_pixels and 0 <= cy < stock_h_pixels:
            img_h, img_w = self.heightmap_arr.shape
            
            px = int((cx / stock_w_pixels) * img_w)
            py = int((cy / stock_h_pixels) * img_h)
            
            px = max(0, min(img_w - 1, px))
            py = max(0, min(img_h - 1, py))
            
            color_val = int(self.heightmap_arr[py, px])
            
            self.project.base_color = color_val
            self.refresh_base_color_ui()
            if hasattr(self, "opt_view"):
                self.opt_view.set_project(self.project)
            if hasattr(self, "curve_view"):
                self.curve_view.set_project(self.project)
            self.update_preprocessed_images()
            self.log(f"[SUCCESS] Selected Base reference color: {color_val}")
            
            self.picker_mode = None
            self.canvas.setCursor(Qt.ArrowCursor)
            self.btn_pick_base.setText("Pick Base Color")
            self.btn_pick_base.setStyleSheet("")
            
            self.project.save_snapshot()
            for op in self.project.operations:
                op["dirty"] = True
            self.stack_widget.refresh_list()

    def refresh_base_color_ui(self):
        if self.project.base_color is not None:
            self.lbl_base_color.setText(f"Base Color: {self.project.base_color}")
            self.lbl_base_color.setStyleSheet("color: #00ffaa; font-weight: bold;")
        else:
            self.lbl_base_color.setText("Base Color: [NONE]")
            self.lbl_base_color.setStyleSheet("color: #a0a0b0;")

    def on_axis_orientation_changed(self):
        if not hasattr(self, "cmb_axis_orient"):
            return
        self.project.swap_axes = (self.cmb_axis_orient.currentIndex() == 1)
        self.project.save_snapshot()
        self.log(f"[INFO] Changed Axis Orientation: {'Swap X & Y (Rotated 90°)' if self.project.swap_axes else 'Standard'}")
        for op in self.project.operations:
            op["dirty"] = True
        self.stack_widget.refresh_list()

    def on_retract_changed(self):
        if not hasattr(self, "chk_retract"):
            return
        self.project.retract_between_passes = self.chk_retract.isChecked()
        self.project.save_snapshot()
        self.log(f"[INFO] Set Z Retract between passes: {'ENABLED' if self.project.retract_between_passes else 'DISABLED (Continuous)'}")
        for op in self.project.operations:
            op["dirty"] = True
        self.stack_widget.refresh_list()

    def log(self, text):
        self.console.append(text)

    # ==============================================================================
    # MODULE PRESETS LOADERS
    # ==============================================================================
    def apply_stone_presets(self):
        self.project.module_type = "Stone Relief"
        self.project.material_name = self.cmb_stone_mat.currentText()
        style = self.cmb_stone_style.currentText()
        
        # Load from Stone relief module
        from modules.stone_relief.module import StoneReliefModule
        mod = StoneReliefModule()
        self.project.operations = mod.get_suggested_operations(style_preset=style)
        
        self.sync_dimensions()
        self.stack_widget.refresh_list()
        self.log(f"[INFO] Applied SUGGESTED operations for Stone Relief: {style}")

    def apply_wood_presets(self):
        self.project.module_type = "Wood Relief"
        self.project.material_name = self.cmb_wood_mat.currentText()
        style = self.cmb_wood_style.currentText()
        
        from modules.wood_relief.module import WoodReliefModule
        mod = WoodReliefModule()
        self.project.operations = mod.get_suggested_operations(style_preset=style)
        
        self.sync_dimensions()
        self.stack_widget.refresh_list()
        self.log(f"[INFO] Applied SUGGESTED operations for Wood Relief: {style}")

    def apply_vcarve_presets(self):
        self.project.module_type = "Wood V-Carve"
        self.project.material_name = self.cmb_vc_mat.currentText()
        
        from modules.wood_vcarve.module import WoodVCarveModule
        mod = WoodVCarveModule()
        self.project.operations = mod.get_suggested_operations()
        
        self.sync_dimensions()
        self.stack_widget.refresh_list()
        self.log(f"[INFO] Applied V-Carve preset operations stack.")

    def apply_acp_presets(self):
        self.project.module_type = "ACP Panels"
        self.project.material_name = "ACP / Alucobond"
        
        from modules.acp_panels.module import ACPPanelsModule
        mod = ACPPanelsModule()
        self.project.operations = mod.get_suggested_operations()
        
        # Set panel parameters
        thick = float(self.txt_acp_thick.text() or 4.0)
        backing = float(self.txt_acp_backing.text() or 0.8)
        
        for op in self.project.operations:
            op["panel_thickness"] = thick
            if op["type"] == "V-Groove Bending":
                op["remaining_backing"] = backing
                op["max_depth"] = thick - backing
                
        self.sync_dimensions()
        self.stack_widget.refresh_list()
        self.log(f"[INFO] Applied ACP Panel grooving preset operations stack.")

    def sync_dimensions(self):
        try:
            self.project.stock_x = float(self.txt_stock_x.text())
            self.project.stock_y = float(self.txt_stock_y.text())
            self.project.max_depth = float(self.txt_depth_z.text())
            self.project.preserve_aspect = self.chk_aspect.isChecked()
            self.project.invert_check = self.chk_invert.isChecked()
            if hasattr(self, "cmb_axis_orient"):
                self.project.swap_axes = (self.cmb_axis_orient.currentIndex() == 1)
            if hasattr(self, "chk_retract"):
                self.project.retract_between_passes = self.chk_retract.isChecked()
            
            self.canvas.set_stock_dimensions(self.project.stock_x, self.project.stock_y)
            self.project.perform_autosave()
        except ValueError:
            pass

    # ==============================================================================
    # DYNAMIC CALCULATIONS & G-CODE EXPORT COMPILES
    # ==============================================================================
    def compile_single_operation(self, op_idx):
        if self.heightmap_arr is None:
            QMessageBox.warning(self, "No Heightmap", "Please load a displacement heightmap image before compiling!")
            return
            
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Please wait until the active compilation completes.")
            return
            
        op = self.project.operations[op_idx]
        self.sync_dimensions()
        
        # Get active module instance
        module = self.get_module_instance(self.project.module_type)
        
        # Gather calculation params
        p_params = self.get_compile_params(op)
        p_params["opt_min_z_variation"] = self.project.opt_min_z_variation
        p_params["opt_compression_tol"] = self.project.opt_compression_tol
        
        if self.processed_arr is None and self.heightmap_arr is not None:
            self.update_preprocessed_images()
            
        hmap = self.processed_arr if self.processed_arr is not None else self.heightmap_arr
        
        # Launch QThread background compiler
        self.progress_bar.setValue(0)
        self.active_worker = CAMCompileWorker(op_idx, op, hmap, p_params, module)
        self.active_worker.op_progress.connect(self.on_worker_progress)
        self.active_worker.log_signal.connect(self.log)
        self.active_worker.op_finished.connect(self.on_worker_finished)
        self.active_worker.start()

    def compile_all_operations(self):
        """Compiles only modified (dirty) operations sequentially in order."""
        if self.heightmap_arr is None:
            QMessageBox.warning(self, "No Heightmap", "Please load a displacement heightmap image first!")
            return
            
        # Find first dirty operation index to compile
        dirty_idx = -1
        for idx, op in enumerate(self.project.operations):
            if op.get("enabled", True) and op.get("dirty", True) and not op.get("locked", False):
                dirty_idx = idx
                break
                
        if dirty_idx != -1:
            self.compile_single_operation(dirty_idx)
            # Re-trigger compilation of remaining dirty ops upon success
            self.progress_bar.setValue(0)
        else:
            self.log("[INFO] All active operations compiled and ready! Compiling files...")
            self.export_gcode_files()

    def get_module_instance(self, module_type):
        if module_type == "Stone Relief":
            from modules.stone_relief.module import StoneReliefModule
            return StoneReliefModule()
        elif module_type == "Wood Relief":
            from modules.wood_relief.module import WoodReliefModule
            return WoodReliefModule()
        elif module_type == "Wood V-Carve":
            from modules.wood_vcarve.module import WoodVCarveModule
            return WoodVCarveModule()
        elif module_type == "ACP Panels":
            from modules.acp_panels.module import ACPPanelsModule
            return ACPPanelsModule()
        return None

    def get_compile_params(self, op):
        # Package image scaling parameters
        img_h, img_w = self.heightmap_arr.shape
        
        # Default offset targets
        scale_x = self.project.stock_x / img_w
        scale_y = self.project.stock_y / img_h
        scale = min(scale_x, scale_y)
        
        scaled_w = img_w * scale
        scaled_h = img_h * scale
        
        offset_x = (self.project.stock_x - scaled_w) / 2.0
        offset_y = (self.project.stock_y - scaled_h) / 2.0
        
        # Load tool variables
        tool = self.tool_library.get_tool(op["tool_id"]) or self.tool_library.tools[0]
        
        return {
            "stock_x": self.project.stock_x,
            "stock_y": self.project.stock_y,
            "max_depth": self.project.max_depth,
            "carving_w": img_w,
            "carving_h": img_h,
            "min_x": 0.0,
            "max_x": float(img_w),
            "min_y": float(img_h),
            "max_y": 0.0,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "scaled_w": scaled_w,
            "scaled_h": scaled_h,
            "preserve_aspect": self.project.preserve_aspect,
            "invert_check": self.project.invert_check,
            "swap_axes": self.project.swap_axes,
            "retract_between_passes": self.project.retract_between_passes,
            "base_color": self.project.base_color,
            "tool": tool,
            "simplification_preset": 1,
            "resol_x": 0.4,
            "toolpath_geometry_mode": self.project.toolpath_geometry_mode,
            "curve_params": {
                "curve_enabled": self.project.curve_enabled,
                "curve_direction": self.project.curve_direction,
                "curve_diagonal_dir": self.project.curve_diagonal_dir,
                "curve_control_points": self.project.curve_control_points,
                "curve_interpolation_type": self.project.curve_interpolation_type,
                "curve_smoothness": self.project.curve_smoothness,
                "curve_reference_mode": self.project.curve_reference_mode,
                "stock_x": self.project.stock_x,
                "stock_y": self.project.stock_y
            }
        }

    def on_worker_progress(self, msg, percent):
        self.progress_bar.setValue(percent)
        self.lbl_image_status.setText(f"Status: {msg} ({percent}%)")

    def on_worker_finished(self, op_idx, moves, stats):
        self.progress_bar.setValue(100)
        self.lbl_image_status.setText("Status: Ready")
        
        if not moves:
            QMessageBox.critical(self, "Compilation Error", "Toolpath calculation generated empty coordinates.")
            return
            
        # Store compiled toolpath moves
        self.compiled_toolpaths[op_idx] = moves
        self.project.operations[op_idx]["dirty"] = False
        
        # Reload stack widget display and canvas line rendering
        self.stack_widget.refresh_list()
        self.update_canvas_paths()
        
        # Automatically compile next dirty operation if present
        dirty_idx = -1
        for idx, op in enumerate(self.project.operations):
            if op.get("enabled", True) and op.get("dirty", True) and not op.get("locked", False):
                dirty_idx = idx
                break
                
        if dirty_idx != -1:
            self.compile_single_operation(dirty_idx)
        else:
            self.log("[SUCCESS] Operations compilation sequence complete.")

    def update_canvas_paths(self):
        paths_to_draw = []
        for idx, op in enumerate(self.project.operations):
            if idx in self.compiled_toolpaths and op.get("enabled", True):
                paths_to_draw.append({
                    "name": op["name"],
                    "type": op["type"],
                    "enabled": op["enabled"],
                    "moves": self.compiled_toolpaths[idx]
                })
        self.canvas.set_toolpaths(paths_to_draw)

    def project_curve_params(self):
        return {
            "curve_enabled": self.project.curve_enabled,
            "curve_direction": self.project.curve_direction,
            "curve_diagonal_dir": self.project.curve_diagonal_dir,
            "curve_control_points": self.project.curve_control_points,
            "curve_interpolation_type": self.project.curve_interpolation_type,
            "curve_smoothness": self.project.curve_smoothness,
            "curve_reference_mode": self.project.curve_reference_mode,
            "stock_x": self.project.stock_x,
            "stock_y": self.project.stock_y
        }

    def get_compensated_safe_z(self, op):
        safe_z = op.get("safe_z", 20.0)
        if self.project.curve_enabled:
            max_c_z = CAMEngine.get_curve_max_z(self.project_curve_params())
            safe_z = safe_z + max(0.0, max_c_z)
        return safe_z

    def export_gcode_files(self):
        """Processes and exports the compiled toolpath operations to G-code files."""
        if not self.compiled_toolpaths:
            QMessageBox.warning(self, "Nothing Compiled", "No operations compiled yet!")
            return
            
        export_mode = self.cmb_exp_mode.currentText()
        post_pp = self.cmb_post_std.currentText()
        
        path, _ = QFileDialog.getSaveFileName(self, "Export G-code File", "", "TAP Files (*.tap);;NC Files (*.nc);;G-code (*.gcode)")
        if not path:
            return
            
        try:
            base_dir = os.path.dirname(path)
            base_name, ext = os.path.splitext(os.path.basename(path))
            
            if "Single File" in export_mode:
                # Mode A: Single aggregated file
                with open(path, "w", encoding="utf-8") as f:
                    writer = ModalWriter(f)
                    
                    # 1. Output general starting header using first tool
                    first_op = None
                    for op in self.project.operations:
                        if op.get("enabled", True):
                            first_op = op
                            break
                            
                    first_tool = self.tool_library.get_tool(first_op["tool_id"])
                    
                    header_lines = PostProcessor.get_header(
                        post_pp, base_name, self.project.stock_x, self.project.stock_y,
                        self.project.max_depth, first_tool["name"], first_op["spindle_speed"], self.get_compensated_safe_z(first_op)
                    )
                    for l in header_lines:
                        writer.write_raw_line(l)
                        
                    current_tool_id = first_tool["id"]
                    
                    # 2. Iterate operations and stream coordinates
                    for idx, op in enumerate(self.project.operations):
                        if not op.get("enabled", True) or idx not in self.compiled_toolpaths:
                            continue
                            
                        moves = self.compiled_toolpaths[idx]
                        tool = self.tool_library.get_tool(op["tool_id"])
                        
                        # Ingest tool-change pause if tool ID changes
                        if tool["id"] != current_tool_id:
                            tc_lines = PostProcessor.get_pause_code(
                                post_pp, tool["name"], tool["id"], self.get_compensated_safe_z(op)
                            )
                            for l in tc_lines:
                                writer.write_raw_line(l)
                            current_tool_id = tool["id"]
                            
                        writer.write_comment(f"OPERATION: {op['name']}")
                        for x, y, z, cmd in moves:
                            writer.write_move(cmd, x=x, y=y, z=z, f_val=op["feed_xy"] if cmd == "G01" else None)
                            
                    # 3. Output safe footer
                    footer_lines = PostProcessor.get_footer(post_pp, self.get_compensated_safe_z(first_op))
                    for l in footer_lines:
                        writer.write_raw_line(l)
                        
                self.log(f"[SUCCESS] Exported Single G-code file: {os.path.basename(path)}")
                QMessageBox.information(self, "Export Success", f"G-code file compiled successfully:\n{path}")
                
            else:
                # Mode B/C: Separate files per tool/operation
                file_count = 0
                for idx, op in enumerate(self.project.operations):
                    if not op.get("enabled", True) or idx not in self.compiled_toolpaths:
                        continue
                        
                    moves = self.compiled_toolpaths[idx]
                    tool = self.tool_library.get_tool(op["tool_id"])
                    
                    op_file_path = os.path.join(base_dir, f"{base_name}_OP{idx+1}_{tool['id']}{ext}")
                    with open(op_file_path, "w", encoding="utf-8") as f:
                        writer = ModalWriter(f)
                        
                        header = PostProcessor.get_header(
                            post_pp, f"{base_name}_OP{idx+1}", self.project.stock_x, self.project.stock_y,
                            self.project.max_depth, tool["name"], op["spindle_speed"], self.get_compensated_safe_z(op)
                        )
                        for l in header:
                            writer.write_raw_line(l)
                            
                        writer.write_comment(f"OPERATION: {op['name']}")
                        for x, y, z, cmd in moves:
                            writer.write_move(cmd, x=x, y=y, z=z, f_val=op["feed_xy"] if cmd == "G01" else None)
                            
                        footer = PostProcessor.get_footer(post_pp, self.get_compensated_safe_z(op))
                        for l in footer:
                            writer.write_raw_line(l)
                            
                    file_count += 1
                    
                self.log(f"[SUCCESS] Exported {file_count} separate G-code operations files.")
                QMessageBox.information(self, "Export Success", f"Exported {file_count} individual G-code operation files in:\n{base_dir}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not save G-code file: {str(e)}")

    # ==============================================================================
    # LIBRARIES CATALOG EDITORS
    # ==============================================================================
    def refresh_tools_table(self):
        self.table_tools.setRowCount(0)
        for t in self.tool_library.tools:
            row = self.table_tools.rowCount()
            self.table_tools.insertRow(row)
            
            self.table_tools.setItem(row, 0, QTableWidgetItem(str(t["id"])))
            self.table_tools.setItem(row, 1, QTableWidgetItem(str(t["name"])))
            self.table_tools.setItem(row, 2, QTableWidgetItem(str(t["type"])))
            self.table_tools.setItem(row, 3, QTableWidgetItem(f"{t['tip_diameter']} mm"))
            self.table_tools.setItem(row, 4, QTableWidgetItem(f"{t['taper_angle']} deg"))
            self.table_tools.setItem(row, 5, QTableWidgetItem(f"{t['cutting_length']} mm"))
            
    def on_tool_double_clicked(self, item):
        row = item.row()
        t_id = self.table_tools.item(row, 0).text()
        tool = self.tool_library.get_tool(t_id)
        if not tool:
            return
            
        dialog = ToolEditorDialog(tool, self)
        if dialog.exec_():
            updated = dialog.get_tool_data()
            self.tool_library.edit_tool(t_id, updated)
            self.refresh_tools_table()
            self.stack_widget.refresh_tool_dropdown()
            self.update_preprocessed_images()

    def on_geometry_mode_changed(self, index):
        mode = "Legacy" if index == 0 else "Geometry Aware"
        self.project.toolpath_geometry_mode = mode
        self.project.save_snapshot()
        self.log(f"[INFO] Switched Toolpath Geometry Mode to: {mode}")
        for op in self.project.operations:
            op["dirty"] = True
        self.stack_widget.refresh_list()
        self.update_preprocessed_images()

    def compute_geometry_visualizations(self):
        if self.heightmap_arr is None:
            return
            
        try:
            # 1. Get active operation and tool parameters
            op = None
            if self.project.operations:
                current_row = self.stack_widget.op_list.currentRow()
                if current_row >= 0 and current_row < len(self.project.operations):
                    op = self.project.operations[current_row]
                else:
                    for o in self.project.operations:
                        if o.get("enabled", True):
                            op = o
                            break
                    if op is None:
                        op = self.project.operations[0]
            
            if op is None:
                op = {
                    "type": "Finishing",
                    "tool_id": "T1",
                    "feed_xy": 1200.0,
                    "spindle_speed": 18000.0,
                    "stepover": 0.5,
                    "max_depth": self.project.max_depth,
                    "enabled": True,
                    "dirty": True
                }
                
            tool = self.tool_library.get_tool(op["tool_id"]) or self.tool_library.tools[0]
            ttype = tool["type"]
            
            # Downsample the heightmap for fast preview simulation
            hmap = self.processed_arr if self.processed_arr is not None else self.heightmap_arr
            img_h, img_w = hmap.shape
            preview_size = 150
            if img_w > preview_size or img_h > preview_size:
                scale_f = preview_size / max(img_w, img_h)
                new_w = int(img_w * scale_f)
                new_h = int(img_h * scale_f)
                step_x = max(1, img_w // new_w)
                step_y = max(1, img_h // new_h)
                hmap_ds = hmap[::step_y, ::step_x]
            else:
                hmap_ds = hmap
                
            ds_h, ds_w = hmap_ds.shape
            
            # Create grid coordinates in mm
            xs = np.linspace(0.0, self.project.stock_x, ds_w)
            ys = np.linspace(0.0, self.project.stock_y, ds_h)
            grid_xs, grid_ys = np.meshgrid(xs, ys)
            
            # Scale heightmap to actual target Z
            Z_surf = -self.project.max_depth * (1.0 - hmap_ds / 255.0)
            
            curve_params = {
                "curve_enabled": self.project.curve_enabled,
                "curve_direction": self.project.curve_direction,
                "curve_diagonal_dir": self.project.curve_diagonal_dir,
                "curve_control_points": self.project.curve_control_points,
                "curve_interpolation_type": self.project.curve_interpolation_type,
                "curve_smoothness": self.project.curve_smoothness,
                "curve_reference_mode": self.project.curve_reference_mode,
                "stock_x": self.project.stock_x,
                "stock_y": self.project.stock_y
            }
            if self.project.curve_enabled:
                offsets = CAMEngine.evaluate_curve_offset_at_xy(grid_xs, grid_ys, self.project.stock_x, self.project.stock_y, curve_params)
                Z_surf = Z_surf + offsets
            
            xs_flat = grid_xs.flatten()
            ys_flat = grid_ys.flatten()
            
            offset_x = 0.0
            offset_y = 0.0
            carving_w = ds_w
            carving_h = ds_h
            preserve_aspect = False
            
            # Compute legacy compensated Z
            Z_comp_legacy = CAMEngine.compute_compensated_z_array(
                xs_flat, ys_flat, ttype, tool, hmap_ds, 
                self.project.stock_x, self.project.stock_y, self.project.max_depth,
                carving_w, carving_h, 0.0, float(ds_h), offset_x, offset_y,
                preserve_aspect, self.project.base_color, self.project.invert_check,
                curve_params=curve_params if self.project.curve_enabled else None,
                toolpath_geometry_mode="Legacy"
            ).reshape((ds_h, ds_w))
            
            # Compute geometry aware compensated Z
            Z_comp_aware = CAMEngine.compute_compensated_z_array(
                xs_flat, ys_flat, ttype, tool, hmap_ds, 
                self.project.stock_x, self.project.stock_y, self.project.max_depth,
                carving_w, carving_h, 0.0, float(ds_h), offset_x, offset_y,
                preserve_aspect, self.project.base_color, self.project.invert_check,
                curve_params=curve_params if self.project.curve_enabled else None,
                toolpath_geometry_mode="Geometry Aware"
            ).reshape((ds_h, ds_w))
            
            active_mode = self.project.toolpath_geometry_mode
            Z_comp_active = Z_comp_aware if active_mode == "Geometry Aware" else Z_comp_legacy
            
            # Compute simulated Machined Surface
            safe_margin = float(tool.get("safe_clearance_margin", 1.0))
            r_samples, z_offsets = CAMEngine.compute_tool_profile_lut(tool, ttype, safe_margin)
            
            r_cutter = float(tool.get("tip_diameter", 3.0)) / 2.0
            step = max(0.2, self.project.stock_x / ds_w)
            R_max_cut = r_cutter + 1.0
            search_range = np.arange(-R_max_cut, R_max_cut + step, step)
            grid_dx, grid_dy = np.meshgrid(search_range, search_range)
            grid_dx = grid_dx.flatten()
            grid_dy = grid_dy.flatten()
            grid_r = np.sqrt(grid_dx**2 + grid_dy**2)
            mask_cut = grid_r <= R_max_cut
            grid_dx = grid_dx[mask_cut]
            grid_dy = grid_dy[mask_cut]
            grid_r = grid_r[mask_cut]
            grid_z_offsets = np.interp(grid_r, r_samples, z_offsets)
            
            Z_machined = np.full_like(Z_comp_active, -9999.0)
            
            for dx, dy, z_off in zip(grid_dx, grid_dy, grid_z_offsets):
                shift_x = int(round(dx / step))
                shift_y = int(round(dy / step))
                
                rolled = np.roll(Z_comp_active, (shift_y, shift_x), axis=(0, 1))
                if shift_y > 0:
                    rolled[:shift_y, :] = -self.project.max_depth
                elif shift_y < 0:
                    rolled[shift_y:, :] = -self.project.max_depth
                if shift_x > 0:
                    rolled[:, :shift_x] = -self.project.max_depth
                elif shift_x < 0:
                    rolled[:, shift_x:] = -self.project.max_depth
                    
                Z_machined = np.maximum(Z_machined, rolled + z_off)
            
            Z_machined = np.clip(Z_machined, -self.project.max_depth, 0.0)
            
            # Render Reachability Map
            reach_rgb = np.zeros((ds_h, ds_w, 3), dtype=np.uint8)
            diff = Z_machined - Z_surf
            
            is_green = diff <= 0.15
            is_geometry_retracted = Z_comp_aware > Z_comp_legacy + 0.15
            flute_len = float(tool.get("flute_length", tool.get("cutting_length", 15.0)))
            is_rubbing = (Z_machined < -flute_len)
            is_red = (is_geometry_retracted | is_rubbing) & (~is_green)
            is_yellow = (~is_green) & (~is_red)
            
            reach_rgb[is_green] = [46, 204, 113]
            reach_rgb[is_yellow] = [241, 196, 15]
            reach_rgb[is_red] = [231, 76, 60]
            
            # Render Machined Surface shading
            norm_machined = (Z_machined - Z_machined.min()) / max(1e-5, Z_machined.max() - Z_machined.min())
            dy_img, dx_img = np.gradient(norm_machined)
            lx, ly, lz = 1.0, 1.0, 1.5
            norm_light = np.sqrt(lx**2 + ly**2 + lz**2)
            lx, ly, lz = lx/norm_light, ly/norm_light, lz/norm_light
            
            nx = -dx_img
            ny = -dy_img
            nz = np.ones_like(nx) * 0.15
            norm_n = np.sqrt(nx**2 + ny**2 + nz**2)
            nx, ny, nz = nx/norm_n, ny/norm_n, nz/norm_n
            
            shaded = nx * lx + ny * ly + nz * lz
            shaded = np.clip((shaded + 1.0) / 2.0 * 255.0, 0, 255).astype(np.uint8)
            
            bytes_reach = reach_rgb.tobytes()
            q_img_reach = QImage(bytes_reach, ds_w, ds_h, ds_w*3, QImage.Format_RGB888)
            pm_reach = QPixmap.fromImage(q_img_reach)
            
            scaled_w = max(400, self.canvas.width())
            scaled_h = max(400, self.canvas.height())
            self.lbl_preview_reach.setPixmap(pm_reach.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            pm_machined = self.arr_to_pixmap(shaded)
            self.lbl_preview_machined.setPixmap(pm_machined.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            # Generate Tool Warnings
            warnings = []
            total_px = ds_w * ds_h
            red_px = np.sum(is_red)
            yellow_px = np.sum(is_yellow)
            
            warnings.append(f"=== TOOLPATH ANALYSIS LOG ({active_mode} Mode) ===")
            warnings.append(f"Active Tool: {tool['name']} ({ttype})")
            warnings.append(f"Tip Diameter: {tool['tip_diameter']} mm | Neck Diameter: {tool['neck_diameter']} mm")
            warnings.append(f"Stickout Length: {tool['stickout_length']} mm | Flute Length: {tool['flute_length']} mm")
            warnings.append(f"--------------------------------------------------")
            
            if red_px > 0:
                warnings.append(f"⚠️ DANGER: {red_px / total_px * 100.0:.1f}% of surface has COLLISIONS or RUBBING!")
                if np.any(is_geometry_retracted):
                    warnings.append(f"  - Neck/holder collision detected: Tool was forced to retract to prevent collision.")
                if np.any(is_rubbing):
                    warnings.append(f"  - Flute length exceeded: Machined depth exceeds cutting flute length ({flute_len} mm). Non-cutting neck will rub workpiece.")
            else:
                warnings.append(f"✅ Safe clearance: No neck/holder collisions or flute rubbing detected.")
                
            if yellow_px > 0:
                warnings.append(f"ℹ️ Unreachable regions: {yellow_px / total_px * 100.0:.1f}% of details are too narrow for this cutter nose.")
            else:
                warnings.append(f"✅ Complete detail reachability: Tool nose can resolve all surface features.")
                
            D = tool["neck_diameter"]
            L = tool["stickout_length"]
            if D > 0 and L > 0:
                deflection_index = (L ** 3) / (D ** 4)
                warnings.append(f"--------------------------------------------------")
                warnings.append(f"Tool Deflection / Rigidity Assessment:")
                warnings.append(f"  - Rigidity Index (L^3/D^4): {deflection_index:.2f}")
                if deflection_index > 150.0:
                    warnings.append(f"  ❌ WARNING: Tool is highly flexible! High risk of deflection, chatter, or breakage.")
                    warnings.append(f"     Suggestion: Reduce stickout length or use a tool with a thicker shank.")
                elif deflection_index > 50.0:
                    warnings.append(f"  ⚠️ CAUTION: Moderate tool deflection risk. Suggest conservative feed rate.")
                else:
                    warnings.append(f"  ✅ Tool rigidity is excellent. Stable cutting expected.")
            
            self.txt_warnings.setPlainText("\n".join(warnings))
            
        except Exception as e:
            self.log(f"[ERROR] Morphological simulation preview failed: {str(e)}")
            
    def add_library_tool(self):
        new_t = {
            "name": "Custom Router cutter",
            "type": "Flat End Mill",
            "tip_diameter": 3.175,
            "ball_radius": 0.0,
            "max_diameter": 3.175,
            "tool_length": 40.0,
            "cutting_length": 15.0,
            "taper_angle": 0.0,
            "notes": "Added via Workshop UI catalog."
        }
        self.tool_library.add_tool(new_t)
        self.refresh_tools_table()
        self.stack_widget.refresh_tool_dropdown()
        
    def delete_library_tool(self):
        row = self.table_tools.currentRow()
        if row < 0:
            return
        t_id = self.table_tools.item(row, 0).text()
        self.tool_library.delete_tool(t_id)
        self.refresh_tools_table()
        self.stack_widget.refresh_tool_dropdown()

    def refresh_materials_table(self):
        self.table_mats.setRowCount(0)
        for name in self.material_library.get_all_names():
            m = self.material_library.get_material(name)
            row = self.table_mats.rowCount()
            self.table_mats.insertRow(row)
            
            self.table_mats.setItem(row, 0, QTableWidgetItem(name))
            self.table_mats.setItem(row, 1, QTableWidgetItem(f"{m['feed_rate_suggest']} mm/min"))
            self.table_mats.setItem(row, 2, QTableWidgetItem(f"{m['plunge_rate_suggest']} mm/min"))
            self.table_mats.setItem(row, 3, QTableWidgetItem(f"{m['spindle_rpm_suggest']} RPM"))
            self.table_mats.setItem(row, 4, QTableWidgetItem(str(m['stepover_factor'])))

    def load_machine_settings(self, index):
        names = self.machine_library.get_all_names()
        if index < 0 or index >= len(names):
            return
            
        m = self.machine_library.get_machine(names[index])
        self.txt_mach_safez.setText(str(m["safe_z"]))
        self.txt_mach_xmax.setText(str(m["x_limit"]))
        self.txt_mach_ymax.setText(str(m["y_limit"]))
        self.cmb_mach_post.setCurrentText(m["post_processor"])

    # ==============================================================================
    # PROJECT SERIALIZATION LOAD/SAVE
    # ==============================================================================
    def on_operations_changed(self):
        self.project.perform_autosave()
        self.sync_dimensions()

    def load_project_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Velora Project", "", "Project Files (*.vproj)")
        if not path:
            return
        try:
            self.project.load_from_file(path)
            self.stack_widget.set_project(self.project)
            self.txt_stock_x.setText(str(self.project.stock_x))
            self.txt_stock_y.setText(str(self.project.stock_y))
            self.txt_depth_z.setText(str(self.project.max_depth))
            self.chk_aspect.setChecked(self.project.preserve_aspect)
            self.chk_invert.setChecked(self.project.invert_check)
            if hasattr(self, "cmb_axis_orient"):
                self.cmb_axis_orient.setCurrentIndex(1 if self.project.swap_axes else 0)
            if hasattr(self, "chk_retract"):
                self.chk_retract.setChecked(self.project.retract_between_passes)
            if hasattr(self, "cmb_geom_mode"):
                mode_idx = 1 if self.project.toolpath_geometry_mode == "Geometry Aware" else 0
                self.cmb_geom_mode.setCurrentIndex(mode_idx)
            self.cmb_exp_mode.setCurrentText(self.project.export_mode)
            
            # Load project heightmap image
            if self.project.image_path and os.path.exists(self.project.image_path):
                self.pil_image = Image.open(self.project.image_path)
                self.lbl_image_status.setText(f"Heightmap Depth: {os.path.basename(self.project.image_path)}")
                self.heightmap_arr = np.array(self.pil_image.convert("L"))
                self.canvas.set_heightmap(self.pil_image)
                
            self.refresh_base_color_ui()
            if hasattr(self, "opt_view"):
                self.opt_view.set_project(self.project)
            if hasattr(self, "curve_view"):
                self.curve_view.set_project(self.project)
            self.update_preprocessed_images()
            self.canvas.set_stock_dimensions(self.project.stock_x, self.project.stock_y)
            self.log(f"[SUCCESS] Opened CAM project file: {os.path.basename(path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error Loading", f"Could not load project: {str(e)}")

    def save_project_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Velora Project", "", "Project Files (*.vproj)")
        if not path:
            return
        try:
            self.sync_dimensions()
            self.project.export_mode = self.cmb_exp_mode.currentText()
            self.project.save_to_file(path)
            self.log(f"[SUCCESS] Saved project file: {os.path.basename(path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"Could not save project: {str(e)}")

    def check_autosave_recovery(self):
        if self.project.check_recovery():
            ret = QMessageBox.question(
                self, "Unsaved Session Detected",
                "Velora CNC detected an unsaved previous session that crashed or closed. Recover it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                self.project.recover_session()
                self.stack_widget.refresh_list()
                self.log("[SUCCESS] Session successfully recovered from autosave cache!")

    def trigger_undo(self):
        if self.project.undo():
            self.stack_widget.refresh_list()
            self.refresh_base_color_ui()
            self.log("[INFO] Undid previous parameter change.")
            self.sync_dimensions()

    def trigger_redo(self):
        if self.project.redo():
            self.stack_widget.refresh_list()
            self.refresh_base_color_ui()
            self.log("[INFO] Redid previously reverted parameter change.")
            self.sync_dimensions()

    def arr_to_pixmap(self, arr):
        h, w = arr.shape
        arr_u8 = np.clip(arr, 0, 255).astype(np.uint8)
        bytes_data = arr_u8.tobytes()
        q_img = QImage(bytes_data, w, h, w, QImage.Format_Grayscale8)
        return QPixmap.fromImage(q_img.copy())

    def update_preprocessed_images(self):
        if self.heightmap_arr is None:
            return
            
        try:
            self.processed_arr, raw_base_mask, base_mask, clean_flat = CAMEngine.optimize_surface(
                self.heightmap_arr, self.project
            )
            
            # Use size of toolpath canvas or fixed size for preview scaling
            scaled_w = max(400, self.canvas.width())
            scaled_h = max(400, self.canvas.height())
            
            # 1. Original Grayscale Image
            pm_orig = self.arr_to_pixmap(self.heightmap_arr)
            self.lbl_preview_orig.setPixmap(pm_orig.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            # 2. Detected Base (RGB Overlay)
            h, w = self.heightmap_arr.shape
            base_rgb = np.stack([self.heightmap_arr]*3, axis=-1)
            base_rgb[base_mask] = [255, 60, 60] # highlight base in red
            bytes_data = base_rgb.tobytes()
            q_img = QImage(bytes_data, w, h, w*3, QImage.Format_RGB888)
            pm_base = QPixmap.fromImage(q_img.copy())
            self.lbl_preview_base.setPixmap(pm_base.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            # 3. Flattened & Cleaned Result
            pm_flat = self.arr_to_pixmap(self.processed_arr)
            self.lbl_preview_flat.setPixmap(pm_flat.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            # 4. Difference View
            diff = np.abs(self.processed_arr.astype(float) - self.heightmap_arr.astype(float))
            diff_scaled = np.clip(diff * 5.0, 0.0, 255.0).astype(np.uint8)
            diff_rgb = np.zeros((h, w, 3), dtype=np.uint8)
            bg = (self.heightmap_arr.astype(float) * 0.3).astype(np.uint8)
            diff_rgb[:, :, 1] = bg
            diff_rgb[:, :, 2] = bg
            mask_changed = diff_scaled > 0
            diff_rgb[mask_changed, 0] = np.maximum(diff_rgb[mask_changed, 0], diff_scaled[mask_changed])
            
            bytes_data_diff = diff_rgb.tobytes()
            q_img_diff = QImage(bytes_data_diff, w, h, w*3, QImage.Format_RGB888)
            pm_diff = QPixmap.fromImage(q_img_diff.copy())
            self.lbl_preview_diff.setPixmap(pm_diff.scaled(
                scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
            
            self.compute_geometry_visualizations()
            
        except Exception as e:
            self.log(f"[ERROR] Preprocessing preview update failed: {str(e)}")

    def on_optimization_params_changed(self):
        self.update_preprocessed_images()
        # Mark all operations as dirty so they recompile with the updated surface
        for op in self.project.operations:
            op["dirty"] = True
        self.stack_widget.refresh_list()
        self.project.perform_autosave()

    def on_curve_params_changed(self):
        # Mark all operations as dirty so they recompile with the updated curve
        for op in self.project.operations:
            op["dirty"] = True
        self.stack_widget.refresh_list()
        self.project.perform_autosave()
        self.update_preprocessed_images()

    def closeEvent(self, event):
        # Clean recovery cache file upon graceful exit
        try:
            path = self.project.get_autosave_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        event.accept()
