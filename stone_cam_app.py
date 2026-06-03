import os
import sys
import json
import time
import numpy as np
from PIL import Image, ImageFilter

from PySide6.QtCore import Qt, QSize, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QColor, QPalette, QPixmap, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QTextEdit, QProgressBar, QFileDialog, QScrollArea, QFrame, QDialog,
    QDialogButtonBox, QMessageBox, QSlider, QTabWidget, QGroupBox
)

# ==============================================================================
# CLICKABLE LABEL FOR IMAGE COLOR SELECTING
# ==============================================================================
class ClickableLabel(QLabel):
    clicked_pos = Signal(int, int, Qt.MouseButton)
    
    def mousePressEvent(self, event):
        self.clicked_pos.emit(event.x(), event.y(), event.button())
        super().mousePressEvent(event)


# ==============================================================================
# INDUSTRIAL DARK MODE STYLE SHEET
# ==============================================================================
DARK_STYLE = """
QMainWindow {
    background-color: #1a1a1f;
}
QWidget {
    color: #e0e0e6;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QLabel {
    font-weight: 500;
}
QFrame.Card {
    background-color: #24242d;
    border: 1px solid #363645;
    border-radius: 8px;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #363645;
    border-radius: 6px;
    margin-top: 15px;
    padding-top: 15px;
    background-color: #24242d;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #0098ff;
}
QLineEdit, QComboBox {
    background-color: #1e1e24;
    border: 1px solid #3a3a4c;
    border-radius: 4px;
    padding: 5px;
    color: #f0f0f5;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #0098ff;
}
QPushButton {
    background-color: #323242;
    border: 1px solid #4a4a5e;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
    color: #f0f0f5;
}
QPushButton:hover {
    background-color: #424256;
    border: 1px solid #5a5a75;
}
QPushButton:pressed {
    background-color: #282836;
}
QPushButton.Primary {
    background-color: #007acc;
    border: 1px solid #0098ff;
}
QPushButton.Primary:hover {
    background-color: #008be6;
}
QPushButton.Primary:pressed {
    background-color: #0066aa;
}
QPushButton.Danger {
    background-color: #cc3333;
    border: 1px solid #ff4444;
}
QPushButton.Danger:hover {
    background-color: #e63939;
}
QProgressBar {
    border: 1px solid #3a3a4c;
    border-radius: 4px;
    text-align: center;
    background-color: #1e1e24;
}
QProgressBar::chunk {
    background-color: #0098ff;
    border-radius: 3px;
}
QTextEdit {
    background-color: #141418;
    border: 1px solid #282835;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #a0a0b0;
    border-radius: 4px;
}
QScrollBar:vertical {
    border: none;
    background: #1a1a1f;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #424256;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #0098ff;
}
QTabWidget::pane {
    border: 1px solid #363645;
    background-color: #24242d;
    border-radius: 4px;
}
QTabBar::tab {
    background-color: #1e1e24;
    border: 1px solid #363645;
    border-bottom: none;
    padding: 6px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #a0a0b0;
}
QTabBar::tab:selected {
    background-color: #24242d;
    color: #e0e0e6;
    border-bottom: 2px solid #0098ff;
}
"""

