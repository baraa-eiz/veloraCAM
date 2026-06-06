import numpy as np
import time
from modules.base_module import BaseModule
from core.engine import CAMEngine

class StoneReliefModule(BaseModule):
    """
    CAM Module for specialized 3D Stone Relief Carving.
    Compiles roughing layers, fine rasters, cross finishes, and detail sweeps.
    """
    def __init__(self):
        super().__init__("Stone Relief")

    def get_suggested_operations(self, material_preset=None, style_preset=None):
        """
        Preloads standard editable stone carving operations.
        Defaults to T1 (Tapered Ball Nose) for finishing, T2 (Flat Mill) for roughing.
        """
        # Suggest a roughing pass + finishing pass as standard balanced configuration
        op_rough = {
            "name": "Coarse Roughing Pass",
            "type": "Raster Roughing",
            "enabled": True,
            "tool_id": "T2",  # Default flat endmill
            "feed_xy": 2500.0,
            "feed_z": 800.0,
            "feed_plunge": 500.0,
            "spindle_speed": 18000,
            "stepover": 3.0,
            "stepdown": 3.0,
            "max_depth": 15.0,
            "stock_allowance": 1.0,
            "safe_z": 20.0,
            "locked": False
        }
        
        op_finish = {
            "name": "High Precision Finishing Pass",
            "type": "Finishing Raster",
            "enabled": True,
            "tool_id": "T1",  # Default tapered ball nose
            "feed_xy": 2500.0,
            "feed_z": 1200.0,
            "feed_plunge": 600.0,
            "spindle_speed": 20000,
            "stepover": 0.8,
            "stepdown": 15.0,  # Single pass following surface
            "max_depth": 15.0,
            "stock_allowance": 0.0,
            "safe_z": 20.0,
            "locked": False
        }
        
        # Apply preloaded style settings if provided
        if style_preset == "Conservative":
            op_rough["feed_xy"] = 1500.0; op_rough["stepdown"] = 1.5
            op_finish["feed_xy"] = 1800.0; op_finish["stepover"] = 0.5
        elif style_preset == "Fast":
            op_rough["feed_xy"] = 3500.0; op_rough["stepdown"] = 5.0
            op_finish["feed_xy"] = 3200.0; op_finish["stepover"] = 1.2
        elif style_preset == "High Detail":
            # Add a cross finishing pass
            op_cross = dict(op_finish)
            op_cross["name"] = "Detail Cross Finishing Pass"
            op_cross["type"] = "Cross Finishing"
            op_cross["stepover"] = 0.5
            return [op_rough, op_finish, op_cross]
            
        return [op_rough, op_finish]

    def validate_operation(self, op, tool_library, stock_x, stock_y, max_depth):
        """
        Performs stone carving validation checking physical parameters, rigidity, and engagement limits.
        """
        warnings = super().validate_operation(op, tool_library, stock_x, stock_y, max_depth)
        tool_id = op.get("tool_id", "")
        tool = tool_library.get_tool(tool_id) if tool_library else None
        
        if tool:
            # 1. Rigidity Assessment: L^3 / D^4
            L = tool.get("stickout_length", tool.get("tool_length", 50.0) - 10.0)
            D = tool.get("neck_diameter", tool.get("shank_diameter", 6.0))
            if D > 0 and L > 0:
                deflection_index = (L ** 3) / (D ** 4)
                if deflection_index > 150.0:
                    warnings.append(f"Rigidity Alert: Tool is highly flexible (Rigidity Index: {deflection_index:.1f}). High deflection/breakage risk on stone.")
                elif deflection_index > 50.0:
                    warnings.append(f"Rigidity Caution: Moderate tool deflection risk (Rigidity Index: {deflection_index:.1f}).")
            
            # 2. Engagement Limits
            max_eng = tool.get("max_engagement", 1.5)
            max_sd = tool.get("max_stepdown", 1.5)
            stepover = op.get("stepover", 1.0)
            stepdown = op.get("stepdown", 1.0)
            if stepover > max_eng:
                warnings.append(f"Engagement Warning: Requested stepover ({stepover}mm) exceeds tool's maximum engagement limit ({max_eng}mm).")
            if stepdown > max_sd and op.get("type") == "Raster Roughing":
                warnings.append(f"Engagement Warning: Requested stepdown ({stepdown}mm) exceeds tool's maximum stepdown limit ({max_sd}mm).")
                
        return warnings

    def compile_toolpath(self, op, arr, project_params, progress_callback=None):
        """
        Compiles high-performance G-code coordinates for Stone Relief.
        """
        op_type = op.get("type", "Finishing Raster")
        
        # Core stock geometries
        stock_x = project_params["stock_x"]
        stock_y = project_params["stock_y"]
        max_depth = op.get("max_depth", project_params["max_depth"])
        safe_z = op.get("safe_z", 20.0)
        curve_params = project_params.get("curve_params", None)
        if curve_params and curve_params.get("curve_enabled", False):
            max_curve_z = CAMEngine.get_curve_max_z(curve_params)
            safe_z = safe_z + max(0.0, max_curve_z)
        
        # Grid parameters from coordinates mapping
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
        
        # Tool geometries
        tool = project_params["tool"]
        ttype = tool["type"]
        
        # Compression and variation tolerances
        rdp_tol = project_params.get("opt_compression_tol", 0.05)
        min_z_var = project_params.get("opt_min_z_variation", 0.05)
        
        geom_mode = project_params.get("toolpath_geometry_mode", "Legacy")
        toolpath_moves = []  # List of coordinates (X, Y, Z, G0/G1)
        
        if op_type == "Raster Roughing":
            # 1. Z-Sliced Layer Roughing Strategy
            stepdown = op.get("stepdown", 3.0)
            stepover = op.get("stepover", 3.0)
            allowance = op.get("stock_allowance", 1.0)
            
            # Generate target depths
            z_slices = list(np.arange(-stepdown, -max_depth - 0.01, -stepdown))
            if not z_slices or z_slices[-1] > -max_depth:
                z_slices.append(-max_depth)
                
            raster_dir = op.get("raster_direction", "Raster X")
            
            if raster_dir == "Raster Y":
                # Step over X, scan Y
                scan_coords = np.arange(0.0, stock_x + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_y + 1.0, 1.0)
            else:
                # Step over Y, scan X
                scan_coords = np.arange(0.0, stock_y + stepover, stepover)
                mach_coords_fwd = np.arange(0.0, stock_x + 1.0, 1.0)
                
            mach_coords_rev = mach_coords_fwd[::-1]
            
            total_layers = len(z_slices)
            for layer_idx, target_z in enumerate(z_slices):
                if progress_callback:
                    progress_callback(f"Roughing Layer {layer_idx+1}/{total_layers}", int((layer_idx/total_layers)*100))
                    
                for i, s in enumerate(scan_coords):
                    forward = (i % 2 == 0)
                    mach = mach_coords_fwd if forward else mach_coords_rev
                    
                    if raster_dir == "Raster Y":
                        ys = mach
                        xs = np.full_like(ys, s)
                    else:
                        xs = mach
                        ys = np.full_like(xs, s)
                    
                    # Vectorized query of surface Z height
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
                            # Initial rapid and plunge transition
                            toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                            cmd = "G01"
                        elif idx == 0:
                            if retract_between_passes:
                                # Safe step transition between layers
                                toolpath_moves.append((pt[0], pt[1], safe_z, "G00"))
                            cmd = "G01"
                        toolpath_moves.append((pt[0], pt[1], pt[2], cmd))
                        
        elif op_type in ["Finishing Raster", "Cross Finishing"]:
            # 2. Vectorized Slope-Aware Scallop finishing strategy
            stepover = op.get("stepover", 0.8)
            resol_x = project_params.get("resol_x", 0.5)
            
            # Switch axes scanning if Cross Finishing is requested
            is_cross = (op_type == "Cross Finishing" or op.get("raster_direction", "Raster X") == "Raster Y")
            
            scan_limit = stock_x if is_cross else stock_y
            mach_limit = stock_y if is_cross else stock_x
            
            scan_coords = np.arange(0.0, scan_limit + stepover, stepover)
            mach_coords_fwd = np.arange(0.0, mach_limit + resol_x, resol_x)
            mach_coords_rev = mach_coords_fwd[::-1]
            
            total_scans = len(scan_coords)
            for s_idx, s in enumerate(scan_coords):
                if progress_callback and s_idx % 20 == 0:
                    progress_callback(f"Finishing scan {s_idx+1}/{total_scans}", int((s_idx/total_scans)*100))
                    
                forward = (s_idx % 2 == 0)
                mach = mach_coords_fwd if forward else mach_coords_rev
                
                if is_cross:
                    xs = np.full_like(mach, s)
                    ys = mach
                else:
                    xs = mach
                    ys = np.full_like(mach, s)
                    
                # Vectorized tool nose radius compensated Z heights
                z_compensated = CAMEngine.compute_compensated_z_array(
                    xs, ys, ttype, tool, arr, stock_x, stock_y, max_depth,
                    carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                    preserve_aspect, base_color, invert_check, curve_params=curve_params,
                    toolpath_geometry_mode=geom_mode
                )
                
                line_points = np.column_stack((xs, ys, z_compensated))
                if geom_mode == "Geometry Aware":
                    max_wall_angle = tool.get("max_wall_angle", 45.0)
                    line_points = CAMEngine.apply_max_wall_angle_filter(line_points, max_wall_angle)
                line_points = CAMEngine.apply_min_z_variation_filter(line_points, min_z_var)
                compressed = CAMEngine.compress_path_3d(line_points, rdp_tol)
                
                for idx, pt in enumerate(compressed):
                    cmd = "G01"
                    if s_idx == 0 and idx == 0:
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
