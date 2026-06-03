import os
import json
import numpy as np
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSlider, QDoubleSpinBox,
    QGroupBox, QFrame, QMessageBox, QFileDialog
)
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPainterPath

from core.engine import CAMEngine

class CurveCanvas(QWidget):
    """
    Interactive widget for plotting and editing control points of the compensation curve.
    """
    curve_changed = Signal()
    point_selected = Signal(int)  # index of selected point

    def __init__(self, parent=None):
        super().__init__(parent)
        self.control_points = []  # List of dicts: [{"pos": %, "z": mm}]
        self.selected_idx = -1
        self.dragging = False
        self.setMinimumSize(450, 300)
        self.setMouseTracking(True)
        
        # Grid settings
        self.z_min = -25.0
        self.z_max = 25.0
        self.margin = 35

        self.interpolation_type = "Smooth Spline"
        self.smoothness = 50.0

    def set_curve(self, control_points, interp_type, smoothness):
        self.control_points = sorted(control_points, key=lambda p: p["pos"])
        self.interpolation_type = interp_type
        self.smoothness = smoothness
        self.selected_idx = -1
        self.update_z_bounds()
        self.update()

    def update_z_bounds(self):
        # Auto adjust scale to fit points if they exceed defaults
        if not self.control_points:
            return
        z_vals = [p["z"] for p in self.control_points]
        min_z = min(z_vals) - 5.0
        max_z = max(z_vals) + 5.0
        
        self.z_min = min(-25.0, min_z)
        self.z_max = max(25.0, max_z)

    def to_screen(self, pos_pct, z_mm):
        w = self.width() - 2 * self.margin
        h = self.height() - 2 * self.margin
        
        x = self.margin + (pos_pct / 100.0) * w
        # Y goes downwards in screen coords, so invert
        y = self.margin + h - ((z_mm - self.z_min) / (self.z_max - self.z_min)) * h
        return x, y

    def to_logic(self, sx, sy):
        w = self.width() - 2 * self.margin
        h = self.height() - 2 * self.margin
        
        pos_pct = np.clip(((sx - self.margin) / w) * 100.0, 0.0, 100.0)
        z_mm = self.z_min + (1.0 - (sy - self.margin) / h) * (self.z_max - self.z_min)
        z_mm = np.clip(z_mm, self.z_min - 20, self.z_max + 20)
        return pos_pct, z_mm

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor("#1a1a24"))
        
        w = self.width() - 2 * self.margin
        h = self.height() - 2 * self.margin
        
        # Draw grid
        pen_grid = QPen(QColor("#2d2d3d"), 1, Qt.DashLine)
        painter.setPen(pen_grid)
        
        # Horizontal lines (Z grid)
        for z_grid in np.linspace(self.z_min, self.z_max, 9):
            _, sy = self.to_screen(0.0, z_grid)
            painter.drawLine(self.margin, sy, self.margin + w, sy)
            # Label
            painter.setPen(QColor("#7d7d8d"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(5, sy + 4, f"{z_grid:+.1f}")
            painter.setPen(pen_grid)

        # Vertical lines (Position grid)
        for pct in range(0, 101, 20):
            sx, _ = self.to_screen(pct, 0.0)
            painter.drawLine(sx, self.margin, sx, self.margin + h)
            # Label
            painter.setPen(QColor("#7d7d8d"))
            painter.drawText(sx - 10, self.height() - 5, f"{pct}%")
            painter.setPen(pen_grid)

        # Draw Z=0 Reference Line (heavier line)
        ref_pen = QPen(QColor("#ffaa00"), 1.5, Qt.SolidLine)
        painter.setPen(ref_pen)
        _, zero_y = self.to_screen(0.0, 0.0)
        painter.drawLine(self.margin, zero_y, self.margin + w, zero_y)
        painter.drawText(self.width() - 30, zero_y - 4, "Z0")

        # Draw the curve
        if len(self.control_points) >= 2:
            path = QPainterPath()
            sample_u = np.linspace(0.0, 1.0, 300)
            sample_z = CAMEngine.evaluate_curve(sample_u, self.control_points, self.interpolation_type, self.smoothness)
            
            sx, sy = self.to_screen(0.0, sample_z[0])
            path.moveTo(sx, sy)
            for u, z in zip(sample_u[1:], sample_z[1:]):
                sx, sy = self.to_screen(u * 100.0, z)
                path.lineTo(sx, sy)
                
            curve_pen = QPen(QColor("#00d2ff"), 2.5, Qt.SolidLine)
            painter.setPen(curve_pen)
            painter.drawPath(path)

        # Draw control points
        for idx, pt in enumerate(self.control_points):
            sx, sy = self.to_screen(pt["pos"], pt["z"])
            
            # Highlight selected point
            if idx == self.selected_idx:
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.setBrush(QBrush(QColor("#ff007f")))
                size = 10
            else:
                painter.setPen(QPen(QColor("#00d2ff"), 1.5))
                painter.setBrush(QBrush(QColor("#1a1a24")))
                size = 8
                
            painter.drawEllipse(QPointF(sx, sy), size/2, size/2)
            
            # Print label / values
            painter.setPen(QColor("#a0a0b0"))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(sx - 15, sy - 10, f"P{idx}: {pt['z']:+.1f}mm")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if clicked close to a control point
            click_pos = event.position()
            closest_idx = -1
            min_dist = 12.0 # threshold pixels
            
            for idx, pt in enumerate(self.control_points):
                sx, sy = self.to_screen(pt["pos"], pt["z"])
                dist = np.hypot(click_pos.x() - sx, click_pos.y() - sy)
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx
                    
            if closest_idx != -1:
                self.selected_idx = closest_idx
                self.dragging = True
                self.point_selected.emit(closest_idx)
                self.update()
            else:
                self.selected_idx = -1
                self.point_selected.emit(-1)
                self.update()

    def mouseMoveEvent(self, event):
        if self.dragging and self.selected_idx != -1:
            cx, cy = self.to_logic(event.position().x(), event.position().y())
            pt = self.control_points[self.selected_idx]
            
            # Z adjustment (can be done for all points)
            pt["z"] = round(cy, 2)
            
            # Horizontal adjustment (not for start and end)
            if self.selected_idx > 0 and self.selected_idx < len(self.control_points) - 1:
                # Clamp position between preceding and succeeding points to prevent crossing
                prev_pos = self.control_points[self.selected_idx - 1]["pos"]
                next_pos = self.control_points[self.selected_idx + 1]["pos"]
                pt["pos"] = round(max(prev_pos + 1.0, min(next_pos - 1.0, cx)), 1)
            elif self.selected_idx == 0:
                pt["pos"] = 0.0
            elif self.selected_idx == len(self.control_points) - 1:
                pt["pos"] = 100.0
                
            self.curve_changed.emit()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.update_z_bounds()
            self.update()


class CurveProfileEditor(QDialog):
    """
    Dialog for configuring the curved surface profile parameters.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curved Base Surface Compensation Profile Editor")
        self.setModal(True)
        self.resize(750, 520)
        
        # Color styling
        self.setStyleSheet("""
            QDialog {
                background-color: #22222e;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1.5px solid #3d3d5c;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #ffaa00;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                font-size: 12px;
            }
            QPushButton {
                background-color: #3b3b4f;
                border: 1px solid #5a5a7a;
                border-radius: 4px;
                padding: 5px 12px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4c4c66;
            }
            QPushButton:pressed {
                background-color: #2c2c3b;
            }
            QComboBox {
                background-color: #2a2a3a;
                border: 1px solid #5a5a7a;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #3b3b4f;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00d2ff;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)

        self.control_points = []
        self.setup_ui()
        self.selected_point_idx = -1

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Left Column: Canvas View
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("📈 <b>Interactive Profile Curve Editor</b> (Drag points to edit, Z=0 is original base)"))
        
        self.canvas = CurveCanvas(self)
        self.canvas.curve_changed.connect(self.on_canvas_curve_changed)
        self.canvas.point_selected.connect(self.on_point_selected_on_canvas)
        left_layout.addWidget(self.canvas)
        
        # Warning/Status box below canvas
        self.warn_frame = QFrame()
        self.warn_frame.setFrameShape(QFrame.StyledPanel)
        self.warn_frame.setStyleSheet("""
            QFrame {
                background-color: #1a221a;
                border: 1.5px solid #33aa33;
                border-radius: 6px;
            }
        """)
        warn_layout = QVBoxLayout(self.warn_frame)
        warn_layout.setContentsMargins(10, 8, 10, 8)
        self.lbl_warn = QLabel("✅ Calibration Status: Curve meets safety parameters.")
        self.lbl_warn.setStyleSheet("color: #44dd44; font-weight: bold;")
        self.lbl_warn.setWordWrap(True)
        warn_layout.addWidget(self.lbl_warn)
        left_layout.addWidget(self.warn_frame)

        main_layout.addLayout(left_layout, 2)

        # Right Column: Controls Panel
        right_layout = QVBoxLayout()
        
        # 1. Select / Modify control points
        grp_points = QGroupBox("1. Control Points Manager")
        grid_points = QGridLayout(grp_points)
        
        grid_points.addWidget(QLabel("Selected Point:"), 0, 0)
        self.lbl_selected_point = QLabel("None")
        self.lbl_selected_point.setStyleSheet("font-weight: bold; color: #ff007f;")
        grid_points.addWidget(self.lbl_selected_point, 0, 1)

        grid_points.addWidget(QLabel("Position (%):"), 1, 0)
        self.spn_pos = QDoubleSpinBox()
        self.spn_pos.setRange(0.0, 100.0)
        self.spn_pos.setSingleStep(1.0)
        self.spn_pos.setSuffix("%")
        self.spn_pos.setEnabled(False)
        self.spn_pos.valueChanged.connect(self.on_numeric_pos_changed)
        grid_points.addWidget(self.spn_pos, 1, 1)

        grid_points.addWidget(QLabel("Z Offset (mm):"), 2, 0)
        self.spn_z = QDoubleSpinBox()
        self.spn_z.setRange(-200.0, 200.0)
        self.spn_z.setSingleStep(0.5)
        self.spn_z.setSuffix(" mm")
        self.spn_z.setEnabled(False)
        self.spn_z.valueChanged.connect(self.on_numeric_z_changed)
        grid_points.addWidget(self.spn_z, 2, 1)

        btn_add = QPushButton("➕ Add Point")
        btn_add.clicked.connect(self.add_control_point)
        grid_points.addWidget(btn_add, 3, 0)

        self.btn_remove = QPushButton("❌ Remove Selected")
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self.remove_selected_point)
        grid_points.addWidget(self.btn_remove, 3, 1)
        
        right_layout.addWidget(grp_points)

        # 2. Curve Interpolation Settings
        grp_interp = QGroupBox("2. Interpolation & Reference")
        grid_interp = QGridLayout(grp_interp)

        grid_interp.addWidget(QLabel("Interpolation Mode:"), 0, 0)
        self.cmb_interp = QComboBox()
        self.cmb_interp.addItems(["Linear", "Smooth Spline", "Rounded / Soft Curve"])
        self.cmb_interp.currentIndexChanged.connect(self.on_params_changed)
        grid_interp.addWidget(self.cmb_interp, 0, 1)

        grid_interp.addWidget(QLabel("Curve Smoothness:"), 1, 0)
        self.slider_smooth = QSlider(Qt.Horizontal)
        self.slider_smooth.setRange(0, 100)
        self.slider_smooth.valueChanged.connect(self.on_params_changed)
        grid_interp.addWidget(self.slider_smooth, 1, 1)

        grid_interp.addWidget(QLabel("Reference Anchor:"), 2, 0)
        self.cmb_ref = QComboBox()
        self.cmb_ref.addItems([
            "Lock Minimum Z",
            "Lock Maximum Z",
            "Lock Center Plane",
            "Lock Start Point",
            "Lock End Point"
        ])
        self.cmb_ref.currentIndexChanged.connect(self.on_params_changed)
        grid_interp.addWidget(self.cmb_ref, 2, 1)

        right_layout.addWidget(grp_interp)

        # 3. Presets & Utilities
        grp_presets = QGroupBox("3. Presets & Actions")
        grid_presets = QGridLayout(grp_presets)

        grid_presets.addWidget(QLabel("Apply Preset Profile:"), 0, 0)
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(["-- Select Preset --", "Flat", "Single Arc (Bow)", "Valley", "Dome", "Wave / Ripple", "S-Curve"])
        self.cmb_preset.currentIndexChanged.connect(self.apply_preset)
        grid_presets.addWidget(self.cmb_preset, 0, 1)

        btn_invert = QPushButton("🔃 Invert Profile (Negate Z)")
        btn_invert.clicked.connect(self.invert_profile)
        grid_presets.addWidget(btn_invert, 1, 0, 1, 2)

        btn_save = QPushButton("💾 Save Profile")
        btn_save.clicked.connect(self.save_profile_file)
        grid_presets.addWidget(btn_save, 2, 0)

        btn_load = QPushButton("📂 Load Profile")
        btn_load.clicked.connect(self.load_profile_file)
        grid_presets.addWidget(btn_load, 2, 1)

        right_layout.addWidget(grp_presets)

        right_layout.addStretch()

        # Dialog Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Curve")
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #0088cc;
                font-weight: bold;
                border: 1px solid #00aaff;
            }
            QPushButton:hover {
                background-color: #00aaff;
            }
        """)
        btn_apply.clicked.connect(self.accept)
        btn_layout.addWidget(btn_apply)
        
        right_layout.addLayout(btn_layout)

        main_layout.addLayout(right_layout, 1)

    def load_from_project(self, project):
        self.control_points = json.loads(json.dumps(project.curve_control_points))  # deep copy
        
        # Load comboboxes and sliders
        idx = self.cmb_interp.findText(project.curve_interpolation_type)
        if idx >= 0: self.cmb_interp.setCurrentIndex(idx)
        
        idx = self.cmb_ref.findText(project.curve_reference_mode)
        if idx >= 0: self.cmb_ref.setCurrentIndex(idx)
        
        self.slider_smooth.setValue(int(project.curve_smoothness))
        
        self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
        self.update_safety_check(project.max_depth)

    def save_to_project(self, project):
        project.curve_control_points = sorted(self.control_points, key=lambda p: p["pos"])
        project.curve_interpolation_type = self.cmb_interp.currentText()
        project.curve_reference_mode = self.cmb_ref.currentText()
        project.curve_smoothness = float(self.slider_smooth.value())

    def on_canvas_curve_changed(self):
        self.control_points = self.canvas.control_points
        # Update spinboxes without triggering signals to avoid loop
        if self.selected_point_idx != -1:
            pt = self.control_points[self.selected_point_idx]
            self.spn_pos.blockSignals(True)
            self.spn_z.blockSignals(True)
            self.spn_pos.setValue(pt["pos"])
            self.spn_z.setValue(pt["z"])
            self.spn_pos.blockSignals(False)
            self.spn_z.blockSignals(False)
        self.update_safety_check()

    def on_point_selected_on_canvas(self, idx):
        self.selected_point_idx = idx
        if idx != -1:
            pt = self.control_points[idx]
            self.lbl_selected_point.setText(f"Point {idx}")
            self.spn_pos.setEnabled(idx > 0 and idx < len(self.control_points) - 1)
            self.spn_z.setEnabled(True)
            
            self.spn_pos.blockSignals(True)
            self.spn_z.blockSignals(True)
            self.spn_pos.setValue(pt["pos"])
            self.spn_z.setValue(pt["z"])
            self.spn_pos.blockSignals(False)
            self.spn_z.blockSignals(False)
            
            # Can remove only if it is not start or end point, and we have > 2 points
            self.btn_remove.setEnabled(idx > 0 and idx < len(self.control_points) - 1 and len(self.control_points) > 2)
        else:
            self.lbl_selected_point.setText("None")
            self.spn_pos.setEnabled(False)
            self.spn_z.setEnabled(False)
            self.btn_remove.setEnabled(False)

    def on_numeric_pos_changed(self, val):
        if self.selected_point_idx != -1:
            pt = self.control_points[self.selected_point_idx]
            pt["pos"] = val
            self.control_points = sorted(self.control_points, key=lambda p: p["pos"])
            self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
            self.selected_point_idx = self.control_points.index(pt)
            self.canvas.selected_idx = self.selected_point_idx
            self.on_canvas_curve_changed()
            self.canvas.update()

    def on_numeric_z_changed(self, val):
        if self.selected_point_idx != -1:
            pt = self.control_points[self.selected_point_idx]
            pt["z"] = val
            self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
            self.canvas.selected_idx = self.selected_point_idx
            self.on_canvas_curve_changed()
            self.canvas.update()

    def on_params_changed(self):
        interp = self.cmb_interp.currentText()
        smooth = self.slider_smooth.value()
        self.canvas.interpolation_type = interp
        self.canvas.smoothness = smooth
        self.canvas.update()
        self.update_safety_check()

    def add_control_point(self):
        # Insert point at 50% with average Z or 0.0
        # Check if 50% already exists, if so insert at 45% or 55%
        pos = 50.0
        existing_positions = [p["pos"] for p in self.control_points]
        while pos in existing_positions:
            pos += 5.0
            if pos >= 95.0:
                pos = 25.0
                
        self.control_points.append({"pos": pos, "z": 0.0})
        self.control_points = sorted(self.control_points, key=lambda p: p["pos"])
        self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
        self.on_point_selected_on_canvas(-1)
        self.update_safety_check()

    def remove_selected_point(self):
        if self.selected_point_idx != -1 and self.selected_point_idx > 0 and self.selected_point_idx < len(self.control_points) - 1:
            self.control_points.pop(self.selected_point_idx)
            self.control_points = sorted(self.control_points, key=lambda p: p["pos"])
            self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
            self.on_point_selected_on_canvas(-1)
            self.update_safety_check()

    def invert_profile(self):
        for pt in self.control_points:
            pt["z"] = -pt["z"]
        self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
        self.on_canvas_curve_changed()
        self.canvas.update()

    def apply_preset(self, index):
        if index == 0:
            return
            
        preset_name = self.cmb_preset.currentText()
        if preset_name == "Flat":
            self.control_points = [{"pos": 0.0, "z": 0.0}, {"pos": 100.0, "z": 0.0}]
        elif preset_name == "Single Arc (Bow)":
            self.control_points = [{"pos": 0.0, "z": 0.0}, {"pos": 50.0, "z": 15.0}, {"pos": 100.0, "z": 0.0}]
        elif preset_name == "Valley":
            self.control_points = [{"pos": 0.0, "z": 0.0}, {"pos": 50.0, "z": -15.0}, {"pos": 100.0, "z": 0.0}]
        elif preset_name == "Dome":
            self.control_points = [
                {"pos": 0.0, "z": 0.0},
                {"pos": 25.0, "z": 10.0},
                {"pos": 50.0, "z": 15.0},
                {"pos": 75.0, "z": 10.0},
                {"pos": 100.0, "z": 0.0}
            ]
        elif preset_name == "Wave / Ripple":
            self.control_points = [
                {"pos": 0.0, "z": 0.0},
                {"pos": 25.0, "z": 8.0},
                {"pos": 50.0, "z": 0.0},
                {"pos": 75.0, "z": -8.0},
                {"pos": 100.0, "z": 0.0}
            ]
        elif preset_name == "S-Curve":
            self.control_points = [
                {"pos": 0.0, "z": -10.0},
                {"pos": 33.0, "z": -6.0},
                {"pos": 66.0, "z": 6.0},
                {"pos": 100.0, "z": 10.0}
            ]
            
        self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
        self.on_point_selected_on_canvas(-1)
        self.update_safety_check()
        
        # Reset preset box to default
        self.cmb_preset.blockSignals(True)
        self.cmb_preset.setCurrentIndex(0)
        self.cmb_preset.blockSignals(False)

    def update_safety_check(self, max_depth_limit=25.0):
        # Calculate min / max offsets of the curve
        sample_u = np.linspace(0.0, 1.0, 200)
        z_vals = CAMEngine.evaluate_curve(
            sample_u, self.control_points,
            self.cmb_interp.currentText(),
            self.slider_smooth.value()
        )
        
        ref = CAMEngine.get_curve_reference_offset(
            self.control_points,
            self.cmb_interp.currentText(),
            self.slider_smooth.value(),
            self.cmb_ref.currentText()
        )
        
        offsets = z_vals - ref
        min_offset = np.min(offsets)
        max_offset = np.max(offsets)
        
        # Safety warning conditions
        warnings = []
        if min_offset < -35.0:
            warnings.append("⚠️ Extreme downward curve offset (< -35mm). Risk of over-travel or crashing table/vice.")
        if max_offset > 35.0:
            warnings.append("⚠️ Extreme upward curve offset (> 35mm). Risk of colliding with tool holder or spindle nose.")
        if (max_offset - min_offset) > max_depth_limit * 2.0:
            warnings.append("⚠️ Curve height variation is large compared to stock carving depth. Re-check clearances!")

        if warnings:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #2e1d0c;
                    border: 1.5px solid #ff9900;
                    border-radius: 6px;
                }
            """)
            self.lbl_warn.setStyleSheet("color: #ffaa44; font-weight: bold;")
            self.lbl_warn.setText("\n".join(warnings))
        else:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #112211;
                    border: 1.5px solid #33aa33;
                    border-radius: 6px;
                }
            """)
            self.lbl_warn.setStyleSheet("color: #44dd44; font-weight: bold;")
            self.lbl_warn.setText(f"✅ Calibration Safe: Min offset {min_offset:+.1f}mm, Max offset {max_offset:+.1f}mm.")

    def save_profile_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Surface Profile", "", "JSON Files (*.json)")
        if path:
            try:
                data = {
                    "curve_control_points": self.control_points,
                    "curve_interpolation_type": self.cmb_interp.currentText(),
                    "curve_reference_mode": self.cmb_ref.currentText(),
                    "curve_smoothness": float(self.slider_smooth.value())
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                QMessageBox.information(self, "Profile Saved", f"Profile exported to:\n{os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Could not save profile: {str(e)}")

    def load_profile_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Surface Profile", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                self.control_points = data["curve_control_points"]
                
                idx = self.cmb_interp.findText(data.get("curve_interpolation_type", "Smooth Spline"))
                if idx >= 0: self.cmb_interp.setCurrentIndex(idx)
                
                idx = self.cmb_ref.findText(data.get("curve_reference_mode", "Lock Center Plane"))
                if idx >= 0: self.cmb_ref.setCurrentIndex(idx)
                
                self.slider_smooth.setValue(int(data.get("curve_smoothness", 50.0)))
                
                self.canvas.set_curve(self.control_points, self.cmb_interp.currentText(), self.slider_smooth.value())
                self.on_point_selected_on_canvas(-1)
                self.update_safety_check()
                
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", f"Could not load profile: {str(e)}")
