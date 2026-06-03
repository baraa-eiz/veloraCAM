import os
import json
import time

class Project:
    """
    Project model encapsulating all parameters, stock settings, operation stack, 
    and output specifications for a Velora CNC CAM job.
    """
    def __init__(self):
        self.file_path = None
        self.module_type = "Stone Relief"
        self.image_path = ""
        
        # Physical workpiece stock configuration
        self.stock_x = 300.0
        self.stock_y = 300.0
        self.max_depth = 15.0
        self.zero_point = 0  # 0=Front-Left, 1=Front-Right, 2=Back-Left, 3=Back-Right, 4=Center
        self.preserve_aspect = True
        self.swap_axes = False
        self.base_color = None
        self.invert_check = False
        self.retract_between_passes = True
        
        # Surface Optimization Settings
        self.opt_flatten_selected_base = False
        self.opt_base_tolerance = 5.0
        self.opt_flatten_all_flat = False
        self.opt_flat_slope_tol = 1.0
        self.opt_preserve_edges = False
        self.opt_edge_distance_mm = 1.0
        self.opt_min_region_size = 100
        self.opt_smoothing_level = "Off"
        self.opt_min_z_variation = 0.05
        self.opt_compression_tol = 0.05
        
        # Curved Base Surface Compensation Settings
        self.curve_enabled = False
        self.curve_direction = "X Axis"
        self.curve_diagonal_dir = "Top Left -> Bottom Right"
        self.curve_control_points = [
            {"pos": 0.0, "z": 0.0},
            {"pos": 100.0, "z": 0.0}
        ]
        self.curve_interpolation_type = "Smooth Spline"
        self.curve_smoothness = 50.0
        self.curve_reference_mode = "Lock Center Plane"
        self.curve_limit_max_pos = 50.0
        self.curve_limit_max_neg = -50.0
        
        # libraries selection
        self.material_name = "Soft Wood"
        self.machine_name = "Generic Stone Router"
        
        # Operations
        self.operations = []  # List of dictionaries, each describing a CAM operation
        self.export_mode = "Single File"  # "Single File", "Separate per Tool", "Separate per Op"
        
        # Undo/Redo Stack
        self.undo_stack = []
        self.redo_stack = []
        self.max_stack_size = 20
 
    def serialize(self):
        """Serializes current project state into a clean dictionary."""
        return {
            "version": "2.0.0",
            "module_type": self.module_type,
            "image_path": self.image_path,
            "stock_x": self.stock_x,
            "stock_y": self.stock_y,
            "max_depth": self.max_depth,
            "zero_point": self.zero_point,
            "preserve_aspect": self.preserve_aspect,
            "swap_axes": self.swap_axes,
            "base_color": self.base_color,
            "invert_check": self.invert_check,
            "retract_between_passes": self.retract_between_passes,
            "opt_flatten_selected_base": self.opt_flatten_selected_base,
            "opt_base_tolerance": self.opt_base_tolerance,
            "opt_flatten_all_flat": self.opt_flatten_all_flat,
            "opt_flat_slope_tol": self.opt_flat_slope_tol,
            "opt_preserve_edges": self.opt_preserve_edges,
            "opt_edge_distance_mm": self.opt_edge_distance_mm,
            "opt_min_region_size": self.opt_min_region_size,
            "opt_smoothing_level": self.opt_smoothing_level,
            "opt_min_z_variation": self.opt_min_z_variation,
            "opt_compression_tol": self.opt_compression_tol,
            "curve_enabled": self.curve_enabled,
            "curve_direction": self.curve_direction,
            "curve_diagonal_dir": self.curve_diagonal_dir,
            "curve_control_points": self.curve_control_points,
            "curve_interpolation_type": self.curve_interpolation_type,
            "curve_smoothness": self.curve_smoothness,
            "curve_reference_mode": self.curve_reference_mode,
            "curve_limit_max_pos": self.curve_limit_max_pos,
            "curve_limit_max_neg": self.curve_limit_max_neg,
            "material_name": self.material_name,
            "machine_name": self.machine_name,
            "operations": self.operations,
            "export_mode": self.export_mode
        }
 
    def deserialize(self, data):
        """Loads project settings from serialized dictionary state."""
        self.module_type = data.get("module_type", "Stone Relief")
        self.image_path = data.get("image_path", "")
        self.stock_x = data.get("stock_x", 300.0)
        self.stock_y = data.get("stock_y", 300.0)
        self.max_depth = data.get("max_depth", 15.0)
        self.zero_point = data.get("zero_point", 0)
        self.preserve_aspect = data.get("preserve_aspect", True)
        self.swap_axes = data.get("swap_axes", False)
        self.base_color = data.get("base_color", None)
        self.invert_check = data.get("invert_check", False)
        self.retract_between_passes = data.get("retract_between_passes", True)
        self.opt_flatten_selected_base = data.get("opt_flatten_selected_base", False)
        self.opt_base_tolerance = data.get("opt_base_tolerance", 5.0)
        self.opt_flatten_all_flat = data.get("opt_flatten_all_flat", False)
        self.opt_flat_slope_tol = data.get("opt_flat_slope_tol", 1.0)
        self.opt_preserve_edges = data.get("opt_preserve_edges", False)
        self.opt_edge_distance_mm = data.get("opt_edge_distance_mm", 1.0)
        self.opt_min_region_size = data.get("opt_min_region_size", 100)
        self.opt_smoothing_level = data.get("opt_smoothing_level", "Off")
        self.opt_min_z_variation = data.get("opt_min_z_variation", 0.05)
        self.opt_compression_tol = data.get("opt_compression_tol", 0.05)
        
        self.curve_enabled = data.get("curve_enabled", False)
        self.curve_direction = data.get("curve_direction", "X Axis")
        self.curve_diagonal_dir = data.get("curve_diagonal_dir", "Top Left -> Bottom Right")
        self.curve_control_points = data.get("curve_control_points", [
            {"pos": 0.0, "z": 0.0},
            {"pos": 100.0, "z": 0.0}
        ])
        self.curve_interpolation_type = data.get("curve_interpolation_type", "Smooth Spline")
        self.curve_smoothness = data.get("curve_smoothness", 50.0)
        self.curve_reference_mode = data.get("curve_reference_mode", "Lock Center Plane")
        self.curve_limit_max_pos = data.get("curve_limit_max_pos", 50.0)
        self.curve_limit_max_neg = data.get("curve_limit_max_neg", -50.0)
        
        self.material_name = data.get("material_name", "Soft Wood")
        self.machine_name = data.get("machine_name", "Generic Stone Router")
        self.operations = data.get("operations", [])
        self.export_mode = data.get("export_mode", "Single File")

    def save_snapshot(self):
        """Saves current state snapshot to the Undo stack. Clears the Redo stack."""
        state = json.dumps(self.serialize())
        # Prevent duplicate snapshots
        if self.undo_stack and self.undo_stack[-1] == state:
            return
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        """Reverts to the previous snapshot if available."""
        if len(self.undo_stack) < 2:
            # We need at least the current state and a previous state to revert
            return False
        current_state = self.undo_stack.pop()
        self.redo_stack.append(current_state)
        previous_state = self.undo_stack[-1]
        
        self.deserialize(json.loads(previous_state))
        return True

    def redo(self):
        """Restores a previously undone snapshot."""
        if not self.redo_stack:
            return False
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        
        self.deserialize(json.loads(state))
        return True

    def save_to_file(self, file_path):
        """Saves project to local disk."""
        self.file_path = file_path
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.serialize(), f, indent=4)

    def load_from_file(self, file_path):
        """Loads project from local disk."""
        self.file_path = file_path
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.deserialize(data)
        # Clear Undo/Redo on file open and push first state
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.save_snapshot()

    def get_autosave_path(self):
        home = os.path.expanduser("~")
        return os.path.join(home, ".veloracnc", "crash_recovery.vproj")

    def perform_autosave(self):
        """Saves a temporary recovery copy in the background."""
        try:
            recovery_dir = os.path.dirname(self.get_autosave_path())
            os.makedirs(recovery_dir, exist_ok=True)
            with open(self.get_autosave_path(), "w", encoding="utf-8") as f:
                json.dump(self.serialize(), f, indent=4)
        except Exception:
            pass

    def check_recovery(self):
        """Checks if a recovery session exists."""
        path = self.get_autosave_path()
        return os.path.exists(path)

    def recover_session(self):
        """Recovers state from a previous crash."""
        path = self.get_autosave_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.deserialize(data)
            # Remove recovery file after success
            try:
                os.remove(path)
            except Exception:
                pass
            return True
        return False
