from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QCheckBox, QGroupBox, QFrame, QPushButton
)
from PySide6.QtGui import QFont

from core.engine import CAMEngine
from ui.curve_editor import CurveProfileEditor

class CurveCompensationView(QWidget):
    """
    Control panel for Curved Base Surface Compensation settings.
    Allows configuring projection direction, reference anchor, and launching the curve editor.
    """
    parameters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.block_signals = False
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header Info Card
        lbl_title = QLabel("🔄 Curved Base Surface Compensation")
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_title.setStyleSheet("color: #00d2ff;")
        main_layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Map toolpaths onto non-flat (cylindrical, spherical, or custom curved) surfaces. "
            "Keeps the original image projection flat (non-stretching) and shifts Z values accordingly."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #a0a0b0; font-size: 13px; margin-bottom: 10px;")
        main_layout.addWidget(lbl_desc)

        # 1. Enable / Disable
        grp_enable = QGroupBox("1. Activation State")
        layout_enable = QVBoxLayout(grp_enable)
        
        self.chk_enabled = QCheckBox("Enable Curved Base Compensation")
        self.chk_enabled.setStyleSheet("font-weight: bold; color: #00d2ff; font-size: 13px;")
        self.chk_enabled.toggled.connect(self.on_param_changed)
        layout_enable.addWidget(self.chk_enabled)
        
        main_layout.addWidget(grp_enable)

        # 2. General Settings
        grp_settings = QGroupBox("2. Coordinate Mapping Settings")
        grid_settings = QGridLayout(grp_settings)
        grid_settings.setSpacing(10)

        grid_settings.addWidget(QLabel("Profile Direction:"), 0, 0)
        self.cmb_direction = QComboBox()
        self.cmb_direction.addItems(["X Axis", "Y Axis", "Diagonal"])
        self.cmb_direction.currentIndexChanged.connect(self.on_direction_changed)
        grid_settings.addWidget(self.cmb_direction, 0, 1)

        self.lbl_diagonal_dir = QLabel("Diagonal Angle:")
        self.cmb_diagonal_dir = QComboBox()
        self.cmb_diagonal_dir.addItems(["Top Left -> Bottom Right", "Bottom Left -> Top Right"])
        self.cmb_diagonal_dir.currentIndexChanged.connect(self.on_param_changed)
        
        grid_settings.addWidget(self.lbl_diagonal_dir, 1, 0)
        grid_settings.addWidget(self.cmb_diagonal_dir, 1, 1)

        grid_settings.addWidget(QLabel("Reference Anchor:"), 2, 0)
        self.cmb_ref = QComboBox()
        self.cmb_ref.addItems([
            "Lock Minimum Z",
            "Lock Maximum Z",
            "Lock Center Plane",
            "Lock Start Point",
            "Lock End Point"
        ])
        self.cmb_ref.currentIndexChanged.connect(self.on_param_changed)
        grid_settings.addWidget(self.cmb_ref, 2, 1)

        main_layout.addWidget(grp_settings)

        # 3. Curve Editor Launcher
        grp_editor = QGroupBox("3. Surface Profile Editor")
        layout_editor = QVBoxLayout(grp_editor)
        layout_editor.setSpacing(10)

        self.btn_edit_profile = QPushButton("📐 Open Interactive Profile Editor...")
        self.btn_edit_profile.setStyleSheet("""
            QPushButton {
                background-color: #3b3b4f;
                border: 1px solid #5a5a7a;
                font-weight: bold;
                padding: 8px 12px;
                color: #ffffff;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0088cc;
                border-color: #00aaff;
            }
        """)
        self.btn_edit_profile.clicked.connect(self.open_profile_editor)
        layout_editor.addWidget(self.btn_edit_profile)
        
        main_layout.addWidget(grp_editor)

        # 4. Status and Safety Warnings Box
        self.warn_frame = QFrame()
        self.warn_frame.setFrameShape(QFrame.StyledPanel)
        self.warn_frame.setStyleSheet("""
            QFrame {
                background-color: #112211;
                border: 1px solid #33aa33;
                border-radius: 6px;
            }
        """)
        warn_layout = QVBoxLayout(self.warn_frame)
        warn_layout.setContentsMargins(12, 12, 12, 12)

        self.lbl_warning = QLabel("Safety Validation: Settings within normal bounds.")
        self.lbl_warning.setStyleSheet("color: #ffaa44; font-weight: bold;")
        self.lbl_warning.setWordWrap(True)
        warn_layout.addWidget(self.lbl_warning)
        main_layout.addWidget(self.warn_frame)

        main_layout.addStretch()

    def set_project(self, project):
        self.project = project
        self.block_signals = True

        self.chk_enabled.setChecked(project.curve_enabled)
        
        idx = self.cmb_direction.findText(project.curve_direction)
        if idx >= 0: self.cmb_direction.setCurrentIndex(idx)
        
        idx = self.cmb_diagonal_dir.findText(project.curve_diagonal_dir)
        if idx >= 0: self.cmb_diagonal_dir.setCurrentIndex(idx)

        idx = self.cmb_ref.findText(project.curve_reference_mode)
        if idx >= 0: self.cmb_ref.setCurrentIndex(idx)

        # Enable/disable controls based on activation state
        self.update_ui_state()
        self.block_signals = False
        self.validate_safety()

    def update_ui_state(self):
        enabled = self.chk_enabled.isChecked()
        self.cmb_direction.setEnabled(enabled)
        self.cmb_ref.setEnabled(enabled)
        self.btn_edit_profile.setEnabled(enabled)
        
        # Diagonal combobox only enabled if Direction is Diagonal
        is_diag = (self.cmb_direction.currentText() == "Diagonal")
        self.lbl_diagonal_dir.setVisible(is_diag)
        self.cmb_diagonal_dir.setVisible(is_diag)
        self.cmb_diagonal_dir.setEnabled(enabled and is_diag)

    def on_direction_changed(self):
        self.update_ui_state()
        self.on_param_changed()

    def save_to_project(self):
        if not self.project:
            return
        try:
            self.project.curve_enabled = self.chk_enabled.isChecked()
            self.project.curve_direction = self.cmb_direction.currentText()
            self.project.curve_diagonal_dir = self.cmb_diagonal_dir.currentText()
            self.project.curve_reference_mode = self.cmb_ref.currentText()
        except ValueError:
            pass

    def on_param_changed(self):
        if self.block_signals:
            return
        self.save_to_project()
        self.validate_safety()
        self.parameters_changed.emit()

    def open_profile_editor(self):
        if not self.project:
            return
        dlg = CurveProfileEditor(self)
        dlg.load_from_project(self.project)
        if dlg.exec() == CurveProfileEditor.Accepted:
            dlg.save_to_project(self.project)
            self.validate_safety()
            self.parameters_changed.emit()

    def validate_safety(self):
        if not self.project:
            return

        if not self.project.curve_enabled:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #1f1f2e;
                    border: 1px solid #3d3d5c;
                    border-radius: 6px;
                }
            """)
            self.lbl_warning.setStyleSheet("color: #a0a0b0;")
            self.lbl_warning.setText("⚪ Curved base compensation is currently disabled. Original flat relief logic is active.")
            return

        # Perform curve math boundaries evaluation
        max_c_z = CAMEngine.get_curve_max_z({
            "curve_enabled": self.project.curve_enabled,
            "curve_direction": self.project.curve_direction,
            "curve_diagonal_dir": self.project.curve_diagonal_dir,
            "curve_control_points": self.project.curve_control_points,
            "curve_interpolation_type": self.project.curve_interpolation_type,
            "curve_smoothness": self.project.curve_smoothness,
            "curve_reference_mode": self.project.curve_reference_mode,
            "stock_x": self.project.stock_x,
            "stock_y": self.project.stock_y
        })

        warnings = []
        
        # Calculate dynamic range
        if max_c_z > 35.0:
            warnings.append(f"⚠️ High profile peak ({max_c_z:+.1f}mm). Ensure retract and clearance safety heights are sufficient.")
            
        if self.project.curve_direction == "Diagonal":
            warnings.append("ℹ️ Diagonal compensation profile is active. Projection boundaries will span diagonally across stock.")

        if warnings:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #2e1d0c;
                    border: 1px solid #ff9900;
                    border-radius: 6px;
                }
            """)
            self.lbl_warning.setStyleSheet("color: #ffaa44; font-weight: bold;")
            self.lbl_warning.setText("\n".join(warnings))
        else:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #112211;
                    border: 1px solid #33aa33;
                    border-radius: 6px;
                }
            """)
            self.lbl_warning.setStyleSheet("color: #44dd44; font-weight: bold;")
            self.lbl_warning.setText(f"✅ Compensation Active: Clearance and Z heights will scale dynamically (Max offset {max_c_z:+.1f}mm).")
