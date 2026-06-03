import numpy as np
from modules.base_module import BaseModule
from core.engine import CAMEngine

class ACPPanelsModule(BaseModule):
    """
    CAM Module for Aluminum Composite Panel (ACP / Alucobond) routing and bending.
    Computes exact folding groove depths, slots, pockets, and contour cutouts.
    """
    def __init__(self):
        super().__init__("ACP Panels")

    def get_suggested_operations(self, material_preset=None, style_preset=None):
        """
        Preloads standard ACP fabrication operations stack.
        """
        op_groove = {
            "name": "Bending V-Grooves (90 deg)",
            "type": "V-Groove Bending",
            "enabled": True,
            "tool_id": "T4",  # 90 deg ACP V-Groove cutter
            "feed_xy": 4000.0,
            "feed_z": 1200.0,
            "feed_plunge": 600.0,
            "spindle_speed": 22000,
            "panel_thickness": 4.0,     # mm
            "remaining_backing": 0.8,   # mm (leaves skin + small backing for folding)
            "max_depth": 3.2,           # 4.0 - 0.8 = 3.2mm
            "safe_z": 10.0,
            "locked": False
        }
        
        op_contour = {
            "name": "Outer Contour Cutout",
            "type": "Contour Cutout",
            "enabled": True,
            "tool_id": "T5",  # 3mm Single Flute endmill
            "feed_xy": 3000.0,
            "feed_z": 800.0,
            "feed_plunge": 500.0,
            "spindle_speed": 18000,
            "stepdown": 2.0,            # 2 passes for 4mm panel
            "panel_thickness": 4.0,
            "max_depth": 4.1,           # Overcut slightly into spoilboard (0.1mm)
            "safe_z": 10.0,
            "locked": False
        }
        
        return [op_groove, op_contour]

    def validate_operation(self, op, tool_library, stock_x, stock_y, max_depth):
        """
        Validates sandwich panel composite thickness boundaries.
        """
        warnings = super().validate_operation(op, tool_library, stock_x, stock_y, max_depth)
        
        t_type = op.get("type", "")
        panel_thickness = op.get("panel_thickness", 4.0)
        
        if t_type == "V-Groove Bending":
            backing = op.get("remaining_backing", 0.8)
            groove_depth = panel_thickness - backing
            
            if groove_depth >= panel_thickness:
                warnings.append(f"Severe Cut Warning: Remaining backing is too thin ({backing}mm). Tool will cut completely through the panel!")
                
            if backing < 0.4:
                warnings.append(f"Core Fragility: Backing thickness ({backing}mm) is highly vulnerable to cracking during folding. 0.8mm is industrial standard.")
                
        return warnings

    def compile_toolpath(self, op, arr, project_params, progress_callback=None):
        """
        Compiles accurate sandwich ACP routing lines.
        """
        op_type = op.get("type", "V-Groove Bending")
        
        stock_x = project_params["stock_x"]
        stock_y = project_params["stock_y"]
        safe_z = op.get("safe_z", 10.0)
        
        carving_w = project_params["carving_w"]
        carving_h = project_params["carving_h"]
        min_x = project_params["min_x"]
        max_x = project_params["max_x"]
        min_y = project_params["min_y"]
        max_y = project_params["max_y"]
        offset_x = project_params["offset_x"]
        offset_y = project_params["offset_y"]
        preserve_aspect = project_params["preserve_aspect"]
        
        base_color = project_params.get("base_color", None)
        invert_check = project_params.get("invert_check", False)
        
        tool = project_params["tool"]
        ttype = tool["type"]
        
        toolpath_moves = []
        
        if op_type == "V-Groove Bending":
            # Compiles V-grooving vectors along the heightmap's deepest lines (folds)
            panel_thickness = op.get("panel_thickness", 4.0)
            backing = op.get("remaining_backing", 0.8)
            target_z = -(panel_thickness - backing)  # e.g., -3.2mm
            
            # Identify bend vectors: simple linear tracks corresponding to heightmap dark spots (pixels < 50)
            y_coords = np.arange(0.0, stock_y + 10.0, 10.0)  # Standard track spacing
            
            total_lines = len(y_coords)
            for idx, y in enumerate(y_coords):
                if progress_callback and idx % 10 == 0:
                    progress_callback(f"Grooving fold lines {idx+1}/{total_lines}", int((idx/total_lines)*100))
                    
                # Scan across X. If the image has a fold line (dark pixel), route down, otherwise travel rapid!
                xs = np.arange(0.0, stock_x + 2.0, 2.0)
                ys = np.full_like(xs, y)
                
                z_surfs = CAMEngine.compute_surface_z_vectorized(
                    xs, ys, arr, stock_x, stock_y, panel_thickness,
                    carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                    preserve_aspect, base_color, invert_check
                )
                
                # Active groove folding: only cut if the heightmap indicates a groove
                # Here we assume heightmap valleys (pixel depth < -1.0mm) represent bend tracks
                z_grooves = np.zeros_like(z_surfs)
                mask_groove = z_surfs < -1.0
                z_grooves[mask_groove] = target_z
                z_grooves[~mask_groove] = 0.0
                
                line_points = np.column_stack((xs, ys, z_grooves))
                compressed = CAMEngine.compress_path_3d(line_points, 0.02)
                
                for pt_idx, pt in enumerate(compressed):
                    cmd = "G01" if pt[2] < -0.1 else "G00"
                    if idx == 0 and pt_idx == 0:
                        toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                    elif pt_idx == 0:
                        toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                    toolpath_moves.append((pt[0], pt[1], pt[2], cmd))
                    
        elif op_type == "Contour Cutout":
            # Slices outer boundary contours in multi-pass steps
            panel_thickness = op.get("panel_thickness", 4.0)
            target_depth = op.get("max_depth", panel_thickness + 0.1)
            stepdown = op.get("stepdown", 2.0)
            
            border_x = [offset_x, offset_x + carving_w, offset_x + carving_w, offset_x, offset_x]
            border_y = [offset_y, offset_y, offset_y + carving_h, offset_y + carving_h, offset_y]
            
            z_levels = list(np.arange(-stepdown, -target_depth - 0.01, -stepdown))
            if not z_levels or z_levels[-1] > -target_depth:
                z_levels.append(-target_depth)
                
            for layer_idx, current_z in enumerate(z_levels):
                if progress_callback:
                    progress_callback(f"Contour Cutout Z={current_z:.1f}mm", int((layer_idx/len(z_levels))*100))
                    
                for pt_idx, (bx, by) in enumerate(zip(border_x, border_y)):
                    if layer_idx == 0 and pt_idx == 0:
                        toolpath_moves.append((bx, by, safe_z, "G00"))
                    toolpath_moves.append((bx, by, current_z, "G01"))
                    
        return toolpath_moves
