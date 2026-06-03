import numpy as np
from modules.base_module import BaseModule
from core.engine import CAMEngine

class WoodReliefModule(BaseModule):
    """
    CAM Module for 3D Wood Relief Carving.
    Features aggressive roughing sweeps, detailed rasters, and boundary edge cleanups.
    """
    def __init__(self):
        super().__init__("Wood Relief")

    def get_suggested_operations(self, material_preset=None, style_preset=None):
        """
        Preloads optimized operations for artistic wood carvings.
        """
        op_rough = {
            "name": "Coarse Wood Roughing",
            "type": "Raster Roughing",
            "enabled": True,
            "tool_id": "T2",  # 6mm Flat mill
            "feed_xy": 4000.0,
            "feed_z": 1200.0,
            "feed_plunge": 800.0,
            "spindle_speed": 20000,
            "stepover": 3.0,
            "stepdown": 6.0,  # Wood allows full-diameter depth per pass
            "max_depth": 15.0,
            "stock_allowance": 0.5,
            "safe_z": 15.0,
            "locked": False
        }
        
        op_finish = {
            "name": "Ball Nose Finish",
            "type": "Ball Nose Finishing",
            "enabled": True,
            "tool_id": "T1",  # 3mm Tapered Ball nose
            "feed_xy": 3500.0,
            "feed_z": 1500.0,
            "feed_plunge": 1000.0,
            "spindle_speed": 22000,
            "stepover": 0.6,  # Fine stepover for wood finish
            "stepdown": 15.0,
            "max_depth": 15.0,
            "stock_allowance": 0.0,
            "safe_z": 15.0,
            "locked": False
        }
        
        op_edge = {
            "name": "Outline Edge Cleanup",
            "type": "Edge Cleanup",
            "enabled": False,
            "tool_id": "T2",  # Clean wood contours using flat endmill
            "feed_xy": 3000.0,
            "feed_z": 1000.0,
            "feed_plunge": 600.0,
            "spindle_speed": 18000,
            "stepover": 1.0,
            "stepdown": 5.0,
            "max_depth": 15.0,
            "stock_allowance": 0.0,
            "safe_z": 15.0,
            "locked": False
        }
        
        if style_preset == "Conservative":
            op_rough["feed_xy"] = 3000.0; op_rough["stepdown"] = 3.0
            op_finish["feed_xy"] = 2800.0; op_finish["stepover"] = 0.4
        elif style_preset == "Fast":
            op_rough["feed_xy"] = 5000.0; op_rough["stepdown"] = 8.0
            op_finish["feed_xy"] = 4500.0; op_finish["stepover"] = 1.0
        elif style_preset == "High Detail":
            op_finish["stepover"] = 0.3
            op_edge["enabled"] = True
            
        return [op_rough, op_finish, op_edge]

    def compile_toolpath(self, op, arr, project_params, progress_callback=None):
        """
        Compiles fast, deep wood relief carvings.
        """
        op_type = op.get("type", "Ball Nose Finishing")
        
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
        
        toolpath_moves = []
        
        if op_type == "Raster Roughing":
            # 1. Standard Wood Z-Slicing
            stepdown = op.get("stepdown", 4.0)
            stepover = op.get("stepover", 3.0)
            allowance = op.get("stock_allowance", 0.5)
            
            z_slices = list(np.arange(-stepdown, -max_depth - 0.01, -stepdown))
            if not z_slices or z_slices[-1] > -max_depth:
                z_slices.append(-max_depth)
                
            raster_dir = op.get("raster_direction", "Raster X")
            
            if raster_dir == "Raster Y":
                scan_coords = np.arange(0.0, stock_x + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_y + 2.0, 2.0)
            else:
                scan_coords = np.arange(0.0, stock_y + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_x + 2.0, 2.0)
                
            mach_coords_rev = mach_coords_fwd[::-1]
            
            total_layers = len(z_slices)
            for layer_idx, target_z in enumerate(z_slices):
                if progress_callback:
                    progress_callback(f"Wood Roughing Layer {layer_idx+1}/{total_layers}", int((layer_idx/total_layers)*100))
                    
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
                    
                    z_targets = z_surfs + allowance
                    z_roughs = np.maximum(z_targets, target_z)
                    z_roughs = np.minimum(0.0, z_roughs)
                    
                    line_points = np.column_stack((xs, ys, z_roughs))
                    line_points = CAMEngine.apply_min_z_variation_filter(line_points, min_z_var)
                    compressed = CAMEngine.compress_path_3d(line_points, rdp_tol)
                    
                    for idx, pt in enumerate(compressed):
                        cmd = "G01"
                        if layer_idx == 0 and i == 0 and idx == 0:
                            toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                        elif idx == 0:
                            if retract_between_passes:
                                toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                        toolpath_moves.append((pt[0], pt[1], pt[2], cmd))
                        
        elif op_type == "Ball Nose Finishing":
            # 2. Detailed Ball Nose Finishing Raster
            stepover = op.get("stepover", 0.6)
            resol_x = project_params.get("resol_x", 0.5)
            
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
                    progress_callback(f"Wood Finishing Line {i+1}/{total_lines}", int((i/total_lines)*100))
                    
                forward = (i % 2 == 0)
                mach = mach_coords_fwd if forward else mach_coords_rev
                
                if raster_dir == "Raster Y":
                    ys = mach
                    xs = np.full_like(ys, s)
                else:
                    xs = mach
                    ys = np.full_like(xs, s)
                
                z_comp = CAMEngine.compute_compensated_z_array(
                    xs, ys, ttype, tool, arr, stock_x, stock_y, max_depth,
                    carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                    preserve_aspect, base_color, invert_check, curve_params=curve_params
                )
                
                line_points = np.column_stack((xs, ys, z_comp))
                line_points = CAMEngine.apply_min_z_variation_filter(line_points, min_z_var)
                compressed = CAMEngine.compress_path_3d(line_points, rdp_tol)
                
                for idx, pt in enumerate(compressed):
                    cmd = "G01"
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
                    
        elif op_type == "Edge Cleanup":
            # 3. Outer Border Edge Outline Cut
            if progress_callback:
                progress_callback("Compiling Edge Cleanup Outline...", 50)
                
            border_points = []
            
            # Simple border vector following the outer carving bounding box
            border_x = [offset_x, offset_x + scaled_w, offset_x + scaled_w, offset_x, offset_x]
            border_y = [offset_y, offset_y, offset_y + scaled_h, offset_y + scaled_h, offset_y]
            
            # Multi-depth stepdown cutting
            stepdown = op.get("stepdown", 5.0)
            z_levels = list(np.arange(-stepdown, -max_depth - 0.01, -stepdown))
            if not z_levels or z_levels[-1] > -max_depth:
                z_levels.append(-max_depth)
                
            for layer_idx, target_z in enumerate(z_levels):
                for pt_idx, (bx, by) in enumerate(zip(border_x, border_y)):
                    if layer_idx == 0 and pt_idx == 0:
                        toolpath_moves.append((bx, by, safe_z, "G00"))
                    toolpath_moves.append((bx, by, target_z, "G01"))
                    
            if progress_callback:
                progress_callback("Edge Cleanup Complete", 100)
                
        return toolpath_moves