# ==============================================================================
# TOOL LIBRARY DIALOG
# ==============================================================================
class ToolDialog(QDialog):
    def __init__(self, parent=None, tool_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add / Edit Tool Specifications")
        self.setMinimumWidth(400)
        self.setStyleSheet(DARK_STYLE)
        
        self.layout = QVBoxLayout(self)
        
        self.grid = QGridLayout()
        self.layout.addLayout(self.grid)
        
        # Tool Name
        self.grid.addWidget(QLabel("Tool Name:"), 0, 0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. LOXA CZ10.3-60(120)")
        self.grid.addWidget(self.name_input, 0, 1)
        
        # Tool Type
        self.grid.addWidget(QLabel("Tool Type:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Tapered Ball Nose", "Ball Nose", "Flat End Mill", "V-Bit"])
        self.grid.addWidget(self.type_combo, 1, 1)
        
        # Tip Diameter (mm)
        self.grid.addWidget(QLabel("Tip Diameter (mm):"), 2, 0)
        self.tip_input = QLineEdit("3.0")
        self.grid.addWidget(self.tip_input, 2, 1)
        
        # Ball Radius (mm)
        self.grid.addWidget(QLabel("Ball Radius (mm):"), 3, 0)
        self.radius_input = QLineEdit("1.5")
        self.grid.addWidget(self.radius_input, 3, 1)
        
        # Max Diameter (mm)
        self.grid.addWidget(QLabel("Max Diameter (mm):"), 4, 0)
        self.max_dia_input = QLineEdit("10.0")
        self.grid.addWidget(self.max_dia_input, 4, 1)
        
        # Tool Length (mm)
        self.grid.addWidget(QLabel("Tool Length (mm):"), 5, 0)
        self.length_input = QLineEdit("60.0")
        self.grid.addWidget(self.length_input, 5, 1)
        
        # Cutting Length (mm)
        self.grid.addWidget(QLabel("Cutting Length (mm):"), 6, 0)
        self.cut_input = QLineEdit("25.0")
        self.grid.addWidget(self.cut_input, 6, 1)
        
        # Notes
        self.grid.addWidget(QLabel("Included/Taper Angle (deg):"), 7, 0)
        self.angle_input = QLineEdit("0.0")
        self.grid.addWidget(self.angle_input, 7, 1)
        
        self.grid.addWidget(QLabel("Notes:"), 8, 0)
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notes or manufacturer brand...")
        self.grid.addWidget(self.notes_input, 8, 1)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
        # Prepopulate if editing
        if tool_data:
            self.name_input.setText(str(tool_data.get("name", "")))
            self.type_combo.setCurrentText(str(tool_data.get("type", "Tapered Ball Nose")))
            self.tip_input.setText(str(tool_data.get("tip_diameter", "3.0")))
            self.radius_input.setText(str(tool_data.get("ball_radius", "1.5")))
            self.max_dia_input.setText(str(tool_data.get("max_diameter", "10.0")))
            self.length_input.setText(str(tool_data.get("tool_length", "60.0")))
            self.cut_input.setText(str(tool_data.get("cutting_length", "25.0")))
            self.angle_input.setText(str(tool_data.get("taper_angle", "0.0")))
            self.notes_input.setText(str(tool_data.get("notes", "")))
            
    def get_tool_data(self):
        try:
            return {
                "name": self.name_input.text().strip() or "Unnamed Tool",
                "type": self.type_combo.currentText(),
                "tip_diameter": float(self.tip_input.text() or 0.0),
                "ball_radius": float(self.radius_input.text() or 0.0),
                "max_diameter": float(self.max_dia_input.text() or 0.0),
                "tool_length": float(self.length_input.text() or 0.0),
                "cutting_length": float(self.cut_input.text() or 0.0),
                "taper_angle": float(self.angle_input.text() or 0.0),
                "notes": self.notes_input.text().strip()
            }
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Please ensure all dimensional values are numbers.")
            return None


# ==============================================================================
# G-CODE GENERATOR BACKGROUND WORKER
# ==============================================================================
class ModalWriter:
    def __init__(self, file_handle, min_xy=0.02, min_z=0.03):
        self.f = file_handle
        self.min_xy = min_xy
        self.min_z = min_z
        self.active_g = None  # None, "G00" or "G01"
        self.active_f = None  # Active feedrate
        self.last_x = None
        self.last_y = None
        self.last_z = None
        self.g0_count = 0
        self.g1_count = 0
        self.redundant_coords_count = 0
        self.total_lines_written = 0
        self.total_z_travel = 0.0
        self.z_retracts_count = 0
        self.z_plunges_count = 0
        
    def write_comment(self, txt):
        self.f.write(f"({txt})\n")
        self.total_lines_written += 1
        
    def write_raw_line(self, line):
        self.f.write(line + "\n")
        self.total_lines_written += 1
        
    def write_move(self, g_cmd, x=None, y=None, z=None, f_val=None):
        # 1. Apply minimum movement filter
        dx = abs(x - self.last_x) if (x is not None and self.last_x is not None) else 999.0
        dy = abs(y - self.last_y) if (y is not None and self.last_y is not None) else 999.0
        dz = abs(z - self.last_z) if (z is not None and self.last_z is not None) else 999.0
        
        # Check if coordinates have changed significantly
        change_xy = (x is not None and (self.last_x is None or dx >= self.min_xy)) or \
                    (y is not None and (self.last_y is None or dy >= self.min_xy))
        change_z = (z is not None and (self.last_z is None or dz >= self.min_z))
        
        if not change_xy and not change_z and (f_val is None or f_val == self.active_f) and g_cmd == self.active_g:
            self.redundant_coords_count += 1
            return # skip redundant move
            
        # Update Z travel statistics before saving last_z
        if z is not None and self.last_z is not None and dz >= self.min_z:
            self.total_z_travel += dz
            if z > self.last_z:
                self.z_retracts_count += 1
            elif z < self.last_z:
                self.z_plunges_count += 1
                
        parts = []
        # G00/G01 modal command output
        if g_cmd != self.active_g:
            parts.append(g_cmd)
            self.active_g = g_cmd
            
        # Modal X, Y, Z coordinates output (only output changed values)
        if x is not None and (self.last_x is None or dx >= self.min_xy):
            parts.append(f"X{x:.3f}")
            self.last_x = x
        if y is not None and (self.last_y is None or dy >= self.min_xy):
            parts.append(f"Y{y:.3f}")
            self.last_y = y
        if z is not None and (self.last_z is None or dz >= self.min_z):
            parts.append(f"Z{z:.3f}")
            self.last_z = z
            
        # Modal feedrate output
        if f_val is not None and f_val != self.active_f:
            parts.append(f"F{f_val:.0f}")
            self.active_f = f_val
            
        if parts:
            line = " ".join(parts)
            self.f.write(line + "\n")
            self.total_lines_written += 1
            if g_cmd == "G00":
                self.g0_count += 1
            elif g_cmd == "G01":
                self.g1_count += 1


import traceback
import heapq

class CAMWorker(QThread):
    # progress_signal params: stage, percent, row, moves, size_kb, elapsed_time
    progress_signal = Signal(str, int, int, int, int, float)
    log_signal = Signal(str)
    finished_signal = Signal(bool, str, dict) # success, error_msg, stats_dict
    
    def __init__(self, params, arr, min_x, max_x, min_y, max_y, carving_w, carving_h, offset_x, offset_y, scaled_w, scaled_h, forbidden_mask):
        super().__init__()
        self.params = params
        self.arr = arr
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.carving_w = carving_w
        self.carving_h = carving_h
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.scaled_w = scaled_w
        self.scaled_h = scaled_h
        self.forbidden_mask = forbidden_mask
        self.is_cancelled = False
        
    def cancel(self):
        self.is_cancelled = True


    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            self._run_safe()
        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"[ERROR] Uncaught background thread error:\n{tb}")
            stats = {
                "total_raw_points": 1,
                "simplified_points": 0,
                "g0_moves": 0,
                "g1_moves": 0,
                "redundant_points_filtered": 0,
                "simplification_percentage": 0.0,
                "final_file_size_kb": 0,
                "long_rapid_moves_count": 0,
                "violations_detected": 0,
                "elapsed_time": 0.0
            }
            self.finished_signal.emit(False, str(e), stats)

    def _run_safe(self):
        # Stats collected
        stats = {
            "total_raw_points": 0,
            "simplified_points": 0,
            "g0_moves": 0,
            "g1_moves": 0,
            "redundant_points_filtered": 0,
            "simplification_percentage": 0.0,
            "final_file_size_kb": 0,
            "long_rapid_moves_count": 0,
            "violations_detected": 0,
            "elapsed_time": 0.0
        }
        
        start_time = time.time()
        
        # Local aliases for simple variable access from params dict
        p = self.params
        stock_x = p["stock_x"]
        stock_y = p["stock_y"]
        max_depth = p["max_depth"]
        spindle_rpm = p["spindle_rpm"]
        feed_xy = p["feed_xy"]
        feed_z = p["feed_z"]
        feed_plunge = p["feed_plunge"]
        safe_z = p["safe_z"]
        zero_point = p["zero_point"]
        preserve_aspect = p["preserve_aspect"]
        swap_axes = p["swap_axes"]
        one_way = p["one_way"]
        min_z_threshold = p["min_z_threshold"]
        is_nogo = p["is_nogo"]
        tool_type = p["tool_type"]
        tool_params = p["tool_params"]
        file_path = p["file_path"]
        do_roughing = p["do_roughing"]
        do_finishing = p["do_finishing"]
        rough_depth = p["rough_depth"]
        rough_allowance = p["rough_allowance"]
        rough_stepover = p["rough_stepover"]
        stepover = p["stepover"]
        resol_x = p["resol_x"]
        min_xy = p["min_xy_movement"]
        min_z = p["min_z_movement"]
        diagnostic_mode = p["diagnostic_mode"]
        
        # Determine RDP simplification tolerance
        rdp_tol = 0.02
        sim_preset = p["simplification_preset"]
        if sim_preset == 0: # Safe
            rdp_tol = 0.01
        elif sim_preset == 1: # Normal
            rdp_tol = 0.03
        elif sim_preset == 2: # Aggressive
            rdp_tol = 0.05
        elif sim_preset == 3: # None
            rdp_tol = 0.0
            
        # Tool tip radii for offset Probe
        tool_tip_diameter = tool_params.get("tip_diameter", 3.0)
        tool_ball_radius = tool_params.get("ball_radius", 1.5)
        tool_max_diameter = tool_params.get("max_diameter", 10.0)

        # Define localized Z value getter
        def get_surface_z(x, y):
            if preserve_aspect:
                cx = x - self.offset_x
                cy = y - self.offset_y
                if cx < 0 or cx >= self.scaled_w or cy < 0 or cy >= self.scaled_h:
                    return -max_depth
                px = self.min_x + (cx / self.scaled_w) * self.carving_w
                py = self.min_y - (cy / self.scaled_h) * self.carving_h
            else:
                px = (x / stock_x) * (self.carving_w - 1)
                py = (self.carving_h - 1) - (y / stock_y) * (self.carving_h - 1)
                
            px = max(0.0, min(float(self.carving_w - 1), px))
            py = max(0.0, min(float(self.carving_h - 1), py))
            
            x0 = int(np.floor(px))
            x1 = min(self.carving_w - 1, x0 + 1)
            y0 = int(np.floor(py))
            y1 = min(self.carving_h - 1, y0 + 1)
            
            dx = px - x0
            dy = py - y0
            
            v00 = self.arr[y0, x0]
            v10 = self.arr[y0, x1]
            v01 = self.arr[y1, x0]
            v11 = self.arr[y1, x1]
            
            val = (1.0 - dx) * (1.0 - dy) * v00 + dx * (1.0 - dy) * v10 + (1.0 - dx) * dy * v01 + dx * dy * v11
            
            # Scaled base color Z logic
            base_color = p.get("base_color", None)
            invert_check = p.get("invert_check", False)
            
            if base_color is not None:
                # Protect against division by zero if base color is pure white or black
                if invert_check:
                    # Inverted mode: Base Color is the highest (0.0), pure black (0) is the deepest (-max_depth)
                    if base_color <= 0.0:
                        z_val = -max_depth * (1.0 - val / 255.0)
                    else:
                        if val >= base_color:
                            z_val = 0.0
                        elif val <= 0.0:
                            z_val = -max_depth
                        else:
                            factor = val / float(base_color)
                            z_val = -max_depth * (1.0 - factor)
                else:
                    # Standard mode: Base Color is the deepest (-max_depth), pure white (255) is the highest (0.0)
                    if base_color >= 255.0:
                        z_val = -max_depth * (1.0 - val / 255.0)
                    else:
                        if val <= base_color:
                            z_val = -max_depth
                        elif val >= 255.0:
                            z_val = 0.0
                        else:
                            factor = (val - base_color) / float(255.0 - base_color)
                            z_val = -max_depth * (1.0 - factor)
            else:
                # Default standard 0-255 scaling
                z_val = -max_depth * (1.0 - val / 255.0)
                
            return z_val

        def transform_xy(raw_x, raw_y):
            if swap_axes:
                tx, ty = raw_y, raw_x
                sx, sy = stock_y, stock_x
            else:
                tx, ty = raw_x, raw_y
                sx, sy = stock_x, stock_y
                
            if zero_point == 0:   # Front-Left
                return tx, ty
            elif zero_point == 1: # Front-Right
                return tx - sx, ty
            elif zero_point == 2: # Back-Left
                return tx, ty - sy
            elif zero_point == 3: # Back-Right
                return tx - sx, ty - sy
            elif zero_point == 4: # Center
                return tx - (sx / 2.0), ty - (sy / 2.0)
            return tx, ty

        def invert_transform(tx, ty):
            if swap_axes:
                sx, sy = stock_y, stock_x
            else:
                sx, sy = stock_x, stock_y
                
            if zero_point == 0:   # Front-Left
                tx_raw, ty_raw = tx, ty
            elif zero_point == 1: # Front-Right
                tx_raw, ty_raw = tx + sx, ty
            elif zero_point == 2: # Back-Left
                tx_raw, ty_raw = tx, ty + sy
            elif zero_point == 3: # Back-Right
                tx_raw, ty_raw = tx + sx, ty + sy
            elif zero_point == 4: # Center
                tx_raw, ty_raw = tx + (sx / 2.0), ty + (sy / 2.0)
            else:
                tx_raw, ty_raw = tx, ty
                
            if swap_axes:
                x, y = ty_raw, tx_raw
            else:
                x, y = tx_raw, ty_raw
            return x, y

        def get_tool_profile_z_offset(ttype, r, params):
            if ttype == "Flat End Mill":
                R_max = params.get("tip_diameter", 3.0) / 2.0
                if r <= R_max:
                    return 0.0
                return 9999.0
            elif ttype == "Ball Nose":
                R_ball = params.get("ball_radius", 1.5)
                R_max = params.get("tip_diameter", 3.0) / 2.0
                if r <= R_ball:
                    return R_ball - np.sqrt(max(0.0, R_ball**2 - r**2))
                elif r <= R_max:
                    return R_ball
                return 9999.0
            elif ttype == "V-Bit":
                R_tip = params.get("tip_diameter", 0.0) / 2.0
                R_max = params.get("max_diameter", 10.0) / 2.0
                angle = params.get("taper_angle", 60.0)
                theta = np.radians(angle / 2.0)
                if r <= R_tip:
                    return 0.0
                elif r <= R_max:
                    return (r - R_tip) / max(1e-5, np.tan(theta))
                return 9999.0
            elif ttype == "Tapered Ball Nose":
                R_tip = params.get("ball_radius", 1.5)
                R_max = params.get("max_diameter", 10.0) / 2.0
                angle = params.get("taper_angle", 10.0)
                theta = np.radians(angle)
                r_tangent = R_tip * np.cos(theta)
                z_tangent = R_tip - R_tip * np.sin(theta)
                if r <= r_tangent:
                    return R_tip - np.sqrt(max(0.0, R_tip**2 - r**2))
                elif r <= R_max:
                    return z_tangent + (r - r_tangent) / max(1e-5, np.tan(theta))
                return 9999.0
            return 0.0

        # Precompute the search grid and corresponding offsets for the active tool
        if tool_type == "Flat End Mill":
            R_max = tool_tip_diameter / 2.0
        elif tool_type == "Ball Nose":
            R_max = tool_tip_diameter / 2.0
        else:
            R_max = tool_max_diameter / 2.0
        R_max = max(0.1, R_max)
        search_step = max(0.1, min(0.5, R_max / 8.0))
        search_range = np.arange(-R_max, R_max + search_step, search_step)
        
        grid_dx, grid_dy = np.meshgrid(search_range, search_range)
        grid_dx = grid_dx.flatten()
        grid_dy = grid_dy.flatten()
        grid_r = np.sqrt(grid_dx**2 + grid_dy**2)
        
        # Filter to only keep coordinates inside R_max
        mask = grid_r <= R_max
        grid_dx = grid_dx[mask]
        grid_dy = grid_dy[mask]
        grid_r = grid_r[mask]
        
        # Precompute z_offsets
        grid_z_offsets = np.array([get_tool_profile_z_offset(tool_type, r, tool_params) for r in grid_r])
        # Only keep valid offsets (z_offset < 9000.0)
        valid_mask = grid_z_offsets < 9000.0
        grid_dx = grid_dx[valid_mask]
        grid_dy = grid_dy[valid_mask]
        grid_z_offsets = grid_z_offsets[valid_mask]

        # Vectorized surface Z height calculation
        def get_surface_z_vectorized(xs, ys):
            is_scalar = isinstance(xs, (int, float)) or np.isscalar(xs)
            if is_scalar:
                xs_arr = np.array([xs], dtype=float)
                ys_arr = np.array([ys], dtype=float)
            else:
                xs_arr = np.asanyarray(xs, dtype=float)
                ys_arr = np.asanyarray(ys, dtype=float)
                
            if preserve_aspect:
                cx = xs_arr - self.offset_x
                cy = ys_arr - self.offset_y
                in_bounds = (cx >= 0) & (cx < self.scaled_w) & (cy >= 0) & (cy < self.scaled_h)
                
                px = np.zeros_like(cx)
                py = np.zeros_like(cy)
                
                px[in_bounds] = self.min_x + (cx[in_bounds] / self.scaled_w) * self.carving_w
                py[in_bounds] = self.min_y - (cy[in_bounds] / self.scaled_h) * self.carving_h
            else:
                px = (xs_arr / stock_x) * (self.carving_w - 1)
                py = (self.carving_h - 1) - (ys_arr / stock_y) * (self.carving_h - 1)
                in_bounds = np.ones_like(px, dtype=bool)
                
            px = np.clip(px, 0.0, float(self.carving_w - 1))
            py = np.clip(py, 0.0, float(self.carving_h - 1))
            
            x0 = np.floor(px).astype(int)
            x1 = np.minimum(self.carving_w - 1, x0 + 1)
            y0 = np.floor(py).astype(int)
            y1 = np.minimum(self.carving_h - 1, y0 + 1)
            
            dx = px - x0
            dy = py - y0
            
            v00 = self.arr[y0, x0]
            v10 = self.arr[y0, x1]
            v01 = self.arr[y1, x0]
            v11 = self.arr[y1, x1]
            
            val = (1.0 - dx) * (1.0 - dy) * v00 + dx * (1.0 - dy) * v10 + (1.0 - dx) * dy * v01 + dx * dy * v11
            
            # Scaled base color Z logic
            base_color = p.get("base_color", None)
            invert_check = p.get("invert_check", False)
            
            if base_color is not None:
                if invert_check:
                    if base_color <= 0.0:
                        z_val = -max_depth * (1.0 - val / 255.0)
                    else:
                        z_val = np.zeros_like(val)
                        z_val[val >= base_color] = 0.0
                        z_val[val <= 0.0] = -max_depth
                        
                        middle = (val > 0.0) & (val < base_color)
                        if np.any(middle):
                            factor = val[middle] / float(base_color)
                            z_val[middle] = -max_depth * (1.0 - factor)
                else:
                    if base_color >= 255.0:
                        z_val = -max_depth * (1.0 - val / 255.0)
                    else:
                        z_val = np.zeros_like(val)
                        z_val[val <= base_color] = -max_depth
                        z_val[val >= 255.0] = 0.0
                        
                        middle = (val > base_color) & (val < 255.0)
                        if np.any(middle):
                            factor = (val[middle] - base_color) / float(255.0 - base_color)
                            z_val[middle] = -max_depth * (1.0 - factor)
            else:
                z_val = -max_depth * (1.0 - val / 255.0)
                
            if preserve_aspect:
                z_val[~in_bounds] = -max_depth
                
            return z_val[0] if is_scalar else z_val

        # Vectorized tool geometry compensated Z height
        def get_tool_compensated_z_array(xs, ys):
            N = len(xs)
            max_zs = np.full(N, -9999.0)
            
            for dx, dy, z_offset in zip(grid_dx, grid_dy, grid_z_offsets):
                local_xs = xs + dx
                local_ys = ys + dy
                z_surfs = get_surface_z_vectorized(local_xs, local_ys)
                tool_zs = z_surfs - z_offset
                max_zs = np.maximum(max_zs, tool_zs)
                
            return max_zs

        # Maintain single scalar query for any legacy/individual calls
        def get_tool_compensated_z(x, y):
            val = get_tool_compensated_z_array(np.array([x], dtype=float), np.array([y], dtype=float))
            return val[0]

        def is_forbidden_vectorized(xs, ys):
            is_scalar = isinstance(xs, (int, float)) or np.isscalar(xs)
            if is_scalar:
                xs_arr = np.array([xs], dtype=float)
                ys_arr = np.array([ys], dtype=float)
            else:
                xs_arr = np.asanyarray(xs, dtype=float)
                ys_arr = np.asanyarray(ys, dtype=float)
                
            if self.forbidden_mask is None:
                return np.zeros_like(xs_arr, dtype=bool)[0] if is_scalar else np.zeros_like(xs_arr, dtype=bool)
                
            if preserve_aspect:
                cx = xs_arr - self.offset_x
                cy = ys_arr - self.offset_y
                in_bounds = (cx >= 0) & (cx < self.scaled_w) & (cy >= 0) & (cy < self.scaled_h)
                
                px = np.zeros_like(cx)
                py = np.zeros_like(cy)
                
                px[in_bounds] = self.min_x + (cx[in_bounds] / self.scaled_w) * self.carving_w
                py[in_bounds] = self.min_y - (cy[in_bounds] / self.scaled_h) * self.carving_h
            else:
                px = (xs_arr / stock_x) * (self.carving_w - 1)
                py = (self.carving_h - 1) - (ys_arr / stock_y) * (self.carving_h - 1)
                in_bounds = np.ones_like(px, dtype=bool)
                
            px_idx = np.clip(px, 0.0, float(self.carving_w - 1)).astype(int)
            py_idx = np.clip(py, 0.0, float(self.carving_h - 1)).astype(int)
            
            mask_vals = self.forbidden_mask[py_idx, px_idx]
            if preserve_aspect:
                mask_vals[~in_bounds] = False
            return mask_vals[0] if is_scalar else mask_vals

        def is_forbidden(x, y):
            return is_forbidden_vectorized(x, y)

        def is_line_intersecting_forbidden(x1, y1, x2, y2):
            if self.forbidden_mask is None:
                return False
            dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            steps = max(2, int(np.ceil(dist / 0.5)))
            for step in range(steps + 1):
                t = step / steps
                sx = x1 + t * (x2 - x1)
                sy = y1 + t * (y2 - y1)
                if is_forbidden(sx, sy):
                    return True
            return False

        # Populate downsampled 2D grid for A* obstacle avoidance
        grid_size = 5.0 # mm grid cell size
        grid_cols = max(5, int(np.ceil(stock_x / grid_size)))
        grid_rows = max(5, int(np.ceil(stock_y / grid_size)))
        obstacle_grid = np.zeros((grid_rows, grid_cols), dtype=bool)
        for r in range(grid_rows):
            for c in range(grid_cols):
                gx = (c + 0.5) * grid_size
                gy = (r + 0.5) * grid_size
                obstacle_grid[r, c] = is_forbidden(gx, gy)

        def to_grid(gx, gy):
            c = int(np.floor(gx / grid_size))
            r = int(np.floor(gy / grid_size))
            return max(0, min(grid_cols - 1, c)), max(0, min(grid_rows - 1, r))

        def find_avoidance_path(start_xy, end_xy):
            sx, sy = start_xy
            ex, ey = end_xy
            
            def to_world(cell):
                col, row = cell
                x = (col + 0.5) * grid_size
                y = (row + 0.5) * grid_size
                return min(stock_x, max(0.0, x)), min(stock_y, max(0.0, y))
                
            start_cell = to_grid(sx, sy)
            end_cell = to_grid(ex, ey)
            
            if start_cell == end_cell:
                return [end_xy]
                
            open_set = []
            heapq.heappush(open_set, (0, start_cell))
            came_from = {}
            g_score = {start_cell: 0}
            
            def heuristic(c1, c2):
                dx = abs(c1[0] - c2[0])
                dy = abs(c1[1] - c2[1])
                return max(dx, dy) + 0.414 * min(dx, dy)
                
            found = False
            while open_set:
                if self.is_cancelled:
                    return []
                _, current = heapq.heappop(open_set)
                
                if current == end_cell:
                    found = True
                    break
                    
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                    neighbor = (current[0] + dx, current[1] + dy)
                    if 0 <= neighbor[0] < grid_cols and 0 <= neighbor[1] < grid_rows:
                        if obstacle_grid[neighbor[1], neighbor[0]]:
                            continue
                        # Diagonal step cost is 1.414, straight step cost is 1.0
                        step_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                        tentative_g = g_score[current] + step_cost
                        if neighbor not in g_score or tentative_g < g_score[neighbor]:
                            came_from[neighbor] = current
                            g_score[neighbor] = tentative_g
                            f_score = tentative_g + heuristic(neighbor, end_cell)
                            heapq.heappush(open_set, (f_score, neighbor))
                            
            if not found:
                self.log_signal.emit("[WARN] A* pathfinder blocked by No-Go Zone. Using direct path.")
                return [end_xy]
                
            grid_path = []
            curr = end_cell
            while curr in came_from:
                grid_path.append(curr)
                curr = came_from[curr]
            grid_path.reverse()
            
            world_path = []
            for cell in grid_path:
                world_path.append(to_world(cell))
                
            if world_path:
                world_path[-1] = end_xy
            return world_path

        def rdp_3d_compress(pts):
            if rdp_tol <= 0.0 or len(pts) < 3:
                return pts
            start, end = pts[0], pts[-1]
            line_vec = end - start
            line_len = np.linalg.norm(line_vec)
            
            if line_len < 1e-8:
                dists = np.linalg.norm(pts[1:-1] - start, axis=1)
            else:
                t = np.dot(pts[1:-1] - start, line_vec) / (line_len ** 2)
                t = np.clip(t, 0.0, 1.0)
                proj = start + t[:, np.newaxis] * line_vec
                dists = np.linalg.norm(pts[1:-1] - proj, axis=1)
                
            if len(dists) == 0:
                return pts
                
            max_idx = np.argmax(dists)
            max_dist = dists[max_idx]
            
            if max_dist > rdp_tol:
                split = max_idx + 1
                left = rdp_3d_compress(pts[:split+1])
                right = rdp_3d_compress(pts[split:])
                return np.vstack((left[:-1], right))
            else:
                return np.array([start, end])

        # Define output G-code file paths
        rough_path = file_path.replace(".tap", "_roughing.tap")
        if do_roughing:
            finish_path = file_path.replace(".tap", "_finishing.tap")
        else:
            finish_path = file_path
            
        # Clear files before starting
        for p_f in [rough_path, finish_path]:
            if os.path.exists(p_f):
                try:
                    os.remove(p_f)
                except Exception:
                    pass

        # -------------------------------------------------------------
        # A. ROUGHING PASS GENERATION (Single Clearance Layer)
        # -------------------------------------------------------------
        if do_roughing:
            self.log_signal.emit("Generating Roughing clearance pass G-code...")
            rough_tmp = rough_path + ".tmp"
            
            try:
                with open(rough_tmp, "w") as f_out:
                    mw = ModalWriter(f_out, min_xy=min_xy, min_z=min_z)
                    mw.write_comment("Velora CNC generated Roughing Pass (Developed by Eng. Bara Eiz - almaamoneiz@gmail.com)")
                    mw.write_comment(f"Tool: {tool_type} - {tool_tip_diameter}mm tip")
                    mw.write_raw_line(f"G90 G21 G17 (Absolute Coordinates, Metric)")
                    mw.write_raw_line(f"M03 S{spindle_rpm} (Spindle On CW)")
                    mw.write_raw_line(f"G00 Z{safe_z:.3f} (Retract to safe Z)")
                    
                    # Row-by-row calculations
                    y_coords = np.arange(0.0, stock_y + rough_stepover, rough_stepover)
                    y_coords = y_coords[y_coords <= stock_y]
                    x_coords = np.arange(0.0, stock_x + resol_x, resol_x)
                    x_coords = x_coords[x_coords <= stock_x]
                    
                    total_rows = len(y_coords)
                    chunk_size = 50
                    curr_raw_x, curr_raw_y = 0.0, 0.0
                    tool_at_safe_z = True
                    rough_segs_processed = 0
                    
                    # Modal state initial values
                    mw.write_move("G00", x=0.0, y=0.0, z=safe_z)
                    
                    # Row chunks
                    for chunk_idx in range(0, total_rows, chunk_size):
                        if self.is_cancelled:
                            break
                            
                        chunk_end = min(total_rows, chunk_idx + chunk_size)
                        for r_idx in range(chunk_idx, chunk_end):
                            y = y_coords[r_idx]
                            forward = (r_idx % 2 == 0) or one_way
                            x_run = x_coords if forward else x_coords[::-1]
                            
                            # Gather row segments
                            xs = np.array(x_run, dtype=float)
                            ys = np.full_like(xs, y)
                            
                            z_surfs = get_tool_compensated_z_array(xs, ys)
                            z_vals = np.maximum(z_surfs + rough_allowance, rough_depth)
                            z_vals = np.minimum(0.0, z_vals)
                            
                            if min_z_threshold > 0.0:
                                filtered_zs = np.copy(z_vals)
                                for i in range(1, len(filtered_zs)):
                                    if abs(filtered_zs[i] - filtered_zs[i-1]) < min_z_threshold:
                                        filtered_zs[i] = filtered_zs[i-1]
                                z_vals = filtered_zs
                                
                            txs, tys = transform_xy(xs, ys)
                            forbiddens = is_forbidden_vectorized(xs, ys)
                            
                            raw_line = []
                            for i in range(len(xs)):
                                raw_line.append((txs[i], tys[i], z_vals[i], forbiddens[i]))
                                stats["total_raw_points"] += 1
                                
                            # Group uncut segments (islands for this row)
                            segments = []
                            current_seg = []
                            for pt in raw_line:
                                if pt[3]: # forbidden zone
                                    if current_seg:
                                        segments.append(current_seg)
                                        current_seg = []
                                else:
                                    current_seg.append(pt[:3])
                            if current_seg:
                                segments.append(current_seg)
                                
                            # Output moves for each segment
                            for segment in segments:
                                compressed = rdp_3d_compress(np.array(segment))
                                stats["simplified_points"] += len(compressed)
                                
                                for idx_pt, (cx, cy, cz) in enumerate(compressed):
                                    if idx_pt == 0:
                                        raw_target_x, raw_target_y = invert_transform(cx, cy)
                                        
                                        # Decide if a Z retract is required
                                        retract_required = True
                                        is_viol = is_line_intersecting_forbidden(curr_raw_x, curr_raw_y, raw_target_x, raw_target_y)
                                        dist = np.sqrt((raw_target_x - curr_raw_x)**2 + (raw_target_y - curr_raw_y)**2)
                                        
                                        if not p.get("retract_between_passes", True):
                                            # Retract is disabled, check safety exceptions
                                            max_transition_dist = max(8.0, rough_stepover * 3.0)
                                            if not is_viol and dist <= max_transition_dist and rough_segs_processed > 0:
                                                retract_required = False
                                                
                                        if retract_required:
                                            if not tool_at_safe_z:
                                                mw.write_move("G00", z=safe_z)
                                                tool_at_safe_z = True
                                                
                                            # Sub-segment checking for rapids
                                            if is_nogo and is_viol:
                                                avoid_path = find_avoidance_path((curr_raw_x, curr_raw_y), (raw_target_x, raw_target_y))
                                                for ap_x, ap_y in avoid_path:
                                                    tap_x, tap_y = transform_xy(ap_x, ap_y)
                                                    mw.write_move("G00", x=tap_x, y=tap_y)
                                            else:
                                                # Check diagnostic warning for long rapid
                                                if dist > 150.0:
                                                    stats["long_rapid_moves_count"] += 1
                                                    self.log_signal.emit(f"[DIAG] Long rapid move detected: {dist:.1f}mm from ({curr_raw_x:.1f}, {curr_raw_y:.1f}) to ({raw_target_x:.1f}, {raw_target_y:.1f})")
                                                    
                                                tap_x, tap_y = transform_xy(raw_target_x, raw_target_y)
                                                mw.write_move("G00", x=tap_x, y=tap_y)
                                                
                                            mw.write_move("G01", z=cz, f_val=feed_plunge)
                                            tool_at_safe_z = False
                                        else:
                                            # Skip Z retract! Write a continuous cutting G01 transition move
                                            tap_x, tap_y = transform_xy(raw_target_x, raw_target_y)
                                            mw.write_move("G01", x=tap_x, y=tap_y, z=cz, f_val=feed_xy)
                                            tool_at_safe_z = False
                                    else:
                                        mw.write_move("G01", x=cx, y=cy, z=cz, f_val=feed_xy)
                                        
                                last_cx, last_cy = compressed[-1][0], compressed[-1][1]
                                curr_raw_x, curr_raw_y = invert_transform(last_cx, last_cy)
                                rough_segs_processed += 1
                                
                        # Update progress
                        percent = int(10 + (chunk_end / total_rows) * 40) # Roughing occupies 10-50%
                        elapsed = time.time() - start_time
                        moves = mw.g0_count + mw.g1_count
                        size_kb = int(mw.total_lines_written * 45 / 1024)
                        self.progress_signal.emit("Generating Roughing Pass...", percent, chunk_end, moves, size_kb, elapsed)
                        
                    # Footer for roughing
                    mw.write_move("G00", z=safe_z)
                    mw.write_comment("End of Roughing Pass")
                    
                # Atomic rename on success
                if not self.is_cancelled:
                    if os.path.exists(rough_path):
                        os.remove(rough_path)
                    os.rename(rough_tmp, rough_path)
                    self.log_signal.emit(f"[CAM] Roughing G-code streamed and validation passed: {rough_path}")
                else:
                    if os.path.exists(rough_tmp):
                        os.remove(rough_tmp)
            except Exception as e:
                self.log_signal.emit(f"[ERROR] Roughing pass failed: {str(e)}")
                raise e

        # -------------------------------------------------------------
        # B. FINISHING PASS GENERATION
        # -------------------------------------------------------------
        if do_finishing and not self.is_cancelled:
            self.log_signal.emit("Generating Finishing pass G-code...")
            finish_tmp = finish_path + ".tmp"
            
            try:
                with open(finish_tmp, "w") as f_out:
                    mw = ModalWriter(f_out, min_xy=min_xy, min_z=min_z)
                    mw.write_comment("Velora CNC generated Finishing Pass (Developed by Eng. Bara Eiz - almaamoneiz@gmail.com)")
                    mw.write_comment(f"Tool: {tool_type} - {tool_tip_diameter}mm tip")
                    mw.write_raw_line(f"G90 G21 G17 (Absolute Coordinates, Metric)")
                    mw.write_raw_line(f"M03 S{spindle_rpm} (Spindle On CW)")
                    mw.write_raw_line(f"G00 Z{safe_z:.3f} (Retract to safe Z)")
                    
                    # 1. Generate all scanline coords
                    raster_axis = p["raster_axis_combo"]
                    if raster_axis == 0: # Raster X
                        y_coords = np.arange(0.0, stock_y + stepover, stepover)
                        y_coords = y_coords[y_coords <= stock_y]
                        x_coords = np.arange(0.0, stock_x + resol_x, resol_x)
                        x_coords = x_coords[x_coords <= stock_x]
                    else: # Raster Y
                        x_coords = np.arange(0.0, stock_x + stepover, stepover)
                        x_coords = x_coords[x_coords <= stock_x]
                        y_coords = np.arange(0.0, stock_y + resol_x, resol_x)
                        y_coords = y_coords[y_coords <= stock_y]
                        
                    all_segments = []
                    
                    self.log_signal.emit("Scanning stock surface geometry...")
                    
                    # Scan rows/columns and group into uncompressed raw segments
                    if raster_axis == 0:
                        total_scans = len(y_coords)
                        for r_idx in range(total_scans):
                            if self.is_cancelled:
                                break
                            y = y_coords[r_idx]
                            forward = (r_idx % 2 == 0) or one_way
                            x_run = x_coords if forward else x_coords[::-1]
                            
                            xs = np.array(x_run, dtype=float)
                            ys = np.full_like(xs, y)
                            
                            z_surfs = get_tool_compensated_z_array(xs, ys)
                            z_vals = np.minimum(0.0, z_surfs)
                            
                            if min_z_threshold > 0.0:
                                filtered_zs = np.copy(z_vals)
                                for i in range(1, len(filtered_zs)):
                                    if abs(filtered_zs[i] - filtered_zs[i-1]) < min_z_threshold:
                                        filtered_zs[i] = filtered_zs[i-1]
                                z_vals = filtered_zs
                                
                            txs, tys = transform_xy(xs, ys)
                            forbiddens = is_forbidden_vectorized(xs, ys)
                            
                            raw_line = []
                            for i in range(len(xs)):
                                raw_line.append((txs[i], tys[i], z_vals[i], forbiddens[i]))
                                stats["total_raw_points"] += 1
                                
                            current_seg = []
                            for pt in raw_line:
                                if pt[3]: # forbidden zone
                                    if current_seg:
                                        all_segments.append(current_seg)
                                        current_seg = []
                                else:
                                    current_seg.append(pt[:3])
                            if current_seg:
                                all_segments.append(current_seg)
                                
                            if r_idx % 100 == 0:
                                percent = int(50 + (r_idx / total_scans) * 15) # Scanning occupies 50-65%
                                self.progress_signal.emit("Scanning Geometry...", percent, r_idx, 0, 0, time.time() - start_time)
                    else:
                        total_scans = len(x_coords)
                        for r_idx in range(total_scans):
                            if self.is_cancelled:
                                break
                            x = x_coords[r_idx]
                            forward = (r_idx % 2 == 0) or one_way
                            y_run = y_coords if forward else y_coords[::-1]
                            
                            ys = np.array(y_run, dtype=float)
                            xs = np.full_like(ys, x)
                            
                            z_surfs = get_tool_compensated_z_array(xs, ys)
                            z_vals = np.minimum(0.0, z_surfs)
                            
                            if min_z_threshold > 0.0:
                                filtered_zs = np.copy(z_vals)
                                for i in range(1, len(filtered_zs)):
                                    if abs(filtered_zs[i] - filtered_zs[i-1]) < min_z_threshold:
                                        filtered_zs[i] = filtered_zs[i-1]
                                z_vals = filtered_zs
                                
                            txs, tys = transform_xy(xs, ys)
                            forbiddens = is_forbidden_vectorized(xs, ys)
                            
                            raw_line = []
                            for i in range(len(ys)):
                                raw_line.append((txs[i], tys[i], z_vals[i], forbiddens[i]))
                                stats["total_raw_points"] += 1
                                
                            current_seg = []
                            for pt in raw_line:
                                if pt[3]: # forbidden zone
                                    if current_seg:
                                        all_segments.append(current_seg)
                                        current_seg = []
                                else:
                                    current_seg.append(pt[:3])
                            if current_seg:
                                all_segments.append(current_seg)
                                
                            if r_idx % 100 == 0:
                                percent = int(50 + (r_idx / total_scans) * 15)
                                self.progress_signal.emit("Scanning Geometry...", percent, r_idx, 0, 0, time.time() - start_time)

                    # 2. Compress all raw segments with RDP 3D compression
                    self.log_signal.emit("Compressing segments...")
                    compressed_segments = []
                    for idx_seg, seg in enumerate(all_segments):
                        if self.is_cancelled:
                            break
                        comp = rdp_3d_compress(np.array(seg))
                        compressed_segments.append(comp)
                        stats["simplified_points"] += len(comp)
                        
                        if idx_seg % 100 == 0:
                            percent = int(65 + (idx_seg / len(all_segments)) * 10) # Compression occupies 65-75%
                            self.progress_signal.emit("Compressing Toolpaths...", percent, idx_seg, 0, 0, time.time() - start_time)

                    # 3. Nearest-Neighbor traversal of segments for optimized Island-Based Machining
                    self.log_signal.emit(f"Executing Island-Based Machining for {len(compressed_segments)} toolpath segments...")
                    curr_raw_x, curr_raw_y = 0.0, 0.0
                    tool_at_safe_z = True
                    
                    # Modal state initial values
                    mw.write_move("G00", x=0.0, y=0.0, z=safe_z)
                    
                    total_segs = len(compressed_segments)
                    segs_processed = 0
                    
                    while compressed_segments and not self.is_cancelled:
                        # Find closest segment (start or end point)
                        best_idx = -1
                        best_dist = 999999.0
                        reverse_best = False
                        
                        # Nearest neighbor search
                        for i_seg, seg in enumerate(compressed_segments):
                            sx_world, sy_world = invert_transform(seg[0][0], seg[0][1])
                            dist_start = np.sqrt((sx_world - curr_raw_x)**2 + (sy_world - curr_raw_y)**2)
                            
                            ex_world, ey_world = invert_transform(seg[-1][0], seg[-1][1])
                            dist_end = np.sqrt((ex_world - curr_raw_x)**2 + (ey_world - curr_raw_y)**2)
                            
                            if dist_start < best_dist:
                                best_dist = dist_start
                                best_idx = i_seg
                                reverse_best = False
                                
                            if dist_end < best_dist:
                                best_dist = dist_end
                                best_idx = i_seg
                                reverse_best = True
                                
                        if best_idx == -1:
                            break
                            
                        # Pick the best segment and remove it
                        seg = compressed_segments.pop(best_idx)
                        if reverse_best:
                            seg = seg[::-1] # Reverse cutting direction
                            
                        # Perform rapid travel to start of segment
                        raw_target_x, raw_target_y = invert_transform(seg[0][0], seg[0][1])
                        
                        # Decide if a Z retract is required
                        retract_required = True
                        is_viol = is_line_intersecting_forbidden(curr_raw_x, curr_raw_y, raw_target_x, raw_target_y)
                        dist = np.sqrt((raw_target_x - curr_raw_x)**2 + (raw_target_y - curr_raw_y)**2)
                        
                        if not p.get("retract_between_passes", True):
                            # Retract is disabled, check if safety clearance allows skipping
                            max_transition_dist = max(8.0, stepover * 3.0)
                            if not is_viol and dist <= max_transition_dist and segs_processed > 0:
                                retract_required = False
                                
                        if retract_required:
                            if not tool_at_safe_z:
                                mw.write_move("G00", z=safe_z)
                                tool_at_safe_z = True
                                
                            # Sub-segment checking for rapids
                            if is_nogo and is_viol:
                                stats["violations_detected"] += 1
                                avoid_path = find_avoidance_path((curr_raw_x, curr_raw_y), (raw_target_x, raw_target_y))
                                for ap_x, ap_y in avoid_path:
                                    tap_x, tap_y = transform_xy(ap_x, ap_y)
                                    mw.write_move("G00", x=tap_x, y=tap_y)
                            else:
                                # Check diagnostic warning for long rapid
                                if dist > 150.0:
                                    stats["long_rapid_moves_count"] += 1
                                    self.log_signal.emit(f"[DIAG] Long rapid move detected: {dist:.1f}mm from ({curr_raw_x:.1f}, {curr_raw_y:.1f}) to ({raw_target_x:.1f}, {raw_target_y:.1f})")
                                    
                                tap_x, tap_y = transform_xy(raw_target_x, raw_target_y)
                                mw.write_move("G00", x=tap_x, y=tap_y)
                                
                            # Plunge and cut segment
                            mw.write_move("G01", z=seg[0][2], f_val=feed_plunge)
                            tool_at_safe_z = False
                        else:
                            # Skip Z retract! Write a continuous cutting G01 transition move
                            tap_x, tap_y = transform_xy(raw_target_x, raw_target_y)
                            mw.write_move("G01", x=tap_x, y=tap_y, z=seg[0][2], f_val=feed_xy)
                            tool_at_safe_z = False
                        
                        for idx_pt in range(1, len(seg)):
                            cx, cy, cz = seg[idx_pt][0], seg[idx_pt][1], seg[idx_pt][2]
                            mw.write_move("G01", x=cx, y=cy, z=cz, f_val=feed_xy)
                            
                        # Update current tool location
                        last_cx, last_cy = seg[-1][0], seg[-1][1]
                        curr_raw_x, curr_raw_y = invert_transform(last_cx, last_cy)
                        
                        segs_processed += 1
                        if segs_processed % 20 == 0:
                            percent = int(75 + (segs_processed / total_segs) * 23) # Machining occupies 75-98%
                            elapsed = time.time() - start_time
                            moves = mw.g0_count + mw.g1_count
                            size_kb = int(mw.total_lines_written * 45 / 1024)
                            self.progress_signal.emit("Machining Islands...", percent, segs_processed, moves, size_kb, elapsed)
                            
                    # Footer for finishing
                    mw.write_move("G00", z=safe_z)
                    mw.write_comment("End of Finishing Pass")
                    
                # Atomic rename on success
                if not self.is_cancelled:
                    if os.path.exists(finish_path):
                        os.remove(finish_path)
                    os.rename(finish_tmp, finish_path)
                    self.log_signal.emit(f"[CAM] Finishing G-code streamed and validation passed: {finish_path}")
                else:
                    if os.path.exists(finish_tmp):
                        os.remove(finish_tmp)
            except Exception as e:
                self.log_signal.emit(f"[ERROR] Finishing pass failed: {str(e)}")
                raise e

        # Validation statistics calculation
        elapsed_time = time.time() - start_time
        stats["elapsed_time"] = elapsed_time
        
        # Safe counts
        stats["g0_moves"] = mw.g0_count
        stats["g1_moves"] = mw.g1_count
        stats["redundant_points_filtered"] = mw.redundant_coords_count
        stats["total_raw_points"] = max(1, stats.get("total_raw_points", 0))
        stats["simplification_percentage"] = (1.0 - (stats["simplified_points"] / stats["total_raw_points"])) * 100.0
        
        # Z movement statistics
        stats["z_retracts_count"] = mw.z_retracts_count
        stats["z_plunges_count"] = mw.z_plunges_count
        stats["total_z_travel_distance"] = mw.total_z_travel
        
        # Calculate reductions and time saved dynamically
        total_potential_segments = segs_processed
        if do_roughing and 'rough_segs_processed' in locals():
            total_potential_segments += rough_segs_processed
        if total_potential_segments < 1:
            total_potential_segments = 1
            
        saved_retracts = max(0, total_potential_segments - mw.z_retracts_count)
        stats["z_movement_reduction_percent"] = (saved_retracts / total_potential_segments) * 100.0
        stats["estimated_time_saved_mins"] = (saved_retracts * 2.0 * safe_z / feed_plunge)
        
        # Calculate active sizes
        final_size = 0
        for p_f in [rough_path, finish_path]:
            if os.path.exists(p_f):
                final_size += os.path.getsize(p_f)
        stats["final_file_size_kb"] = int(final_size / 1024)
        
        if self.is_cancelled:
            # Cleanup temp files
            for p_t in [rough_path + ".tmp", finish_path + ".tmp"]:
                if os.path.exists(p_t):
                    try:
                        os.remove(p_t)
                    except Exception:
                        pass
            self.finished_signal.emit(False, "User Cancelled", stats)
        else:
            self.finished_signal.emit(True, "", stats)
class StoneCAMApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Velora CNC - 3D CNC Toolpath Engine")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(DARK_STYLE)
        
        # State variables
        self.input_image_path = None
        self.pil_original_image = None
        self.pil_processed_image = None
        self.tools_list = []
        self.tools_library_path = r"c:\Users\pc\Desktop\cnc\tools_library.json"
        
        # Color pickers & re-entrancy states
        self.base_color = None
        self.forbidden_color = None
        self.picker_mode = None
        self.is_generating = False
        
        # Debounce timer for preview updates to prevent freezing during fast typing
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.do_process_image_preview)
        
        self.init_ui()
        self.load_tool_library()
        self.log("Welcome to Velora CNC! Developed by Eng. Bara Eiz (almaamoneiz@gmail.com).")

    def init_ui(self):
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # ==============================================================================
        # LEFT CONTROL PANEL (Scrollable)
        # ==============================================================================
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setFixedWidth(420)
        
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        sidebar_layout.setSpacing(12)
        
        # Title Card
        title_card = QFrame()
        title_card.setObjectName("TitleCard")
        title_card.setStyleSheet("QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #005999, stop:1 #0098ff); border-radius: 8px; }")
        title_card_layout = QVBoxLayout(title_card)
        title_lbl = QLabel("VELORA CNC")
        title_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_lbl.setStyleSheet("color: #ffffff; font-weight: bold;")
        subtitle_lbl = QLabel("Developed by Eng. Bara Eiz")
        subtitle_lbl.setStyleSheet("color: #e2f2ff; font-weight: bold; font-size: 11px;")
        contact_lbl = QLabel("almaamoneiz@gmail.com")
        contact_lbl.setStyleSheet("color: #b3dcff; font-size: 10px;")
        title_card_layout.addWidget(title_lbl)
        title_card_layout.addWidget(subtitle_lbl)
        title_card_layout.addWidget(contact_lbl)
        sidebar_layout.addWidget(title_card)
        
        # --- Group 1: Image Import & Processing ---
        img_group = QGroupBox("1. Image Import & Processing")
        img_layout = QGridLayout(img_group)
        img_layout.setContentsMargins(12, 18, 12, 12)
        img_layout.setSpacing(8)
        
        self.btn_load_img = QPushButton("Import Depth Image")
        self.btn_load_img.setIconSize(QSize(16, 16))
        self.btn_load_img.clicked.connect(self.import_image)
        img_layout.addWidget(self.btn_load_img, 0, 0, 1, 2)
        
        img_layout.addWidget(QLabel("Image Downsampling:"), 1, 0)
        self.downsample_combo = QComboBox()
        self.downsample_combo.addItems(["1x (Full Resolution)", "2x (Fast)", "4x (Super Fast)", "8x (Draft)"])
        self.downsample_combo.setCurrentIndex(0) # Default 1x (Full Resolution) for maximum detail
        self.downsample_combo.currentIndexChanged.connect(self.process_image_preview)
        img_layout.addWidget(self.downsample_combo, 1, 1)
        
        self.invert_check = QCheckBox("Invert Relief Height (White = deepest)")
        self.invert_check.stateChanged.connect(self.process_image_preview)
        img_layout.addWidget(self.invert_check, 2, 0, 1, 2)
        
        img_layout.addWidget(QLabel("Gaussian Blur / Smoothing:"), 3, 0)
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setMinimum(0)
        self.blur_slider.setMaximum(10)
        self.blur_slider.setValue(0) # Default 0 (No blur/smoothing) for sharp details
        self.blur_slider.valueChanged.connect(self.process_image_preview)
        img_layout.addWidget(self.blur_slider, 3, 1)
        
        sidebar_layout.addWidget(img_group)
        
        # --- Group 1.5: Base & Protected Zones ---
        zone_group = QGroupBox("Base & Protected Zones")
        zone_layout = QGridLayout(zone_group)
        zone_layout.setContentsMargins(12, 18, 12, 12)
        zone_layout.setSpacing(8)
        
        self.btn_pick_base = QPushButton("Pick Base Color")
        self.btn_pick_base.clicked.connect(self.start_pick_base)
        zone_layout.addWidget(self.btn_pick_base, 0, 0)
        
        self.lbl_base_color = QLabel("Base Color: None")
        self.lbl_base_color.setStyleSheet("color: #a0a0b0;")
        zone_layout.addWidget(self.lbl_base_color, 0, 1)
        
        zone_layout.addWidget(QLabel("Base Flat Tolerance:"), 1, 0)
        self.base_tolerance_input = QLineEdit("5")
        self.base_tolerance_input.textChanged.connect(self.process_image_preview)
        zone_layout.addWidget(self.base_tolerance_input, 1, 1)
        
        zone_layout.addWidget(QLabel("Min Z Change (mm):"), 2, 0)
        self.min_z_input = QLineEdit("0.02")
        zone_layout.addWidget(self.min_z_input, 2, 1)
        
        self.btn_pick_forbidden = QPushButton("Pick Forbidden Color")
        self.btn_pick_forbidden.clicked.connect(self.start_pick_forbidden)
        zone_layout.addWidget(self.btn_pick_forbidden, 3, 0)
        
        self.lbl_forbidden_color = QLabel("Forbidden: None")
        self.lbl_forbidden_color.setStyleSheet("color: #a0a0b0;")
        zone_layout.addWidget(self.lbl_forbidden_color, 3, 1)
        
        zone_layout.addWidget(QLabel("Forbidden Tolerance:"), 4, 0)
        self.forbidden_tolerance_input = QLineEdit("10")
        self.forbidden_tolerance_input.textChanged.connect(self.process_image_preview)
        zone_layout.addWidget(self.forbidden_tolerance_input, 4, 1)
        
        zone_layout.addWidget(QLabel("Forbidden Area Offset (mm):"), 5, 0)
        self.forbidden_offset_input = QLineEdit("0.0")
        self.forbidden_offset_input.setToolTip("Positive values expand the protected area. Negative values shrink it.")
        self.forbidden_offset_input.textChanged.connect(self.process_image_preview)
        zone_layout.addWidget(self.forbidden_offset_input, 5, 1)
        
        zone_layout.addWidget(QLabel("Forbidden Area Behavior:"), 6, 0)
        self.forbidden_behavior_combo = QComboBox()
        self.forbidden_behavior_combo.addItem("Protected Area (Crossing Allowed)")
        self.forbidden_behavior_combo.addItem("No-Go Zone (No Crossing)")
        self.forbidden_behavior_combo.currentIndexChanged.connect(self.process_image_preview)
        zone_layout.addWidget(self.forbidden_behavior_combo, 6, 1)
        
        sidebar_layout.addWidget(zone_group)
        
        # --- Group 2: Workpiece Stock Setup ---
        stock_group = QGroupBox("2. Stock Workpiece Setup")
        stock_layout = QGridLayout(stock_group)
        stock_layout.setContentsMargins(12, 18, 12, 12)
        stock_layout.setSpacing(8)
        
        stock_layout.addWidget(QLabel("Workpiece Width X (mm):"), 0, 0)
        self.stock_x_input = QLineEdit("300.0")
        self.stock_x_input.textChanged.connect(self.update_live_estimates)
        stock_layout.addWidget(self.stock_x_input, 0, 1)
        
        stock_layout.addWidget(QLabel("Workpiece Length Y (mm):"), 1, 0)
        self.stock_y_input = QLineEdit("1000.0")
        self.stock_y_input.textChanged.connect(self.update_live_estimates)
        stock_layout.addWidget(self.stock_y_input, 1, 1)
        
        stock_layout.addWidget(QLabel("Maximum Relief Depth Z (mm):"), 2, 0)
        self.stock_z_input = QLineEdit("25.0")
        stock_layout.addWidget(self.stock_z_input, 2, 1)
        
        self.aspect_check = QCheckBox("Lock Aspect Ratio (Uniform Centering)")
        self.aspect_check.setChecked(True)
        stock_layout.addWidget(self.aspect_check, 3, 0, 1, 2)
        
        stock_layout.addWidget(QLabel("CNC Zero Point Origin:"), 4, 0)
        self.zero_point_combo = QComboBox()
        self.zero_point_combo.addItems([
            "Front-Left Corner (X0, Y0)",
            "Front-Right Corner (-X, Y)",
            "Back-Left Corner (X, -Y)",
            "Back-Right Corner (-X, -Y)",
            "Center (X-center, Y-center)"
        ])
        stock_layout.addWidget(self.zero_point_combo, 4, 1)
        
        sidebar_layout.addWidget(stock_group)
        
        # --- Group 3: Tool Library Selector ---
        tool_group = QGroupBox("3. Active Cutting Tool")
        tool_layout = QVBoxLayout(tool_group)
        tool_layout.setContentsMargins(12, 18, 12, 12)
        tool_layout.setSpacing(8)
        
        self.tool_combo = QComboBox()
        self.tool_combo.currentIndexChanged.connect(self.on_tool_selected)
        tool_layout.addWidget(self.tool_combo)
        
        btn_tool_layout = QHBoxLayout()
        self.btn_add_tool = QPushButton("Add New...")
        self.btn_add_tool.clicked.connect(self.add_tool)
        btn_tool_layout.addWidget(self.btn_add_tool)
        
        self.btn_edit_tool = QPushButton("Edit Spec")
        self.btn_edit_tool.clicked.connect(self.edit_tool)
        btn_tool_layout.addWidget(self.btn_edit_tool)
        
        self.btn_del_tool = QPushButton("Delete")
        self.btn_del_tool.clicked.connect(self.delete_tool)
        btn_tool_layout.addWidget(self.btn_del_tool)
        tool_layout.addLayout(btn_tool_layout)
        
        sidebar_layout.addWidget(tool_group)
        
        # --- Group 4: Feeds & Speeds ---
        feeds_group = QGroupBox("4. Feeds and Speeds")
        feeds_layout = QGridLayout(feeds_group)
        feeds_layout.setContentsMargins(12, 18, 12, 12)
        feeds_layout.setSpacing(8)
        
        feeds_layout.addWidget(QLabel("Spindle RPM:"), 0, 0)
        self.spindle_input = QLineEdit("24000")
        feeds_layout.addWidget(self.spindle_input, 0, 1)
        
        feeds_layout.addWidget(QLabel("XY Feedrate (mm/min):"), 1, 0)
        self.xy_feed_input = QLineEdit("3000")
        feeds_layout.addWidget(self.xy_feed_input, 1, 1)
        
        feeds_layout.addWidget(QLabel("Z Vertical Feedrate (mm/min):"), 2, 0)
        self.z_feed_input = QLineEdit("1500")
        feeds_layout.addWidget(self.z_feed_input, 2, 1)
        
        feeds_layout.addWidget(QLabel("Plunge Feedrate (mm/min):"), 3, 0)
        self.plunge_feed_input = QLineEdit("800")
        feeds_layout.addWidget(self.plunge_feed_input, 3, 1)
        
        feeds_layout.addWidget(QLabel("Safe Clearance Z (mm):"), 4, 0)
        self.safe_z_input = QLineEdit("20.0")
        feeds_layout.addWidget(self.safe_z_input, 4, 1)
        
        sidebar_layout.addWidget(feeds_group)
        
        # --- Group 5: Toolpath Parameters ---
        path_group = QGroupBox("5. Toolpath Strategy Settings")
        path_layout = QGridLayout(path_group)
        path_layout.setContentsMargins(12, 18, 12, 12)
        path_layout.setSpacing(8)
        
        path_layout.addWidget(QLabel("Finishing Stepover (mm):"), 0, 0)
        self.stepover_input = QLineEdit("0.5") # High detail default stepover for 3mm ball nose
        self.stepover_input.textChanged.connect(self.update_live_estimates)
        path_layout.addWidget(self.stepover_input, 0, 1)
        
        path_layout.addWidget(QLabel("Sampling Resolution X (mm):"), 1, 0)
        self.resol_x_input = QLineEdit("0.25") # Dense point sampling default along scanline
        self.resol_x_input.textChanged.connect(self.update_live_estimates)
        path_layout.addWidget(self.resol_x_input, 1, 1)
        
        path_layout.addWidget(QLabel("Path tolerance (RDP compression mm):"), 2, 0)
        self.tolerance_input = QLineEdit("0.02") # Tight tolerance default to retain crisp ornament features
        path_layout.addWidget(self.tolerance_input, 2, 1)
        
        path_layout.addWidget(QLabel("Raster Scan Axis:"), 3, 0)
        self.raster_axis_combo = QComboBox()
        self.raster_axis_combo.addItems(["Raster X (Horizontal lines)", "Raster Y (Vertical lines)"])
        path_layout.addWidget(self.raster_axis_combo, 3, 1)
        
        path_layout.addWidget(QLabel("Machining Direction:"), 4, 0)
        self.machining_mode_combo = QComboBox()
        self.machining_mode_combo.addItems(["One-Way Machining", "Two-Way Machining (Zigzag)"])
        self.machining_mode_combo.setCurrentIndex(1) # Default Two-Way
        path_layout.addWidget(self.machining_mode_combo, 4, 1)
        
        path_layout.addWidget(QLabel("Axis Orientation:"), 5, 0)
        self.axis_orientation_combo = QComboBox()
        self.axis_orientation_combo.addItems(["Standard (X=X, Y=Y)", "Swap X and Y (X=Y, Y=X)"])
        self.axis_orientation_combo.setCurrentIndex(0) # Default Standard
        path_layout.addWidget(self.axis_orientation_combo, 5, 1)
        
        self.rough_check = QCheckBox("Generate Roughing Clearance Pass")
        self.rough_check.setChecked(False)
        self.rough_check.stateChanged.connect(self.on_roughing_toggled)
        path_layout.addWidget(self.rough_check, 6, 0, 1, 2)
        
        # Single-pass roughing container
        self.rough_container = QWidget()
        rough_container_layout = QGridLayout(self.rough_container)
        rough_container_layout.setContentsMargins(0, 5, 0, 5)
        rough_container_layout.setSpacing(6)
        
        self.rough_depth_lbl = QLabel("Single-Pass Roughing Floor Depth (mm):")
        rough_container_layout.addWidget(self.rough_depth_lbl, 0, 0)
        self.rough_depth_input = QLineEdit("-24.0")
        rough_container_layout.addWidget(self.rough_depth_input, 0, 1)
        
        self.rough_allowance_lbl = QLabel("Finishing Allowance (mm):")
        rough_container_layout.addWidget(self.rough_allowance_lbl, 1, 0)
        self.rough_allowance_input = QLineEdit("1.0")
        rough_container_layout.addWidget(self.rough_allowance_input, 1, 1)
        
        self.rough_stepover_lbl = QLabel("Roughing Stepover (mm):")
        rough_container_layout.addWidget(self.rough_stepover_lbl, 2, 0)
        self.rough_stepover_input = QLineEdit("3.0")
        rough_container_layout.addWidget(self.rough_stepover_input, 2, 1)
        
        path_layout.addWidget(self.rough_container, 7, 0, 1, 2)
        
        self.on_roughing_toggled() # Hide inputs if roughing is disabled
        
        self.finish_check = QCheckBox("Generate High-Precision Finishing Pass")
        self.finish_check.setChecked(True)
        path_layout.addWidget(self.finish_check, 8, 0, 1, 2)
        
        path_layout.addWidget(QLabel("Simplification Preset:"), 9, 0)
        self.simplification_combo = QComboBox()
        self.simplification_combo.addItems([
            "Safe (0.01 mm)",
            "Normal (0.03 mm)",
            "Aggressive (0.05 mm)",
            "None (No Merging)"
        ])
        self.simplification_combo.setCurrentIndex(1) # Default Normal
        path_layout.addWidget(self.simplification_combo, 9, 1)
        
        path_layout.addWidget(QLabel("Min XY Movement (mm):"), 10, 0)
        self.min_xy_input = QLineEdit("0.02")
        path_layout.addWidget(self.min_xy_input, 10, 1)
        
        path_layout.addWidget(QLabel("Min Z Movement (mm):"), 11, 0)
        self.min_z_move_input = QLineEdit("0.03")
        path_layout.addWidget(self.min_z_move_input, 11, 1)
        
        self.retract_check = QCheckBox("Z Retract Between Passes")
        self.retract_check.setChecked(True)
        path_layout.addWidget(self.retract_check, 12, 0, 1, 2)
        
        self.diagnostic_check = QCheckBox("Enable Diagnostic Mode (.log file)")
        self.diagnostic_check.setChecked(False)
        path_layout.addWidget(self.diagnostic_check, 13, 0, 1, 2)
        
        sidebar_layout.addWidget(path_group)
        
        # Bottom spacer to prevent bloated stretching
        sidebar_layout.addStretch()
        
        scroll_area.setWidget(sidebar)
        main_layout.addWidget(scroll_area)
        
        # ==============================================================================
        # RIGHT PANEL (Previews, Logs, Export Controls)
        # ==============================================================================
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)
        
        # --- Previews Area ---
        tab_widget = QTabWidget()
        
        # Tab 1: Image Depth Preview
        self.tab_preview = QWidget()
        preview_layout = QVBoxLayout(self.tab_preview)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        
        self.canvas = ClickableLabel("Import an ornamental stone depth image to visualize rendering...")
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setStyleSheet("QLabel { background-color: #121216; border: 1px dashed #3a3a4c; border-radius: 6px; color: #6a6a7c; font-size: 14px; }")
        self.canvas.setMinimumSize(400, 350)
        self.canvas.clicked_pos.connect(self.on_canvas_clicked)
        preview_layout.addWidget(self.canvas)
        
        tab_widget.addTab(self.tab_preview, "Ornamental Depth Preview")
        right_panel.addWidget(tab_widget, 1)
        
        # --- Estimates & G-Code Export Control Card ---
        export_card = QFrame()
        export_card.setFrameShape(QFrame.StyledPanel)
        export_card.setFrameShadow(QFrame.Raised)
        export_card.setLineWidth(1)
        export_card.setObjectName("ExportCard")
        export_card.setStyleSheet("QFrame#ExportCard { background-color: #24242d; border: 1px solid #363645; border-radius: 8px; padding: 15px; }")
        
        export_layout = QVBoxLayout(export_card)
        
        # Estimates layout
        est_grid = QGridLayout()
        est_grid.setContentsMargins(0, 0, 0, 10)
        
        self.lbl_est_lines = QLabel("Estimated Scanlines: --")
        self.lbl_est_lines.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_est_lines.setStyleSheet("color: #c0c0d0;")
        est_grid.addWidget(self.lbl_est_lines, 0, 0)
        
        self.lbl_est_points = QLabel("Est. Total Raw Points: --")
        self.lbl_est_points.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_est_points.setStyleSheet("color: #c0c0d0;")
        est_grid.addWidget(self.lbl_est_points, 0, 1)
        
        self.lbl_est_size = QLabel("Estimated G-Code Size: --")
        self.lbl_est_size.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_est_size.setStyleSheet("color: #00ffaa;")
        est_grid.addWidget(self.lbl_est_size, 1, 0)
        
        self.lbl_warning = QLabel("")
        self.lbl_warning.setFont(QFont("Segoe UI", 10, QFont.Normal))
        self.lbl_warning.setStyleSheet("color: #ff9900;")
        est_grid.addWidget(self.lbl_warning, 1, 1)
        
        export_layout.addLayout(est_grid)
        
        # Generate Action layout
        btn_action_layout = QHBoxLayout()
        self.btn_compile = QPushButton("Compile Mach3 G-Code (.tap)")
        self.btn_compile.setEnabled(False)
        self.btn_compile.setFixedHeight(45)
        self.btn_compile.setObjectName("CompileBtn")
        self.btn_compile.setStyleSheet("QPushButton#CompileBtn { background-color: #007acc; font-size: 15px; border-radius: 6px; } QPushButton#CompileBtn:hover { background-color: #0098ff; }")
        self.btn_compile.clicked.connect(self.generate_cam_toolpaths)
        btn_action_layout.addWidget(self.btn_compile)
        export_layout.addLayout(btn_action_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        export_layout.addWidget(self.progress_bar)
        
        right_panel.addWidget(export_card)
        
        # --- Console Logs Area ---
        log_group = QGroupBox("System logs & G-code header inspect")
        log_layout = QVBoxLayout(log_group)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(150)
        log_layout.addWidget(self.console)
        
        right_panel.addWidget(log_group)
        main_layout.addLayout(right_panel, 2)

    # ==============================================================================
    # HELPER LOGGING
    # ==============================================================================
    def log(self, message):
        self.console.append(str(message))
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        QApplication.processEvents()

    # ==============================================================================
    # ROUGHING INTERFACE TOGGLE
    # ==============================================================================
    def on_roughing_toggled(self):
        enabled = self.rough_check.isChecked()
        self.rough_container.setVisible(enabled)

    # ==============================================================================
    # IMAGE IMPORT & PROCESSING PIPELINE
    # ==============================================================================
    def import_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Grayscale Ornamental Depth Map", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            try:
                self.input_image_path = file_path
                with Image.open(file_path) as img:
                    self.pil_original_image = img.copy()
                self.log(f"Successfully loaded heightmap image: {os.path.basename(file_path)} ({self.pil_original_image.width} x {self.pil_original_image.height} pixels)")
                self.process_image_preview()
                self.btn_compile.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self, "Image Import Error", f"Could not load the selected image.\nError details: {str(e)}")

    # ==============================================================================
    # BASE FLATTENING & FORBIDDEN AREA SELECTION
    # ==============================================================================
    def start_pick_base(self):
        self.picker_mode = "base"
        self.btn_pick_base.setText("Click depth image...")
        self.btn_pick_base.setStyleSheet("background-color: #005999; border: 1px solid #00ffaa;")
        self.btn_pick_forbidden.setText("Pick Forbidden Color")
        self.btn_pick_forbidden.setStyleSheet("")
        self.canvas.setCursor(Qt.CrossCursor)
        self.log("Click on the depth image to select the Base reference color.")

    def start_pick_forbidden(self):
        self.picker_mode = "forbidden"
        self.btn_pick_forbidden.setText("Click depth image...")
        self.btn_pick_forbidden.setStyleSheet("background-color: #cc3333; border: 1px solid #00ffaa;")
        self.btn_pick_base.setText("Pick Base Color")
        self.btn_pick_base.setStyleSheet("")
        self.canvas.setCursor(Qt.CrossCursor)
        self.log("Click on the depth image to select the Forbidden area color.")

    def on_canvas_clicked(self, x, y, button):
        if self.pil_processed_image is None:
            return
            
        lbl_w, lbl_h = self.canvas.width(), self.canvas.height()
        pixmap = self.canvas.pixmap()
        if not pixmap:
            return
        pm_w, pm_h = pixmap.width(), pixmap.height()
        
        dx = (lbl_w - pm_w) // 2
        dy = (lbl_h - pm_h) // 2
        
        cx = x - dx
        cy = y - dy
        if 0 <= cx < pm_w and 0 <= cy < pm_h:
            img_w = self.pil_processed_image.width
            img_h = self.pil_processed_image.height
            px = int((cx / pm_w) * img_w)
            py = int((cy / pm_h) * img_h)
            px = max(0, min(img_w - 1, px))
            py = max(0, min(img_h - 1, py))
            
            color_val = self.pil_processed_image.getpixel((px, py))
            
            if getattr(self, "picker_mode", None) == "base":
                self.base_color = color_val
                self.lbl_base_color.setText(f"Base Color: {color_val}")
                self.lbl_base_color.setStyleSheet("color: #00ffaa; font-weight: bold;")
                self.log(f"Selected Base reference color: {color_val}")
                self.picker_mode = None
                self.btn_pick_base.setText("Pick Base Color")
                self.btn_pick_base.setStyleSheet("")
                self.canvas.setCursor(Qt.ArrowCursor)
                self.process_image_preview()
            elif getattr(self, "picker_mode", None) == "forbidden":
                self.forbidden_color = color_val
                self.lbl_forbidden_color.setText(f"Forbidden: {color_val}")
                self.lbl_forbidden_color.setStyleSheet("color: #ff3333; font-weight: bold;")
                self.log(f"Selected Forbidden area color: {color_val}")
                self.picker_mode = None
                self.btn_pick_forbidden.setText("Pick Forbidden Color")
                self.btn_pick_forbidden.setStyleSheet("")
                self.canvas.setCursor(Qt.ArrowCursor)
                self.process_image_preview()

    def process_image_preview(self):
        if self.pil_original_image is None:
            return
        # Restart the timer to debounce expensive calculations while user is typing
        self.preview_timer.start(250)

    def do_process_image_preview(self):
        if self.pil_original_image is None:
            return
            
        self.preview_cuts = []
        self.preview_travels = []
        
        try:
            # 1. Convert to L (Grayscale)
            img = self.pil_original_image.convert("L")
            
            # 2. Blur / Smoothing filter
            blur_radius = self.blur_slider.value()
            if blur_radius > 0:
                img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                
            # 3. Downsampling
            downsample_factor = 2 ** self.downsample_combo.currentIndex() # 1x, 2x, 4x, 8x
            if downsample_factor > 1:
                new_w = max(16, img.width // downsample_factor)
                new_h = max(16, img.height // downsample_factor)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
            # 4. Invert Height if required
            if self.invert_check.isChecked():
                # Efficient pixel-level inversion
                arr = np.array(img)
                arr = 255 - arr
                img = Image.fromarray(arr)
                
            # 5. Base Color Flattening Filter
            if getattr(self, "base_color", None) is not None:
                arr = np.array(img, dtype=np.float32)
                try:
                    btol = float(self.base_tolerance_input.text() or 5)
                except ValueError:
                    btol = 5.0
                mask = np.abs(arr - self.base_color) <= btol
                arr[mask] = self.base_color
                img = Image.fromarray(arr.astype(np.uint8))
                
            self.pil_processed_image = img
            self.display_image_in_canvas()
            self.update_live_estimates()
            
        except Exception as e:
            self.log(f"Error processing image: {str(e)}")

    def get_forbidden_mask(self):
        return self.get_forbidden_mask_extended(0.0)

    def get_forbidden_mask_extended(self, additional_offset_mm=0.0):
        if self.pil_processed_image is None or getattr(self, "forbidden_color", None) is None:
            return None
            
        try:
            ftol = float(self.forbidden_tolerance_input.text() or 10)
        except ValueError:
            ftol = 10.0
            
        # Get raw mask based on color tolerance
        arr = np.array(self.pil_processed_image, dtype=np.float32)
        raw_mask_arr = (np.abs(arr - self.forbidden_color) <= ftol).astype(np.uint8) * 255
        
        # Read the offset value from UI
        try:
            offset_mm = float(self.forbidden_offset_input.text() or 0.0)
        except ValueError:
            offset_mm = 0.0
            
        total_offset_mm = offset_mm + additional_offset_mm
        if total_offset_mm == 0.0:
            return raw_mask_arr > 0
            
        # Convert millimeters to pixels based on current workpiece size and image resolution
        try:
            stock_x = float(self.stock_x_input.text() or 150.0)
            stock_y = float(self.stock_y_input.text() or 150.0)
        except ValueError:
            stock_x = 150.0
            stock_y = 150.0
            
        img_w, img_h = self.pil_processed_image.width, self.pil_processed_image.height
        
        # Let's calculate pixels per millimeter
        px_per_mm_x = img_w / stock_x if stock_x > 0 else 1.0
        px_per_mm_y = img_h / stock_y if stock_y > 0 else 1.0
        
        # Use average pixel density for uniform morphology radius
        px_density = (px_per_mm_x + px_per_mm_y) / 2.0
        px_offset = total_offset_mm * px_density
        
        # Compute diameter for the min/max filter:
        diameter = int(round(2.0 * abs(px_offset))) | 1
        if diameter < 3:
            return raw_mask_arr > 0
            
        # Apply Pillow's MaxFilter / MinFilter
        mask_image = Image.fromarray(raw_mask_arr)
        
        # Optimization: if the morphology filter is too large, downscale it to prevent slow execution and hangs
        if diameter > 31:
            scale_factor = diameter / 15.0
            new_w = max(16, int(round(img_w / scale_factor)))
            new_h = max(16, int(round(img_h / scale_factor)))
            mask_image_small = mask_image.resize((new_w, new_h), Image.Resampling.NEAREST)
            small_diameter = 15
            if total_offset_mm > 0.0:
                mask_image_small = mask_image_small.filter(ImageFilter.MaxFilter(size=small_diameter))
            else:
                mask_image_small = mask_image_small.filter(ImageFilter.MinFilter(size=small_diameter))
            mask_image = mask_image_small.resize((img_w, img_h), Image.Resampling.NEAREST)
        else:
            if total_offset_mm > 0.0:
                # Positive value: expands the forbidden area (dilates white area)
                mask_image = mask_image.filter(ImageFilter.MaxFilter(size=diameter))
            else:
                # Negative value: shrinks the forbidden area (erodes white area)
                mask_image = mask_image.filter(ImageFilter.MinFilter(size=diameter))
            
        adjusted_mask_arr = np.array(mask_image)
        return adjusted_mask_arr > 0

    def workspace_to_canvas(self, tx, ty, w, h):
        try:
            stock_x = float(self.stock_x_input.text() or 150.0)
            stock_y = float(self.stock_y_input.text() or 150.0)
        except ValueError:
            stock_x = 150.0
            stock_y = 150.0
            
        swap_axes = (self.axis_orientation_combo.currentIndex() == 1)
        zero_point = self.zero_point_combo.currentIndex()
        
        if swap_axes:
            sx, sy = stock_y, stock_x
        else:
            sx, sy = stock_x, stock_y
            
        if zero_point == 0:   # Front-Left
            tx_raw, ty_raw = tx, ty
        elif zero_point == 1: # Front-Right
            tx_raw, ty_raw = tx + sx, ty
        elif zero_point == 2: # Back-Left
            tx_raw, ty_raw = tx, ty + sy
        elif zero_point == 3: # Back-Right
            tx_raw, ty_raw = tx + sx, ty + sy
        elif zero_point == 4: # Center
            tx_raw, ty_raw = tx + (sx / 2.0), ty + (sy / 2.0)
        else:
            tx_raw, ty_raw = tx, ty
            
        if swap_axes:
            x, y = ty_raw, tx_raw
        else:
            x, y = tx_raw, ty_raw
            
        img_w, img_h = self.pil_processed_image.width, self.pil_processed_image.height
        preserve_aspect = self.aspect_check.isChecked()
        
        min_y_val = getattr(self, "min_y", 0)
        max_y_val = getattr(self, "max_y", img_h - 1)
        min_x_val = getattr(self, "min_x", 0)
        max_x_val = getattr(self, "max_x", img_w - 1)
        carving_w_val = getattr(self, "carving_w", img_w)
        carving_h_val = getattr(self, "carving_h", img_h)
        scaled_w_val = getattr(self, "scaled_w", stock_x)
        scaled_h_val = getattr(self, "scaled_h", stock_y)
        offset_x_val = getattr(self, "offset_x_val", 0.0)
        offset_y_val = getattr(self, "offset_y_val", 0.0)
        
        if preserve_aspect:
            cx_work = x - offset_x_val
            cy_work = y - offset_y_val
            if cx_work < 0 or cx_work >= scaled_w_val or cy_work < 0 or cy_work >= scaled_h_val:
                px = (x / max(1.0, stock_x)) * (img_w - 1)
                py = (img_h - 1) - (y / max(1.0, stock_y)) * (img_h - 1)
            else:
                px = min_x_val + (cx_work / max(1.0, scaled_w_val)) * carving_w_val
                py = max_y_val - (cy_work / max(1.0, scaled_h_val)) * carving_h_val
        else:
            px = (x / max(1.0, stock_x)) * (img_w - 1)
            py = (img_h - 1) - (y / max(1.0, stock_y)) * (img_h - 1)
            
        cx = (px / max(1, img_w - 1)) * w
        cy = (py / max(1, img_h - 1)) * h
        return cx, cy

    def display_image_in_canvas(self):
        if self.pil_processed_image is None:
            return
            
        # Convert PIL to QImage and QPixmap for PySide6
        pil_img = self.pil_processed_image.convert("RGBA")
        
        # Overlay forbidden color in red
        if getattr(self, "forbidden_color", None) is not None:
            mask = self.get_forbidden_mask()
            if mask is not None:
                pixels = np.array(pil_img)
                pixels[mask, 0] = np.clip(0.4 * pixels[mask, 0] + 0.6 * 255, 0, 255).astype(np.uint8)
                pixels[mask, 1] = np.clip(0.4 * pixels[mask, 1] + 0.6 * 30, 0, 255).astype(np.uint8)
                pixels[mask, 2] = np.clip(0.4 * pixels[mask, 2] + 0.6 * 30, 0, 255).astype(np.uint8)
                pil_img = Image.fromarray(pixels)
            
        data = pil_img.tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        
        # Fit image to preview label dimensions while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(self.canvas.size() - QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # Draw origin zero indicator
        canvas_pixmap = QPixmap(scaled_pixmap.size())
        canvas_pixmap.fill(Qt.transparent)
        
        painter = QPainter(canvas_pixmap)
        painter.drawPixmap(0, 0, scaled_pixmap)
        
        # Zero point position styling
        zero_point = self.zero_point_combo.currentIndex()
        w, h = scaled_pixmap.width(), scaled_pixmap.height()
        
        pen = QPen(QColor(255, 60, 60))
        pen.setWidth(4)
        painter.setPen(pen)
        
        # Draw G-code preview path overlays if they exist
        preview_cuts = getattr(self, "preview_cuts", None)
        preview_travels = getattr(self, "preview_travels", None)
        
        if preview_cuts or preview_travels:
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF
            
            # Draw travels first so they appear behind cutting paths
            if preview_travels:
                pen_travel = QPen(QColor(0, 190, 255, 220))
                pen_travel.setWidthF(1.5)
                pen_travel.setStyle(Qt.DashLine)
                painter.setPen(pen_travel)
                for seg in preview_travels:
                    if len(seg) < 2:
                        continue
                    poly = QPolygonF()
                    for tx, ty in seg:
                        cx, cy = self.workspace_to_canvas(tx, ty, w, h)
                        poly.append(QPointF(cx, cy))
                    painter.drawPolyline(poly)
                    
            if preview_cuts:
                # Get active tool parameters to compute exact physical cut width at depth
                idx = self.tool_combo.currentData()
                tool = self.tools_list[idx] if (idx is not None and idx < len(self.tools_list)) else None
                if tool:
                    ttype = tool.get("type", "Ball Nose")
                    t_tip = tool.get("tip_diameter", 3.0)
                    t_ball = tool.get("ball_radius", 1.5)
                    t_max = tool.get("max_diameter", 10.0)
                    t_angle = tool.get("taper_angle", 0.0)
                else:
                    ttype = "Ball Nose"
                    t_tip = 3.0
                    t_ball = 1.5
                    t_max = 10.0
                    t_angle = 0.0

                try:
                    stock_x = float(self.stock_x_input.text() or 50.0)
                except ValueError:
                    stock_x = 50.0
                    
                def get_tool_radius_at_depth(d):
                    d = max(0.0, d)
                    if ttype == "Flat End Mill":
                        return t_tip / 2.0
                    elif ttype == "Ball Nose":
                        if d < t_ball:
                            return np.sqrt(max(0.0, 2.0 * t_ball * d - d**2))
                        return t_tip / 2.0
                    elif ttype == "V-Bit":
                        theta = np.radians(t_angle / 2.0)
                        return min(t_max / 2.0, (t_tip / 2.0) + d * np.tan(theta))
                    elif ttype == "Tapered Ball Nose":
                        theta = np.radians(t_angle)
                        r_tangent = t_ball * np.cos(theta)
                        d_tangent = t_ball - t_ball * np.sin(theta)
                        if d < d_tangent:
                            return np.sqrt(max(0.0, 2.0 * t_ball * d - d**2))
                        else:
                            return min(t_max / 2.0, r_tangent + (d - d_tangent) * np.tan(theta))
                    return 1.5

                for seg in preview_cuts:
                    if len(seg) < 2:
                        continue
                    
                    # Draw continuous segmented line with varying width based on coordinate depth
                    for idx_pt in range(len(seg) - 1):
                        p1 = seg[idx_pt]
                        p2 = seg[idx_pt + 1]
                        
                        # Support both old (tx, ty) and new (tx, ty, cz) coordinates safely
                        tx1, ty1 = p1[0], p1[1]
                        cz1 = p1[2] if len(p1) > 2 else 0.0
                        
                        tx2, ty2 = p2[0], p2[1]
                        cz2 = p2[2] if len(p2) > 2 else 0.0
                        
                        cx1, cy1 = self.workspace_to_canvas(tx1, ty1, w, h)
                        cx2, cy2 = self.workspace_to_canvas(tx2, ty2, w, h)
                        
                        # Depth is -Z
                        d = -(cz1 + cz2) / 2.0
                        p_rad = get_tool_radius_at_depth(d)
                        
                        # Project physical diameter (in mm) to canvas pixels
                        pen_w = max(1.5, 2.0 * p_rad * (w / max(1.0, stock_x)))
                        
                        # Transparent green overlay
                        pen_cut = QPen(QColor(0, 255, 100, 100))
                        pen_cut.setWidthF(pen_w)
                        pen_cut.setCapStyle(Qt.RoundCap)
                        pen_cut.setJoinStyle(Qt.RoundJoin)
                        painter.setPen(pen_cut)
                        
                        painter.drawLine(cx1, cy1, cx2, cy2)

        # Origin crosshair location
        ox, oy = 0, 0
        if zero_point == 0:   # Front-Left (Usually bottom-left in machine space, let's render bottom-left coordinate)
            ox, oy = 10, h - 10
        elif zero_point == 1: # Front-Right (bottom-right)
            ox, oy = w - 10, h - 10
        elif zero_point == 2: # Back-Left (top-left)
            ox, oy = 10, 10
        elif zero_point == 3: # Back-Right (top-right)
            ox, oy = w - 10, 10
        elif zero_point == 4: # Center
            ox, oy = w // 2, h // 2
            
        # Draw origin target
        painter.drawLine(ox - 15, oy, ox + 15, oy)
        painter.drawLine(ox, oy - 15, ox, oy + 15)
        
        painter.end()
        
        self.canvas.setPixmap(canvas_pixmap)
        self.canvas.setText("") # Clear default placeholder text

    # ==============================================================================
    # ESTIMATION & LIVE CALCULATIONS
    # ==============================================================================
    def update_live_estimates(self):
        if self.pil_processed_image is None:
            return
            
        try:
            # Load workpiece dimensions
            stock_x = float(self.stock_x_input.text() or 0.0)
            stock_y = float(self.stock_y_input.text() or 0.0)
            stepover = float(self.stepover_input.text() or 1.0)
            resol_x = float(self.resol_x_input.text() or 0.5)
            
            if stock_x <= 0 or stock_y <= 0 or stepover <= 0 or resol_x <= 0:
                return
                
            # Calculations
            est_lines = int(stock_y / stepover) + 1
            pts_per_line = int(stock_x / resol_x) + 1
            total_raw_points = est_lines * pts_per_line
            
            # Simple G-code file size estimation: ~55 bytes per linear coordinate G01 line
            est_size_mb = (total_raw_points * 55) / (1024 * 1024)
            
            # Update display
            self.lbl_est_lines.setText(f"Estimated Scanlines: {est_lines}")
            self.lbl_est_points.setText(f"Est. Total Raw Points: {total_raw_points:,}")
            self.lbl_est_size.setText(f"Estimated G-Code Size: {est_size_mb:.2f} MB")
            
            # Set warnings if file size or points are excessive
            if total_raw_points > 500000 or est_size_mb > 25.0:
                self.lbl_warning.setText("⚠️ Warning: Large G-code file size! Increase stepover/resolution or downsample.")
                self.lbl_est_size.setStyleSheet("color: #ff3333; font-weight: bold;")
            else:
                self.lbl_warning.setText("")
                self.lbl_est_size.setStyleSheet("color: #00ffaa; font-weight: bold;")
                
        except ValueError:
            pass # Suppress typing input exceptions

    # ==============================================================================
    # TOOL LIBRARY PERSISTENCE & CRUD
    # ==============================================================================
    def load_tool_library(self):
        if not os.path.exists(self.tools_library_path):
            # Create default library file
            defaults = [
                {
                    "name": "LOXA CZ10.3-60(120)",
                    "type": "Tapered Ball Nose",
                    "tip_diameter": 3.0,
                    "ball_radius": 1.5,
                    "max_diameter": 10.0,
                    "tool_length": 60.0,
                    "cutting_length": 25.0,
                    "notes": "Default professional tapered ball nose tool for stone engraving."
                },
                {
                    "name": "Roughing Endmill 6mm",
                    "type": "Flat End Mill",
                    "tip_diameter": 6.0,
                    "ball_radius": 0.0,
                    "max_diameter": 6.0,
                    "tool_length": 50.0,
                    "cutting_length": 25.0,
                    "notes": "Standard flat roughing tool."
                }
            ]
            try:
                os.makedirs(os.path.dirname(self.tools_library_path), exist_ok=True)
                with open(self.tools_library_path, "w") as f:
                    json.dump(defaults, f, indent=4)
            except Exception as e:
                self.log(f"Warning: Could not write default tools library: {str(e)}")
                
        # Read from JSON
        try:
            with open(self.tools_library_path, "r") as f:
                self.tools_list = json.load(f)
        except Exception as e:
            self.log(f"Error loading tools library: {str(e)}")
            self.tools_list = []
            
        self.populate_tool_dropdown()

    def populate_tool_dropdown(self):
        self.tool_combo.clear()
        for idx, tool in enumerate(self.tools_list):
            self.tool_combo.addItem(f"{tool['name']} ({tool['type']} R{tool['ball_radius']}mm)", idx)
            
    def on_tool_selected(self):
        idx = self.tool_combo.currentData()
        if idx is not None and idx < len(self.tools_list):
            tool = self.tools_list[idx]
            self.log(f"Active Tool Selected: {tool['name']} ({tool['type']})")

    def save_tool_library(self):
        try:
            with open(self.tools_library_path, "w") as f:
                json.dump(self.tools_list, f, indent=4)
            self.populate_tool_dropdown()
            self.log("Tools library successfully saved to disk.")
        except Exception as e:
            QMessageBox.critical(self, "Database Save Error", f"Could not write tool library changes: {str(e)}")

    def add_tool(self):
        dialog = ToolDialog(self)
        if dialog.exec() == QDialog.Accepted:
            tool_data = dialog.get_tool_data()
            if tool_data:
                self.tools_list.append(tool_data)
                self.save_tool_library()
                self.tool_combo.setCurrentIndex(self.tool_combo.count() - 1)

    def edit_tool(self):
        idx = self.tool_combo.currentData()
        if idx is not None and idx < len(self.tools_list):
            dialog = ToolDialog(self, self.tools_list[idx])
            if dialog.exec() == QDialog.Accepted:
                tool_data = dialog.get_tool_data()
                if tool_data:
                    self.tools_list[idx] = tool_data
                    self.save_tool_library()
                    self.tool_combo.setCurrentIndex(idx)
        else:
            QMessageBox.warning(self, "No Tool Selected", "Please select a tool from the library list to edit.")

    def delete_tool(self):
        idx = self.tool_combo.currentData()
        if idx is not None and idx < len(self.tools_list):
            tool_name = self.tools_list[idx]["name"]
            res = QMessageBox.question(
                self, "Confirm Delete", f"Are you sure you want to permanently delete tool specifications for '{tool_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.Yes:
                self.tools_list.pop(idx)
                self.save_tool_library()
        else:
            QMessageBox.warning(self, "No Tool Selected", "Please select a tool to delete.")

    def find_avoidance_path(self, start_xy, end_xy, obstacle_grid, grid_size, stock_x, stock_y):
        import heapq
        sx, sy = start_xy
        ex, ey = end_xy
        
        # Grid dimensions
        rows, cols = obstacle_grid.shape
        
        def to_grid(x, y):
            col = max(0, min(cols - 1, int(x / grid_size)))
            row = max(0, min(rows - 1, int(y / grid_size)))
            return col, row
            
        def to_world(col, row):
            x = (col + 0.5) * grid_size
            y = (row + 0.5) * grid_size
            return min(stock_x, max(0.0, x)), min(stock_y, max(0.0, y))
            
        start_cell = to_grid(sx, sy)
        end_cell = to_grid(ex, ey)
        
        if start_cell == end_cell:
            return [end_xy]
            
        open_set = []
        # Store tuple: (f_score, cell)
        heapq.heappush(open_set, (0, start_cell))
        came_from = {}
        g_score = {start_cell: 0}
        
        def heuristic(c1, c2):
            # Chebyshev/Octile distance for diagonal movement
            dx = abs(c1[0] - c2[0])
            dy = abs(c1[1] - c2[1])
            return max(dx, dy) + 0.414 * min(dx, dy)
            
        found = False
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == end_cell:
                found = True
                break
                
            # 8-connectivity directions
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if 0 <= neighbor[0] < cols and 0 <= neighbor[1] < rows:
                    if obstacle_grid[neighbor[1], neighbor[0]]:
                        continue # Skip obstacle
                        
                    step_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                    tentative_g = g_score[current] + step_cost
                    
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f_score = tentative_g + heuristic(neighbor, end_cell)
                        heapq.heappush(open_set, (f_score, neighbor))
                        
        if not found:
            return [end_xy]
            
        # Reconstruct grid cell path
        path = []
        curr = end_cell
        while curr in came_from:
            path.append(curr)
            curr = came_from[curr]
        path.reverse()
        
        # Convert path cells to world coordinates
        world_path = []
        for col, row in path:
            world_path.append(to_world(col, row))
            
        if world_path:
            world_path[-1] = end_xy
            
        return world_path

    # ==============================================================================
    # ROUGHING / FINISHING CNC CORE ALGORITHMS
    # ==============================================================================
    def on_worker_progress(self, stage, percent, row, moves, size_kb, elapsed_time):
        self.last_progress_time = time.time()
        self.progress_bar_dialog.setValue(percent)
        self.progress_stage_lbl.setText(stage)
        
        # Calculate estimated time remaining
        if percent > 0:
            total_est = (elapsed_time / percent) * 100.0
            remaining = max(0.0, total_est - elapsed_time)
            rem_str = f"{remaining:.1f}s"
        else:
            rem_str = "--"
            
        self.progress_info_lbl.setText(
            f"Row/Seg: {row} | Moves: {moves} | Est. Size: {size_kb} KB | "
            f"Elapsed: {elapsed_time:.1f}s | Est. Remaining: {rem_str}"
        )

    def cancel_generation(self):
        self.log("[CAM] Cancellation requested by user. Restoring workspace...")
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        if hasattr(self, "generation_progress_dialog"):
            self.generation_progress_dialog.close()
            
    def check_worker_watchdog(self):
        if hasattr(self, "last_progress_time"):
            diff = time.time() - self.last_progress_time
            if diff > 10.0:
                self.log("[WARN] Worker thread has not reported progress for 10 seconds. Check CPU load.")

    def on_worker_finished(self, success, error_msg, stats):
        if hasattr(self, "watchdog_timer"):
            self.watchdog_timer.stop()
        if hasattr(self, "generation_progress_dialog"):
            self.generation_progress_dialog.close()
            
        self.btn_compile.setEnabled(True)
        self.is_generating = False
        
        # Clean progress bars
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
        if not success:
            if error_msg == "User Cancelled":
                QMessageBox.warning(self, "Generation Cancelled", "G-code generation was successfully cancelled by the user.")
                self.log("[CAM] Workspace rolled back. Temporary G-code files removed.")
            else:
                QMessageBox.critical(self, "CAM Engine Error", f"G-code generation failed:\n{error_msg}")
                self.log(f"[ERROR] CAM engine error: {error_msg}")
            return

        # Core physical verification of generated files
        try:
            p = self.worker.params
            do_roughing = p["do_roughing"]
            do_finishing = p["do_finishing"]
            file_path = p["file_path"]
            
            rough_path = file_path.replace(".tap", "_roughing.tap")
            if do_roughing:
                finish_path = file_path.replace(".tap", "_finishing.tap")
            else:
                finish_path = file_path
                
            files_to_verify = []
            if do_roughing:
                files_to_verify.append(("Roughing", rough_path))
            if do_finishing:
                files_to_verify.append(("Finishing", finish_path))
                
            for label, p_file in files_to_verify:
                self.log(f"[CAM] Verifying output file on disk: {p_file}")
                if not os.path.exists(p_file):
                    raise FileNotFoundError(f"{label} G-code file was not created on disk: {p_file}")
                    
                sz = os.path.getsize(p_file)
                self.log(f"[CAM] File size check: {sz} bytes")
                if sz <= 0:
                    raise ValueError(f"{label} G-code file is empty (0 bytes): {p_file}")
                    
                # Modified timestamp check (verify within 15 seconds)
                mtime = os.path.getmtime(p_file)
                time_diff = time.time() - mtime
                if time_diff > 15.0:
                    raise ValueError(f"{label} G-code file timestamp is stale ({time_diff:.1f}s old): {p_file}")
            
            # Post-generation Diagnostics logging if enabled
            if p["diagnostic_mode"]:
                diag_path = file_path + ".log"
                self.log(f"[DIAG] Diagnostic Mode active. Writing execution log to: {diag_path}")
                with open(diag_path, "w") as df:
                    df.write("Velora CNC - 3D CNC Toolpath Engine Diagnostic Log\n")
                    df.write("Developed by Eng. Bara Eiz (almaamoneiz@gmail.com)\n")
                    df.write("========================================================\n")
                    df.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    df.write(f"Elapsed Generation Time: {stats['elapsed_time']:.2f} seconds\n")
                    df.write(f"Total Raw Toolpath Points Scanned: {stats['total_raw_points']}\n")
                    df.write(f"Total Simplified G-code Points: {stats['simplified_points']}\n")
                    df.write(f"Point Simplification Reduction: {stats['simplification_percentage']:.2f}%\n")
                    df.write(f"Total G0 Rapid Moves: {stats['g0_moves']}\n")
                    df.write(f"Total G1 Linear Cuts: {stats['g1_moves']}\n")
                    df.write(f"Redundant coordinates removed: {stats['redundant_points_filtered']}\n")
                    df.write(f"Long rapids detected (>150mm): {stats['long_rapid_moves_count']}\n")
                    df.write(f"No-Go Zone crossings/violations avoided: {stats['violations_detected']}\n")
                    df.write(f"Z Retracts / Z Plunges Generated: {stats['z_retracts_count']} / {stats['z_plunges_count']}\n")
                    df.write(f"Total Z axis travel distance: {stats['total_z_travel_distance']:.1f} mm\n")
                    df.write(f"Z Retract reduction percentage: {stats['z_movement_reduction_percent']:.1f}%\n")
                    df.write(f"Estimated Machining Time Saved: {stats['estimated_time_saved_mins']:.1f} mins\n")
                    df.write(f"Final output file sizes: {stats['final_file_size_kb']} KB\n")
                    df.write("========================================================\n")
                    df.write("Machining settings:\n")
                    df.write(f"  Tool type: {p['tool_type']}\n")
                    df.write(f"  Tip/Max Diameter: {p['tool_params']['tip_diameter']}mm / {p['tool_params']['max_diameter']}mm\n")
                    df.write(f"  Zero Point Origin: {p['zero_point']}\n")
                    df.write(f"  Forbidden behavioral behavior: No-Go Zone={p['is_nogo']}\n")
                    df.write(f"  Z Retract Between Passes: {p.get('retract_between_passes', True)}\n")
                self.log(f"[DIAG] Diagnostic report written successfully.")

            # Load preview toolpath cuts for visualization rendering!
            self.preview_cuts = []
            self.preview_travels = []
            
            self.log("[CAM] Rendering preview toolpaths for screen visualizer...")
            
            # We do a fast downsampled 2D render loop for Qt visualizer
            arr_h, arr_w = self.worker.arr.shape
            
            def get_surf_z(x, y):
                if p["preserve_aspect"]:
                    cx = x - self.worker.offset_x
                    cy = y - self.worker.offset_y
                    if cx < 0 or cx >= self.worker.scaled_w or cy < 0 or cy >= self.worker.scaled_h:
                        return -p["max_depth"]
                    px = self.worker.min_x + (cx / self.worker.scaled_w) * self.worker.carving_w
                    py = self.worker.min_y - (cy / self.worker.scaled_h) * self.worker.carving_h
                else:
                    px = (x / p["stock_x"]) * (arr_w - 1)
                    py = (arr_h - 1) - (y / p["stock_y"]) * (arr_h - 1)
                px = max(0, min(arr_w - 1, int(px)))
                py = max(0, min(arr_h - 1, int(py)))
                val = self.worker.arr[py, px]
                
                # Scaled base color Z logic
                base_color = p.get("base_color", None)
                invert_check = p.get("invert_check", False)
                max_depth = p["max_depth"]
                
                if base_color is not None:
                    if invert_check:
                        if base_color <= 0.0:
                            z_val = -max_depth * (1.0 - val / 255.0)
                        else:
                            if val >= base_color:
                                z_val = 0.0
                            elif val <= 0.0:
                                z_val = -max_depth
                            else:
                                factor = val / float(base_color)
                                z_val = -max_depth * (1.0 - factor)
                    else:
                        if base_color >= 255.0:
                            z_val = -max_depth * (1.0 - val / 255.0)
                        else:
                            if val <= base_color:
                                z_val = -max_depth
                            elif val >= 255.0:
                                z_val = 0.0
                            else:
                                factor = (val - base_color) / float(255.0 - base_color)
                                z_val = -max_depth * (1.0 - factor)
                else:
                    z_val = -max_depth * (1.0 - val / 255.0)
                    
                return z_val

            # Finishing preview cuts
            if do_finishing:
                prev_y = np.linspace(0.0, p["stock_y"], min(25, int(p["stock_y"]/2.0)))
                prev_x = np.linspace(0.0, p["stock_x"], 100)
                for y in prev_y:
                    pts = []
                    for x in prev_x:
                        z = get_surf_z(x, y)
                        pts.append((x, y, min(0.0, z)))
                    self.preview_cuts.append(np.array(pts))
            elif do_roughing:
                prev_y = np.linspace(0.0, p["stock_y"], 10)
                prev_x = np.linspace(0.0, p["stock_x"], 50)
                for y in prev_y:
                    pts = []
                    for x in prev_x:
                        pts.append((x, y, p["rough_depth"]))
                    self.preview_cuts.append(np.array(pts))

            # Display headings preview in console
            self.console.clear()
            self.log("=== COMPILATION SUCCESSFUL ===")
            self.log(f"Time Taken: {stats['elapsed_time']:.2f}s")
            self.log(f"Collinear Points Simplification: {stats['simplification_percentage']:.1f}% Reduction")
            self.log(f"Redundant modal commands omitted: {stats['redundant_points_filtered']} lines")
            self.log(f"No-Go Zone violations avoided: {stats['violations_detected']}")
            self.log(f"Z Retracts / Z Plunges Generated: {stats['z_retracts_count']} / {stats['z_plunges_count']}")
            self.log(f"Total Z axis travel distance: {stats['total_z_travel_distance']:.1f} mm")
            self.log(f"Z Retract reduction percentage: {stats['z_movement_reduction_percent']:.1f}%")
            self.log(f"Estimated Machining Time Saved: {stats['estimated_time_saved_mins']:.1f} mins")
            
            if do_roughing:
                self.log(f"\n[ROUGHING PATH]: {rough_path}")
                self.log("--- Header Preview ---")
                with open(rough_path, "r") as rf:
                    lines = [rf.readline().strip() for _ in range(12)]
                for line in lines:
                    self.log(line)
                    
            if do_finishing:
                self.log(f"\n[FINISHING PATH]: {finish_path}")
                self.log("--- Header Preview ---")
                with open(finish_path, "r") as ff:
                    lines = [ff.readline().strip() for _ in range(12)]
                for line in lines:
                    self.log(line)
                    
            # Refresh screen canvas to paint toolpaths!
            self.display_image_in_canvas()
            
            QMessageBox.information(
                self, "Compilation Successful",
                f"CNC G-code compiled successfully!\n\n"
                f"Simplification: {stats['simplification_percentage']:.1f}% reduction\n"
                f"Redundant moves filtered: {stats['redundant_points_filtered']}\n"
                f"Total moves: {stats['g0_moves'] + stats['g1_moves']}\n\n"
                f"--- Z Retract Optimization ---\n"
                f"Z Retracts / Plunges: {stats['z_retracts_count']} / {stats['z_plunges_count']}\n"
                f"Total Z Travel: {stats['total_z_travel_distance']:.1f} mm ({stats['z_movement_reduction_percent']:.1f}% reduction)\n"
                f"Estimated Time Saved: {stats['estimated_time_saved_mins']:.1f} minutes!\n\n"
                f"File verified physically on disk."
            )
            
        except Exception as ex:
            QMessageBox.critical(self, "Validation Error", f"Output verification failed:\n{str(ex)}")
            self.log(f"[ERROR] Physical file check failed: {str(ex)}")

    def generate_cam_toolpaths(self):
        if self.pil_processed_image is None:
            QMessageBox.critical(self, "Missing Image", "Please import and load a depth map image before compiling.")
            return
            
        if self.is_generating:
            self.log("Generation already in progress. Ignoring duplicate click.")
            return
        self.is_generating = True
        
        try:
            self.log("[CAM] Start generation process")
            
            # 1. Read dimensional stock values
            stock_x = float(self.stock_x_input.text())
            stock_y = float(self.stock_y_input.text())
            max_depth = float(self.stock_z_input.text())
            
            # 2. Reads feeds and spindle speeds
            spindle_rpm = int(self.spindle_input.text())
            feed_xy = float(self.xy_feed_input.text())
            feed_z = float(self.z_feed_input.text())
            feed_plunge = float(self.plunge_feed_input.text())
            safe_z = float(self.safe_z_input.text())
            
            # Zero-point, aspect preservation, axis swapping, machining strategy
            zero_point = self.zero_point_combo.currentIndex()
            preserve_aspect = self.aspect_check.isChecked()
            swap_axes = (self.axis_orientation_combo.currentIndex() == 1)
            one_way = (self.machining_mode_combo.currentIndex() == 0)
            
            # Z-noise threshold
            try:
                min_z_threshold = float(self.min_z_input.text() or 0.0)
            except ValueError:
                min_z_threshold = 0.0
                
            # Forbidden area colors and tolerance
            forbidden_color = getattr(self, "forbidden_color", None)
            try:
                forbidden_tolerance = float(self.forbidden_tolerance_input.text() or 10)
            except ValueError:
                forbidden_tolerance = 10.0
                
            # Get active tool parameters
            idx = self.tool_combo.currentData()
            tool = self.tools_list[idx] if idx is not None else None
            
            if tool:
                tool_type = tool.get("type", "Ball Nose")
                tool_tip_diameter = tool.get("tip_diameter", 3.0)
                tool_ball_radius = tool.get("ball_radius", 1.5)
                tool_max_diameter = tool.get("max_diameter", 10.0)
                tool_length = tool.get("tool_length", 60.0)
                tool_cutting_length = tool.get("cutting_length", 25.0)
                tool_taper_angle = tool.get("taper_angle", 0.0)
            else:
                tool_type = "Ball Nose"
                tool_tip_diameter = 3.0
                tool_ball_radius = 1.5
                tool_max_diameter = 10.0
                tool_length = 60.0
                tool_cutting_length = 25.0
                tool_taper_angle = 0.0
                
            tool_params = {
                "tip_diameter": tool_tip_diameter,
                "ball_radius": tool_ball_radius,
                "max_diameter": tool_max_diameter,
                "tool_length": tool_length,
                "cutting_length": tool_cutting_length,
                "taper_angle": tool_taper_angle
            }
            
            if tool_type in ["Flat End Mill", "Ball Nose"]:
                finish_tool_radius = tool_tip_diameter / 2.0
            else:
                finish_tool_radius = tool_max_diameter / 2.0
                
            # Read variables needed for warnings & strategies
            stepover = float(self.stepover_input.text() or 1.0)
            resol_x = float(self.resol_x_input.text() or 0.5)
            is_nogo = (self.forbidden_behavior_combo.currentIndex() == 1)
            
            # Read optimizations inputs
            try:
                min_xy = float(self.min_xy_input.text() or 0.02)
            except ValueError:
                min_xy = 0.02
            try:
                min_z = float(self.min_z_move_input.text() or 0.03)
            except ValueError:
                min_z = 0.03
                
            do_roughing = self.rough_check.isChecked()
            do_finishing = self.finish_check.isChecked()
            
            if not do_roughing and not do_finishing:
                QMessageBox.warning(self, "No Pass Selected", "Please select at least one machining pass (Roughing or Finishing).")
                self.is_generating = False
                return
                
            try:
                rough_depth = float(self.rough_depth_input.text())
                rough_allowance = float(self.rough_allowance_input.text())
                rough_stepover = float(self.rough_stepover_input.text())
            except ValueError:
                rough_depth = -24.0
                rough_allowance = 1.0
                rough_stepover = 3.0

            # ---------------------------------------------------------
            # VALIDATION AND COMPREHENSIVE WARNING CHECKS
            # ---------------------------------------------------------
            warnings_list = []
            
            if abs(max_depth) > tool_cutting_length:
                warnings_list.append(f"⚠️ Warning: Max cutting depth ({abs(max_depth):.1f} mm) exceeds tool cutting length ({tool_cutting_length:.1f} mm). Shank collision may occur!")
                
            if tool_type == "V-Bit":
                theta = np.radians(tool_taper_angle / 2.0)
                cut_width = tool_tip_diameter + 2.0 * abs(max_depth) * np.tan(theta)
                if cut_width > tool_max_diameter:
                    warnings_list.append(f"⚠️ Warning: Max depth ({abs(max_depth):.1f} mm) creates cutting width ({cut_width:.1f} mm) larger than V-bit max tool diameter ({tool_max_diameter:.1f} mm).")
                elif cut_width > 20.0:
                    warnings_list.append(f"⚠️ Warning: V-Bit cutting width at maximum depth is very wide ({cut_width:.1f} mm).")
            
            if tool_type in ["Ball Nose", "Tapered Ball Nose"]:
                R_tip = tool_ball_radius if tool_type == "Tapered Ball Nose" else (tool_tip_diameter / 2.0)
                if R_tip > 0.0:
                    scallop_h = (stepover ** 2) / (8.0 * R_tip)
                    if scallop_h > 0.1:
                        warnings_list.append(f"⚠️ Warning: Large stepover ({stepover:.1f} mm) for ball-nose may create visible scallops ({scallop_h:.3f} mm height). Consider reducing stepover.")
                    if stepover > (2.0 * R_tip):
                        warnings_list.append(f"⚠️ Warning: Stepover ({stepover:.1f} mm) exceeds tool diameter ({2.0 * R_tip:.1f} mm). Uncut material ridges will remain!")
 
            if tool_type == "Flat End Mill":
                if tool_tip_diameter > (2.0 * resol_x):
                    warnings_list.append(f"⚠️ Warning: Flat End Mill diameter ({tool_tip_diameter:.1f} mm) is larger than double the stepover/resolution ({resol_x:.2f} mm). Sharp corners or details smaller than the cutter diameter cannot be reproduced.")
                if stepover > tool_tip_diameter:
                    warnings_list.append(f"⚠️ Warning: Stepover ({stepover:.1f} mm) exceeds flat tool diameter ({tool_tip_diameter:.1f} mm). Uncut material ridges will remain!")
 
            if is_nogo and finish_tool_radius > 0.0:
                try:
                    user_offset = float(self.forbidden_offset_input.text() or 5.0)
                except ValueError:
                    user_offset = 5.0
                if finish_tool_radius > user_offset:
                    warnings_list.append(f"⚠️ Warning: Tool physical radius ({finish_tool_radius:.1f} mm) is larger than forbidden area offset ({user_offset:.1f} mm), significantly expanding the blocked No-Go Zone.")
 
            if warnings_list:
                self.log("\n".join(warnings_list))
                self.lbl_warning.setText(warnings_list[0])
                self.lbl_warning.setStyleSheet("color: #ffaa00; font-weight: bold;")
            else:
                self.lbl_warning.setText("")
                
            # File selection dialog
            default_dir = os.getcwd()
            default_file = os.path.join(default_dir, "cnc_toolpath.tap")
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Mach3 G-Code File", default_file, "G-Code TAP Files (*.tap)"
            )
            if not file_path:
                self.log("[CAM] Generation cancelled by user")
                self.is_generating = False
                return
                
            if not file_path.lower().endswith(".tap"):
                file_path += ".tap"
                
            self.log(f"[CAM] Output path selected: {file_path}")
            
            # Setup Progress Dialog
            self.generation_progress_dialog = QDialog(self)
            self.generation_progress_dialog.setWindowTitle("Generating G-Code Toolpath...")
            self.generation_progress_dialog.setMinimumWidth(450)
            self.generation_progress_dialog.setModal(True)
            self.generation_progress_dialog.setStyleSheet("QDialog { background-color: #1a1a1f; color: #e0e0e6; } QLabel { font-size: 12px; }")
            
            progress_layout = QVBoxLayout(self.generation_progress_dialog)
            self.progress_stage_lbl = QLabel("Initializing background calculation thread...")
            self.progress_stage_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
            progress_layout.addWidget(self.progress_stage_lbl)
            
            self.progress_bar_dialog = QProgressBar()
            self.progress_bar_dialog.setValue(0)
            self.progress_bar_dialog.setFixedHeight(22)
            self.progress_bar_dialog.setStyleSheet("QProgressBar { background-color: #2b2b35; border: 1px solid #3d3d4e; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #007acc; }")
            progress_layout.addWidget(self.progress_bar_dialog)
            
            self.progress_info_lbl = QLabel("")
            self.progress_info_lbl.setStyleSheet("color: #a0a0b0; font-size: 11px;")
            progress_layout.addWidget(self.progress_info_lbl)
            
            self.progress_cancel_btn = QPushButton("Cancel Generation")
            self.progress_cancel_btn.setFixedHeight(35)
            self.progress_cancel_btn.setStyleSheet("QPushButton { background-color: #aa2222; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #cc3333; }")
            progress_layout.addWidget(self.progress_cancel_btn)
            
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(5)
            self.btn_compile.setEnabled(False)
            
            # Setup parameters dictionary
            params = {
                "stock_x": stock_x,
                "stock_y": stock_y,
                "max_depth": max_depth,
                "spindle_rpm": spindle_rpm,
                "feed_xy": feed_xy,
                "feed_z": feed_z,
                "feed_plunge": feed_plunge,
                "safe_z": safe_z,
                "zero_point": zero_point,
                "preserve_aspect": preserve_aspect,
                "swap_axes": swap_axes,
                "one_way": one_way,
                "min_z_threshold": min_z_threshold,
                "is_nogo": is_nogo,
                "tool_type": tool_type,
                "tool_params": tool_params,
                "file_path": file_path,
                "do_roughing": do_roughing,
                "do_finishing": do_finishing,
                "rough_depth": rough_depth,
                "rough_allowance": rough_allowance,
                "rough_stepover": rough_stepover,
                "stepover": stepover,
                "resol_x": resol_x,
                "simplification_preset": self.simplification_combo.currentIndex(),
                "min_xy_movement": min_xy,
                "min_z_movement": min_z,
                "diagnostic_mode": self.diagnostic_check.isChecked(),
                "raster_axis_combo": self.raster_axis_combo.currentIndex(),
                "base_color": self.base_color,
                "invert_check": self.invert_check.isChecked(),
                "retract_between_passes": self.retract_check.isChecked(),
            }
            
            # Dilate forbidden mask
            if is_nogo:
                forbidden_mask = self.get_forbidden_mask_extended(finish_tool_radius)
            else:
                forbidden_mask = self.get_forbidden_mask_extended(0.0)
                
            arr = np.array(self.pil_processed_image, dtype=np.float32)
            img_h, img_w = arr.shape
            
            non_black = np.where(arr > 15)
            if len(non_black[0]) > 0 and preserve_aspect:
                min_y, max_y = np.min(non_black[0]), np.max(non_black[0])
                min_x, max_x = np.min(non_black[1]), np.max(non_black[1])
                carving_w = max_x - min_x + 1
                carving_h = max_y - min_y + 1
            else:
                min_y, max_y, min_x, max_x = 0, img_h - 1, 0, img_w - 1
                carving_w, carving_h = img_w, img_h
                
            if preserve_aspect:
                scale_x = stock_x / carving_w
                scale_y = stock_y / carving_h
                scale = min(scale_x, scale_y)
                scaled_w = carving_w * scale
                scaled_h = carving_h * scale
                offset_x = (stock_x - scaled_w) / 2.0
                offset_y = (stock_y - scaled_h) / 2.0
            else:
                scaled_w = stock_x
                scaled_h = stock_y
                offset_x = 0.0
                offset_y = 0.0
                
            # Create worker
            self.worker = CAMWorker(
                params, arr, min_x, max_x, min_y, max_y, carving_w, carving_h,
                offset_x, offset_y, scaled_w, scaled_h, forbidden_mask
            )
            
            self.worker.progress_signal.connect(self.on_worker_progress)
            self.worker.log_signal.connect(self.log)
            self.worker.finished_signal.connect(self.on_worker_finished)
            self.progress_cancel_btn.clicked.connect(self.cancel_generation)
            
            # Start thread execution
            self.worker.start()
            
            # Start watchdog
            self.last_progress_time = time.time()
            self.watchdog_timer = QTimer(self)
            self.watchdog_timer.timeout.connect(self.check_worker_watchdog)
            self.watchdog_timer.start(2000)
            
            # Show progress overlay dialog
            self.generation_progress_dialog.show()
            
        except Exception as e:
            QMessageBox.critical(self, "CAM Engine Error", f"Initialization failed:\n{str(e)}")
            self.log(f"[CAM] Initialization error: {str(e)}")
            self.is_generating = False
            self.btn_compile.setEnabled(True)
            self.progress_bar.setVisible(False)

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StoneCAMApp()
    window.show()
    sys.exit(app.exec())
