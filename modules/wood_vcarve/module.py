import numpy as np
from modules.base_module import BaseModule
from core.engine import CAMEngine

class WoodVCarveModule(BaseModule):
    """
    CAM Module for specialized V-Carving and engraving on wood.
    Computes variable-width cuts using flat clearing pre-passes and V-Bit geometry.
    """
    def __init__(self):
        super().__init__("Wood V-Carve")

    def get_suggested_operations(self, material_preset=None, style_preset=None):
        """
        Preloads multi-stage V-Carve operations stack.
        """
        op_clear = {
            "name": "Flat Clearing Pass (Pocket)",
            "type": "Flat Clearing",
            "enabled": True,
            "tool_id": "T2",  # 6mm Flat mill
            "feed_xy": 3000.0,
            "feed_z": 1000.0,
            "feed_plunge": 600.0,
            "spindle_speed": 18000,
            "stepover": 2.5,
            "stepdown": 3.0,
            "max_depth": 5.0,  # Clear down to pocket floor
            "stock_allowance": 0.2,
            "safe_z": 15.0,
            "locked": False
        }
        
        op_vcarve = {
            "name": "V-Bit Detailing Sweep",
            "type": "V-Carve Detailing",
            "enabled": True,
            "tool_id": "T3",  # 60 deg V-Bit
            "feed_xy": 2500.0,
            "feed_z": 1000.0,
            "feed_plunge": 500.0,
            "spindle_speed": 20000,
            "stepover": 0.4,
            "stepdown": 10.0,  # Engrave depth is geometric
            "max_depth": 8.0,
            "stock_allowance": 0.0,
            "safe_z": 15.0,
            "locked": False
        }
        
        if style_preset == "Conservative":
            op_clear["feed_xy"] = 2000.0
            op_vcarve["feed_xy"] = 1800.0
        elif style_preset == "Fast":
            op_clear["feed_xy"] = 4000.0
            op_vcarve["feed_xy"] = 3000.0
            
        return [op_clear, op_vcarve]

    def validate_operation(self, op, tool_library, stock_x, stock_y, max_depth):
        """
        Performs V-Bit specific geometric boundary checking.
        """
        warnings = super().validate_operation(op, tool_library, stock_x, stock_y, max_depth)
        
        tool_id = op.get("tool_id", "")
        tool = tool_library.get_tool(tool_id) if tool_library else None
        
        if tool and op.get("type") == "V-Carve Detailing":
            if tool.get("type") != "V-Bit" and tool.get("type") != "Tapered Ball Nose":
                warnings.append("Tool Type Warning: V-Carve detailing requires a V-Bit or Tapered Ball Nose cutter.")
                
            # Verify depth suitability based on taper geometry
            angle = tool.get("taper_angle", 60.0)
            max_dia = tool.get("max_diameter", 10.0)
            theta = np.radians(angle / 2.0)
            
            # Geometric max depth of V-bit cutting face
            geo_max_depth = (max_dia / 2.0) / max(1e-5, np.tan(theta))
            op_depth = op.get("max_depth", max_depth)
            
            if op_depth > geo_max_depth:
                warnings.append(f"Geometry Alert: Target depth ({op_depth}mm) exceeds V-Bit's maximum active cutting depth ({geo_max_depth:.1f}mm). Excess material will rub shank.")
                
        return warnings

    def compile_toolpath(self, op, arr, project_params, progress_callback=None):
        """
        Compiles precise V-carving toolpaths.
        """
        op_type = op.get("type", "V-Carve Detailing")
        
        stock_x = project_params["stock_x"]
        stock_y = project_params["stock_y"]
        max_depth = op.get("max_depth", project_params["max_depth"])
        safe_z = op.get("safe_z", 15.0)
        curve_params = project_params.get("curve_params", None)
        if curve_params and curve_params.get("curve_enabled", False):
            max_curve_z = CAMEngine.get_curve_max_z(curve_params)
            safe_z = safe_z + max(0.0, max_curve_z)
        
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
        retract_between_passes = project_params.get("retract_between_passes", True)
        
        tool = project_params["tool"]
        ttype = tool["type"]
        
        # Compression and variation tolerances
        rdp_tol = project_params.get("opt_compression_tol", 0.05)
        min_z_var = project_params.get("opt_min_z_variation", 0.05)
        
        geom_mode = project_params.get("toolpath_geometry_mode", "Legacy")
        toolpath_moves = []
        
        if op_type == "Flat Clearing":
            # 1. Pockets flat floor clearing (Roughing out areas where heightmap pixel >= threshold)
            stepdown = op.get("stepdown", 3.0)
            stepover = op.get("stepover", 2.0)
            threshold_z = -max_depth / 2.0  # Intermediate floor
            
            z_levels = list(np.arange(-stepdown, threshold_z - 0.01, -stepdown))
            if not z_levels or z_levels[-1] > threshold_z:
                z_levels.append(threshold_z)
                
            raster_dir = op.get("raster_direction", "Raster X")
            
            if raster_dir == "Raster Y":
                scan_coords = np.arange(0.0, stock_x + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_y + 2.0, 2.0)
            else:
                scan_coords = np.arange(0.0, stock_y + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_x + 2.0, 2.0)
                
            mach_coords_rev = mach_coords_fwd[::-1]
            
            for layer_idx, target_z in enumerate(z_levels):
                if progress_callback:
                    progress_callback(f"Pocket Clearing Z={target_z:.1f}mm", int((layer_idx/len(z_levels))*100))
                    
                for i, s in enumerate(scan_coords):
                    forward = (i % 2 == 0)
                    mach = mach_coords_fwd if forward else mach_coords_rev
                    
                    if raster_dir == "Raster Y":
                        ys = mach
                        xs = np.full_like(ys, s)
                    else:
                        xs = mach
                        ys = np.full_like(xs, s)
                    
                    z_surfs = CAMEngine.compute_surface_z_vectorized(
                        xs, ys, arr, stock_x, stock_y, max_depth,
                        carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                        preserve_aspect, base_color, invert_check, curve_params=curve_params
                    )
                    
                    # Pocket clear logic: Only cut where the surface is deep (below -1.0mm)
                    z_clears = np.zeros_like(z_surfs)
                    mask_cut = z_surfs < -1.0
                    z_clears[mask_cut] = np.maximum(z_surfs[mask_cut], target_z)
                    z_clears[~mask_cut] = 0.0  # Retract above stock top
                    
                    line_points = np.column_stack((xs, ys, z_clears))
                    line_points = CAMEngine.apply_min_z_variation_filter(line_points, min_z_var)
                    compressed = CAMEngine.compress_path_3d(line_points, rdp_tol)
                    
                    for idx, pt in enumerate(compressed):
                        cmd = "G01" if pt[2] < -0.1 else "G00"
                        if layer_idx == 0 and i == 0 and idx == 0:
                            toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                        elif idx == 0:
                            if retract_between_passes:
                                toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                        toolpath_moves.append((pt[0], pt[1], pt[2], cmd))
                        
        elif op_type == "V-Carve Detailing":
            # 2. Vectorized V-Bit detailing (follows full 3D contour carving with geometric taper)
            stepover = op.get("stepover", 0.5)
            resol_x = project_params.get("resol_x", 0.4)
            
            raster_dir = op.get("raster_direction", "Raster X")
            
            if raster_dir == "Raster Y":
                scan_coords = np.arange(0.0, stock_x + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_y + resol_x, resol_x)
            else:
                scan_coords = np.arange(0.0, stock_y + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_x + resol_x, resol_x)
                
            mach_coords_rev = mach_coords_fwd[::-1]
            
            total_lines = len(scan_coords)
            for i, s in enumerate(scan_coords):
                if progress_callback and i % 50 == 0:
                    progress_callback(f"V-Carve raster {i+1}/{total_lines}", int((i/total_lines)*100))
                    
                forward = (i % 2 == 0)
                mach = mach_coords_fwd if forward else mach_coords_rev
                
                if raster_dir == "Raster Y":
                    ys = mach
                    xs = np.full_like(ys, s)
                else:
                    xs = mach
                    ys = np.full_like(xs, s)
                
                # Perform full V-Bit geometry compensated Z array
                z_vcomp = CAMEngine.compute_compensated_z_array(
                    xs, ys, ttype, tool, arr, stock_x, stock_y, max_depth,
                    carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                    preserve_aspect, base_color, invert_check, curve_params=curve_params,
                    toolpath_geometry_mode=geom_mode
                )
                
                line_points = np.column_stack((xs, ys, z_vcomp))
                line_points = CAMEngine.apply_min_z_variation_filter(line_points, min_z_var)
                compressed = CAMEngine.compress_path_3d(line_points, rdp_tol)
                
                for idx, pt in enumerate(compressed):
                    cmd = "G01" if pt[2] < -0.1 else "G00"
                    if i == 0 and idx == 0:
                        toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                    elif idx == 0:
                        prev_pt = toolpath_moves[-1]
                        dist = np.sqrt((pt[0]-prev_pt[0])**2 + (pt[1]-prev_pt[1])**2)
                        
                        retract_required = True
                        if not retract_between_passes:
                            # Bypass retract if next start coordinate is close (adjacent pass)
                            if dist <= max(8.0, 3 * stepover):
                                retract_required = False
                                
                        if retract_required:
                            toolpath_moves.append((prev_pt[0], prev_pt[1], safe_z, "G00"))
                            toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                    toolpath_moves.append((pt[0], pt[1], pt[2], cmd))
                    
        return toolpath_moves
