from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QLineEdit, QComboBox, QCheckBox, QGroupBox, QFrame
)
from PySide6.QtGui import QFont

class SurfaceOptimizationView(QWidget):
    """
    Surface Optimization and Base Cleanup preprocessing control panel.
    Allows adjusting flattening, edge protection, smoothing, and compression parameters.
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
        lbl_title = QLabel("🎛 Advanced Surface Optimization & Base Cleanup")
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_title.setStyleSheet("color: #00d2ff;")
        main_layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Configure real-time heightmap preprocessing to flatten raw base planes, "
            "protect detail edges, remove noise, and optimize toolpath compression."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #a0a0b0; font-size: 13px; margin-bottom: 10px;")
        main_layout.addWidget(lbl_desc)

        # Section 1: Base Flattening
        grp_base = QGroupBox("1. Flat Base Detection & Leveling")
        grid_base = QGridLayout(grp_base)
        grid_base.setSpacing(10)

        self.chk_flatten_selected = QCheckBox("Flatten Selected Base Color")
        self.chk_flatten_selected.setStyleSheet("font-weight: bold; color: #00d2ff;")
        self.chk_flatten_selected.toggled.connect(self.on_param_changed)
        grid_base.addWidget(self.chk_flatten_selected, 0, 0, 1, 2)

        grid_base.addWidget(QLabel("Base Color Tolerance (0-255):"), 1, 0)
        self.txt_base_tol = QLineEdit()
        self.txt_base_tol.setPlaceholderText("5.0")
        self.txt_base_tol.textChanged.connect(self.on_param_changed)
        grid_base.addWidget(self.txt_base_tol, 1, 1)

        self.chk_flatten_all = QCheckBox("Flatten All Flat Regions Automatically")
        self.chk_flatten_all.setStyleSheet("font-weight: bold; color: #00d2ff;")
        self.chk_flatten_all.toggled.connect(self.on_param_changed)
        grid_base.addWidget(self.chk_flatten_all, 2, 0, 1, 2)

        grid_base.addWidget(QLabel("Gradient Slope Tolerance:"), 3, 0)
        self.txt_slope_tol = QLineEdit()
        self.txt_slope_tol.setPlaceholderText("1.0")
        self.txt_slope_tol.textChanged.connect(self.on_param_changed)
        grid_base.addWidget(self.txt_slope_tol, 3, 1)

        main_layout.addWidget(grp_base)

        # Section 2: Edge Protection & Filtering
        grp_protect = QGroupBox("2. Edge Protection & Region Filtering")
        grid_protect = QGridLayout(grp_protect)
        grid_protect.setSpacing(10)

        self.chk_preserve_edges = QCheckBox("Preserve Detail Near Relief Edges (Edge Protection)")
        self.chk_preserve_edges.setStyleSheet("font-weight: bold; color: #00d2ff;")
        self.chk_preserve_edges.toggled.connect(self.on_param_changed)
        grid_protect.addWidget(self.chk_preserve_edges, 0, 0, 1, 2)

        grid_protect.addWidget(QLabel("Edge Protection Distance (mm):"), 1, 0)
        self.txt_edge_dist = QLineEdit()
        self.txt_edge_dist.setPlaceholderText("1.0")
        self.txt_edge_dist.textChanged.connect(self.on_param_changed)
        grid_protect.addWidget(self.txt_edge_dist, 1, 1)

        grid_protect.addWidget(QLabel("Minimum Base Region Size (pixels):"), 2, 0)
        self.txt_min_region = QLineEdit()
        self.txt_min_region.setPlaceholderText("100")
        self.txt_min_region.textChanged.connect(self.on_param_changed)
        grid_protect.addWidget(self.txt_min_region, 2, 1)

        main_layout.addWidget(grp_protect)

        # Section 3: Smoothing
        grp_smooth = QGroupBox("3. Surface Smoothing & Noise Filters")
        grid_smooth = QGridLayout(grp_smooth)
        grid_smooth.setSpacing(10)

        grid_smooth.addWidget(QLabel("Intelligent Surface Smoothing:"), 0, 0)
        self.cmb_smoothing = QComboBox()
        self.cmb_smoothing.addItems(["Off", "Light", "Medium", "Aggressive"])
        self.cmb_smoothing.currentIndexChanged.connect(self.on_param_changed)
        grid_smooth.addWidget(self.cmb_smoothing, 0, 1)

        main_layout.addWidget(grp_smooth)

        # Section 4: Global Cleaning
        grp_gcode = QGroupBox("4. Global Toolpath & G-code Optimization")
        grid_gcode = QGridLayout(grp_gcode)
        grid_gcode.setSpacing(10)

        grid_gcode.addWidget(QLabel("Minimum Z Variation To Keep (mm):"), 0, 0)
        self.txt_min_z_var = QLineEdit()
        self.txt_min_z_var.setPlaceholderText("0.05")
        self.txt_min_z_var.textChanged.connect(self.on_param_changed)
        grid_gcode.addWidget(self.txt_min_z_var, 0, 1)

        grid_gcode.addWidget(QLabel("Collinear Compression Tolerance (mm):"), 1, 0)
        self.txt_compress_tol = QLineEdit()
        self.txt_compress_tol.setPlaceholderText("0.05")
        self.txt_compress_tol.textChanged.connect(self.on_param_changed)
        grid_gcode.addWidget(self.txt_compress_tol, 1, 1)

        main_layout.addWidget(grp_gcode)

        # Section 5: Safety Warnings Box
        self.warn_frame = QFrame()
        self.warn_frame.setFrameShape(QFrame.StyledPanel)
        self.warn_frame.setStyleSheet("""
            QFrame {
                background-color: #2e1d0c;
                border: 1px solid #d48000;
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
        
        self.chk_flatten_selected.setChecked(project.opt_flatten_selected_base)
        self.txt_base_tol.setText(str(project.opt_base_tolerance))
        self.chk_flatten_all.setChecked(project.opt_flatten_all_flat)
        self.txt_slope_tol.setText(str(project.opt_flat_slope_tol))
        self.chk_preserve_edges.setChecked(project.opt_preserve_edges)
        self.txt_edge_dist.setText(str(project.opt_edge_distance_mm))
        self.txt_min_region.setText(str(project.opt_min_region_size))
        
        idx = self.cmb_smoothing.findText(project.opt_smoothing_level)
        if idx >= 0:
            self.cmb_smoothing.setCurrentIndex(idx)
            
        self.txt_min_z_var.setText(str(project.opt_min_z_variation))
        self.txt_compress_tol.setText(str(project.opt_compression_tol))
        
        self.block_signals = False
        self.validate_safety()

    def save_to_project(self):
        if not self.project:
            return
        
        try:
            self.project.opt_flatten_selected_base = self.chk_flatten_selected.isChecked()
            self.project.opt_base_tolerance = float(self.txt_base_tol.text())
            self.project.opt_flatten_all_flat = self.chk_flatten_all.isChecked()
            self.project.opt_flat_slope_tol = float(self.txt_slope_tol.text())
            self.project.opt_preserve_edges = self.chk_preserve_edges.isChecked()
            self.project.opt_edge_distance_mm = float(self.txt_edge_dist.text())
            self.project.opt_min_region_size = int(self.txt_min_region.text())
            self.project.opt_smoothing_level = self.cmb_smoothing.currentText()
            self.project.opt_min_z_variation = float(self.txt_min_z_var.text())
            self.project.opt_compression_tol = float(self.txt_compress_tol.text())
        except ValueError:
            pass # Keep current state if entry is incomplete/invalid

    def on_param_changed(self):
        if self.block_signals:
            return
        self.save_to_project()
        self.validate_safety()
        self.parameters_changed.emit()

    def validate_safety(self):
        if not self.project:
            return
            
        warnings = []
        
        # Check base tolerance
        if self.project.opt_flatten_selected_base and self.project.opt_base_tolerance > 30.0:
            warnings.append("⚠️ Base Color Tolerance is high (>30), which may flatten slope transitions or detail areas.")
            
        # Check smoothing + edge protection
        if self.project.opt_smoothing_level == "Aggressive" and not self.project.opt_preserve_edges:
            warnings.append("⚠️ Aggressive Surface Smoothing is active without Edge Protection. Relief contours may blur.")
            
        # Check high Z variation
        if self.project.opt_min_z_variation > 0.2:
            warnings.append("⚠️ Minimum Z Variation threshold is unusually high (>0.2mm). Fine vertical details could be flattened.")
            
        # Check high compression tolerance
        if self.project.opt_compression_tol > 0.2:
            warnings.append("⚠️ Collinear Compression Tolerance is high (>0.2mm). G-code points will be heavily reduced, possibly losing shape accuracy.")

        if warnings:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #2e1d0c;
                    border: 1px solid #ff9900;
                    border-radius: 6px;
                }
            """)
            self.lbl_warning.setText("\n".join(warnings))
            self.warn_frame.show()
        else:
            self.warn_frame.setStyleSheet("""
                QFrame {
                    background-color: #112211;
                    border: 1px solid #33aa33;
                    border-radius: 6px;
                }
            """)
            self.lbl_warning.setText("✅ Safety Validation: Settings within safe engineering thresholds.")
            self.warn_frame.show()
