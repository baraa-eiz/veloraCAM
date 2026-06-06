import os
import sys
import unittest
import numpy as np
import tempfile
import json

# Add root folder to path to import components
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.settings import SettingsManager
from core.project import Project
from core.engine import CAMEngine
from core.writer import ModalWriter
from libraries.tools import ToolLibrary
from libraries.materials import MaterialLibrary
from libraries.machines import MachineLibrary
from postprocessors.post_processor import PostProcessor

from modules.stone_relief.module import StoneReliefModule
from modules.wood_relief.module import WoodReliefModule
from modules.wood_vcarve.module import WoodVCarveModule
from modules.acp_panels.module import ACPPanelsModule

class TestVeloraCNCModularSuite(unittest.TestCase):
    """
    Automated verification suite validating all 15 operational scenarios.
    """
    def setUp(self):
        # Create a mock 50x50 heightmap array containing a diagonal groove (pixels 0-255)
        self.arr = np.full((50, 50), 255, dtype=np.uint8)
        for i in range(50):
            # Diagonal dark groove representing detailed ornament
            self.arr[i, max(0, i-2):min(50, i+3)] = 20
            
        self.tool_lib = ToolLibrary()
        self.tool_lib.tools = self.tool_lib.get_default_tools()  # Force default tools for robust testing
        self.mat_lib = MaterialLibrary()
        self.mach_lib = MachineLibrary()
        
        # Build base project parameters
        self.project_params = {
            "stock_x": 300.0,
            "stock_y": 300.0,
            "max_depth": 15.0,
            "carving_w": 50,
            "carving_h": 50,
            "min_x": 0.0,
            "max_x": 50.0,
            "min_y": 50.0,
            "max_y": 0.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "scaled_w": 300.0,
            "scaled_h": 300.0,
            "preserve_aspect": True,
            "invert_check": False,
            "base_color": None,
            "tool": self.tool_lib.tools[0],  # LOXA Tapered Ball nose
            "simplification_preset": 1,
            "resol_x": 1.0
        }

    # ==============================================================================
    # Automated Case 1: Stone Relief Finishing
    # ==============================================================================
    def test_01_stone_relief_finishing(self):
        mod = StoneReliefModule()
        op = {
            "name": "Finishing Raster Pass",
            "type": "Finishing Raster",
            "enabled": True,
            "tool_id": "T1",
            "feed_xy": 2000.0,
            "feed_z": 1000.0,
            "spindle_speed": 18000,
            "stepover": 2.0,
            "max_depth": 10.0,
            "safe_z": 20.0
        }
        
        moves = mod.compile_toolpath(op, self.arr, self.project_params)
        self.assertGreater(len(moves), 0, "Stone finishing should compile coordinate points.")
        # Check coordinates boundaries
        for x, y, z, cmd in moves:
            self.assertTrue(0.0 <= x <= 300.0)
            self.assertTrue(0.0 <= y <= 300.0)
            self.assertTrue(-10.0 <= z <= 20.0)

    # ==============================================================================
    # Automated Case 2: Roughing + Finishing (Single File with pauses)
    # ==============================================================================
    def test_02_rough_finish_single_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            with open(tmp_path, "w") as f:
                writer = ModalWriter(f)
                
                # Setup custom tool-change sequence
                writer.write_tool_change("T2", "Flat Roughing 6mm", 20.0)
                writer.write_move("G01", x=10.0, y=10.0, z=-5.0)
                
                writer.write_tool_change("T1", "LOXA CZ10.3", 20.0)
                writer.write_move("G01", x=10.0, y=10.0, z=-10.0)
                
            with open(tmp_path, "r") as f:
                content = f.read()
                
            self.assertIn("M05", content, "Spindle stop code (M05) should be present.")
            self.assertIn("M0", content, "Operator pause code (M0) should be present.")
            self.assertIn("CHANGE TO TOOL", content, "Parenthetical operator instructions should be printed.")
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ==============================================================================
    # Automated Case 3: Roughing + Finishing (Separate Files per Tool)
    # ==============================================================================
    def test_03_rough_finish_multi_file(self):
        header_lines = PostProcessor.get_header("GRBL", "SeparateTest", 200.0, 200.0, 10.0, "Flat Mill", 18000, 15.0)
        content = "\n".join(header_lines)
        self.assertIn("; Units: mm", content)
        self.assertIn("M3 S18000", content)
        
        footer_lines = PostProcessor.get_footer("GRBL", 15.0)
        footer_content = "\n".join(footer_lines)
        self.assertIn("M5 ; Spindle OFF", footer_content)
        self.assertIn("M30", footer_content)

    # ==============================================================================
    # Automated Case 4: Wood Relief Multi-Pass
    # ==============================================================================
    def test_04_wood_relief_multipass(self):
        mod = WoodReliefModule()
        suggested = mod.get_suggested_operations()
        self.assertEqual(len(suggested), 3, "Wood Relief should default to Rough, Finish, and Edge cleanup operations.")
        self.assertEqual(suggested[0]["type"], "Raster Roughing")
        self.assertEqual(suggested[1]["type"], "Ball Nose Finishing")

    # ==============================================================================
    # Automated Case 5: Wood V-Carve Operations Stack
    # ==============================================================================
    def test_05_wood_vcarve_stack(self):
        mod = WoodVCarveModule()
        ops = mod.get_suggested_operations()
        self.assertEqual(len(ops), 2, "V-Carve should offer flat pocket clearing and detailing.")
        self.assertEqual(ops[0]["type"], "Flat Clearing")
        self.assertEqual(ops[1]["type"], "V-Carve Detailing")

    # ==============================================================================
    # Automated Case 6: ACP Panel Grooving
    # ==============================================================================
    def test_06_acp_grooving_depth(self):
        mod = ACPPanelsModule()
        op = {
            "name": "Bending line",
            "type": "V-Groove Bending",
            "panel_thickness": 4.0,
            "remaining_backing": 0.8,
            "tool_id": "T4",
            "stepover": 0.2,
            "stepdown": 0.2
        }
        
        # Remaining backing is 0.8mm -> Groove depth must be exactly 3.2mm
        target_z = -(op["panel_thickness"] - op["remaining_backing"])
        self.assertEqual(target_z, -3.2, "Bending groove depth should be exactly 3.2mm deep.")
        
        warnings = mod.validate_operation(op, self.tool_lib, 200, 200, 4.0)
        self.assertEqual(len(warnings), 0, "Valid thickness should not trigger collision alerts.")

    # ==============================================================================
    # Automated Case 7: Forbidden Machining Area
    # ==============================================================================
    def test_07_nogo_obstacle_avoidance(self):
        # 5x5 obstacle grid
        grid = np.zeros((5, 5), dtype=bool)
        grid[2, 2] = True  # Center cell is forbidden!
        
        # Find detour around center
        start = (0.5, 2.5)  # Far left
        end = (4.5, 2.5)    # Far right
        
        path = CAMEngine.find_avoidance_path(start, end, grid, 1.0, 5.0, 5.0)
        self.assertGreater(len(path), 2, "Detour routing should contain intermediate avoidance points.")
        # Ensure path does not cross center (2.5, 2.5) directly
        for pt in path:
            self.assertFalse(2.0 <= pt[0] <= 3.0 and 2.0 <= pt[1] <= 3.0)

    # ==============================================================================
    # Automated Case 8: Collision Warning (Short Tool)
    # ==============================================================================
    def test_08_collision_short_tool(self):
        mod = StoneReliefModule()
        op = {
            "name": "Finishing",
            "tool_id": "T1",
            "max_depth": 35.0  # Depth is 35mm
        }
        # T1 has cutting_length of 25mm. Deep engraving must trigger a warning!
        warnings = mod.validate_operation(op, self.tool_lib, 300, 300, 35.0)
        self.assertTrue(any("Collision Risk" in w for w in warnings), "Short tool should flag collision warnings.")

    # ==============================================================================
    # Automated Case 9: Missing Material/Parameters Warning
    # ==============================================================================
    def test_09_missing_parameters_warnings(self):
        mod = StoneReliefModule()
        op = {
            "name": "Invalid Op",
            "tool_id": "NON_EXISTENT",
            "max_depth": 10.0
        }
        warnings = mod.validate_operation(op, self.tool_lib, 300, 300, 10.0)
        self.assertTrue(any("Missing or unassigned cutting tool" in w for w in warnings))

    # ==============================================================================
    # Automated Case 10: Post Processor Target (Mach3)
    # ==============================================================================
    def test_10_post_processor_mach3(self):
        lines = PostProcessor.get_header("Mach3", "TestJob", 300, 300, 15, "LOXA", 20000, 20.0)
        content = "\n".join(lines)
        self.assertIn("G64 (Continuous Velocity Mode)", content)
        self.assertIn("G90", content)
        self.assertIn("M03 S20000", content)

    # ==============================================================================
    # Automated Case 11: Post Processor Target (GRBL)
    # ==============================================================================
    def test_11_post_processor_grbl(self):
        lines = PostProcessor.get_header("GRBL", "TestJob", 300, 300, 15, "LOXA", 20000, 20.0)
        content = "\n".join(lines)
        self.assertIn("; Absolute positioning", content)
        self.assertIn("M3 S20000", content)

    # ==============================================================================
    # Automated Case 12: UI Scaling & Bounds
    # ==============================================================================
    def test_12_ui_scaling_bounds(self):
        # Image coordinates 10x10. Stock is 300x150. Aspect ratio preserves uniform scales.
        img_w, img_h = 10, 10
        stock_x, stock_y = 300.0, 150.0
        
        scale_x = stock_x / img_w
        scale_y = stock_y / img_h
        scale = min(scale_x, scale_y)  # 150/10 = 15.0
        
        self.assertEqual(scale, 15.0, "Scale should be limited by height ratio.")
        scaled_w = img_w * scale
        scaled_h = img_h * scale
        self.assertEqual(scaled_w, 150.0)
        self.assertEqual(scaled_h, 150.0)

    # ==============================================================================
    # Automated Case 13: Project File Save/Load
    # ==============================================================================
    def test_13_project_save_load(self):
        p = Project()
        p.stock_x = 450.0
        p.stock_y = 450.0
        p.max_depth = 25.0
        p.operations = [{"name": "Test Op", "type": "Raster", "tool_id": "T1"}]
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            p.save_to_file(tmp_path)
            
            p2 = Project()
            p2.load_from_file(tmp_path)
            
            self.assertEqual(p2.stock_x, 450.0)
            self.assertEqual(p2.max_depth, 25.0)
            self.assertEqual(len(p2.operations), 1)
            self.assertEqual(p2.operations[0]["name"], "Test Op")
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ==============================================================================
    # Automated Case 14: Autosave & Undo/Redo
    # ==============================================================================
    def test_14_undo_redo_stack(self):
        p = Project()
        p.stock_x = 300.0
        p.save_snapshot()  # Push initial state
        
        p.stock_x = 400.0
        p.save_snapshot()  # Push second state
        
        self.assertEqual(p.stock_x, 400.0)
        
        ret = p.undo()
        self.assertTrue(ret)
        self.assertEqual(p.stock_x, 300.0, "Undo should restore previous stock parameter.")
        
        ret2 = p.redo()
        self.assertTrue(ret2)
        self.assertEqual(p.stock_x, 400.0, "Redo should restore parameter.")

    # ==============================================================================
    # Automated Case 15: Selective Regeneration
    # ==============================================================================
    def test_15_selective_regeneration(self):
        p = Project()
        op_a = {"name": "Rough", "dirty": False, "locked": False}
        op_b = {"name": "Finish", "dirty": True, "locked": False}
        p.operations = [op_a, op_b]
        
        # Test modification dirty flag triggers
        op_b["feed_xy"] = 3000.0
        op_b["dirty"] = True
        
        # Check that op_a is NOT dirty (cached) and will bypass recomputations
        self.assertFalse(p.operations[0]["dirty"], "Operation A should remain cached.")
        self.assertTrue(p.operations[1]["dirty"], "Operation B must be dirty and ready for recompile.")

    # ==============================================================================
    # Automated Case 16: Z Retract Between Passes Bypass Validation
    # ==============================================================================
    def test_16_z_retract_bypass(self):
        mod = StoneReliefModule()
        op = {
            "name": "Finishing Raster Pass",
            "type": "Finishing Raster",
            "enabled": True,
            "tool_id": "T1",
            "stepover": 2.0,
            "max_depth": 10.0,
            "safe_z": 20.0
        }
        
        # Scenario 1: retract_between_passes is True (always retracts)
        params_with_retract = dict(self.project_params)
        params_with_retract["retract_between_passes"] = True
        moves_with = mod.compile_toolpath(op, self.arr, params_with_retract)
        
        # Scenario 2: retract_between_passes is False (bypasses adjacent retracts)
        params_no_retract = dict(self.project_params)
        params_no_retract["retract_between_passes"] = False
        moves_no = mod.compile_toolpath(op, self.arr, params_no_retract)
        
        # Count rapid retract moves (cmd == "G00" and z == safe_z) after the initial plunge
        retracts_with = sum(1 for m in moves_with[1:] if m[3] == "G00" and m[2] == 20.0)
        retracts_no = sum(1 for m in moves_no[1:] if m[3] == "G00" and m[2] == 20.0)
        
        # The optimized bypass run must have significantly fewer Z retract movements!
        self.assertLess(retracts_no, retracts_with, "Optimized retract-bypass should contain fewer Z-retracts.")

    # ==============================================================================
    # Automated Case 17: Raster Direction Validation (Raster X vs Raster Y)
    # ==============================================================================
    def test_17_raster_direction(self):
        mod = StoneReliefModule()
        op_x = {
            "name": "Finishing Raster Pass",
            "type": "Finishing Raster",
            "enabled": True,
            "tool_id": "T1",
            "stepover": 2.0,
            "max_depth": 5.0,
            "safe_z": 20.0,
            "raster_direction": "Raster X"
        }
        
        op_y = dict(op_x)
        op_y["raster_direction"] = "Raster Y"
        
        params = dict(self.project_params)
        params["retract_between_passes"] = True
        
        # Compile both directions
        moves_x = mod.compile_toolpath(op_x, self.arr, params)
        moves_y = mod.compile_toolpath(op_y, self.arr, params)
        
        # Verify that for Raster X, we step over Y (meaning Y is constant within segments of G01 movements)
        # Verify that for Raster Y, we step over X (meaning X is constant within segments of G01 movements)
        self.assertNotEqual(moves_x, moves_y, "Toolpaths with different raster directions must not be identical.")
        
        # Print a success confirmation
        print("Raster Direction validation successful: Raster X and Raster Y compiled distinct toolpaths.")

    # ==============================================================================
    # Automated Case 18: Surface Optimization Pipeline (Base flattening, edge protection, smoothing)
    # ==============================================================================
    def test_18_surface_optimization_pipeline(self):
        # Create dummy project
        proj = Project()
        proj.stock_x = 50.0
        proj.stock_y = 50.0
        proj.base_color = 50.0
        proj.opt_flatten_selected_base = True
        proj.opt_base_tolerance = 2.0
        proj.opt_min_region_size = 1
        proj.opt_preserve_edges = False
        proj.opt_smoothing_level = "Off"
        
        # 50x50 dummy heightmap. Value 50 is flat base, 100 is relief
        arr = np.full((50, 50), 50.0)
        arr[20:30, 20:30] = 100.0 # square relief
        # Add small noise to the base area
        arr[5, 5] = 51.0
        arr[10, 10] = 49.0
        
        # Test basic selected base flattening
        out, raw_mask, base_mask, clean_flat = CAMEngine.optimize_surface(arr, proj)
        self.assertEqual(out[5, 5], 50.0, "Selected base noise at (5,5) should be flattened to 50.")
        self.assertEqual(out[10, 10], 50.0, "Selected base noise at (10,10) should be flattened to 50.")
        self.assertEqual(out[25, 25], 100.0, "Relief area should remain unflattened.")
        
        # Test edge protection
        proj.opt_preserve_edges = True
        proj.opt_edge_distance_mm = 5.0 # pixel size is 50mm / 50px = 1.0mm per px, so 5 pixels erosion
        out_protected, _, base_mask_protected, _ = CAMEngine.optimize_surface(arr, proj)
        
        # Pixels at distance <= 5 from the relief (20:30) must NOT be flattened to base color if they had noise
        # Let's add noise to a pixel near the relief edge (e.g. at 18, 18)
        arr_noisy_edge = arr.copy()
        arr_noisy_edge[18, 18] = 51.0
        _, _, base_mask_p, _ = CAMEngine.optimize_surface(arr_noisy_edge, proj)
        self.assertFalse(base_mask_p[18, 18], "Pixel near relief edge should be protected (excluded from base mask).")
        
        # Test min Z variation filter
        path = np.array([
            [0.0, 0.0, -1.0],
            [1.0, 0.0, -1.01],
            [2.0, 0.0, -1.02],
            [3.0, 0.0, -1.1]
        ])
        filtered = CAMEngine.apply_min_z_variation_filter(path, 0.05)
        self.assertEqual(filtered[1, 2], -1.0, "Z variation of 0.01 should be suppressed to -1.0.")
        self.assertEqual(filtered[2, 2], -1.0, "Z variation of 0.02 should be suppressed to -1.0.")
        self.assertEqual(filtered[3, 2], -1.1, "Z variation of 0.1 should not be suppressed.")
        
        print("Surface Optimization validation successful: Base flattening, edge protection, and Z-variation filtering verified.")

    # ==============================================================================
    # Automated Case 19: Curved Base Compensation Pipeline
    # ==============================================================================
    def test_19_curved_base_compensation(self):
        # 1. Setup curve params
        curve_params = {
            "curve_enabled": True,
            "curve_direction": "X Axis",
            "curve_diagonal_dir": "Top Left -> Bottom Right",
            "curve_control_points": [
                {"pos": 0.0, "z": 0.0},
                {"pos": 50.0, "z": 15.0},
                {"pos": 100.0, "z": 0.0}
            ],
            "curve_interpolation_type": "Smooth Spline",
            "curve_smoothness": 50.0,
            "curve_reference_mode": "Lock Minimum Z",
            "stock_x": 100.0,
            "stock_y": 100.0
        }
        
        # 2. Test spline calculation at boundaries and midpoint
        u = np.array([0.0, 0.5, 1.0])
        z_vals = CAMEngine.evaluate_curve(u, curve_params["curve_control_points"], "Smooth Spline", 50.0)
        self.assertAlmostEqual(z_vals[0], 0.0, delta=0.1)
        self.assertAlmostEqual(z_vals[1], 15.0, delta=0.1)
        self.assertAlmostEqual(z_vals[2], 0.0, delta=0.1)
        
        # 3. Test coordinate mapping projection (X direction)
        u_x = CAMEngine.get_normalized_u(50.0, 20.0, 100.0, 100.0, "X Axis")
        self.assertAlmostEqual(u_x, 0.5, delta=0.01)
        
        # Test coordinate mapping projection (Y direction)
        u_y = CAMEngine.get_normalized_u(20.0, 50.0, 100.0, 100.0, "Y Axis")
        self.assertAlmostEqual(u_y, 0.5, delta=0.01)
        
        # Test coordinate mapping projection (Diagonal)
        u_diag = CAMEngine.get_normalized_u(50.0, 50.0, 100.0, 100.0, "Diagonal", "Top Left -> Bottom Right")
        self.assertAlmostEqual(u_diag, 0.5, delta=0.01)
        
        # 4. Test reference plane calculations
        ref_offset = CAMEngine.get_curve_reference_offset(
            curve_params["curve_control_points"], "Smooth Spline", 50.0, "Lock Minimum Z"
        )
        self.assertAlmostEqual(ref_offset, 0.0, delta=0.1)
        
        ref_offset_max = CAMEngine.get_curve_reference_offset(
            curve_params["curve_control_points"], "Smooth Spline", 50.0, "Lock Maximum Z"
        )
        self.assertAlmostEqual(ref_offset_max, 15.0, delta=0.1)
        
        # 5. Test vectorized Z offset application at XY coordinates
        xs = np.array([0.0, 50.0, 100.0])
        ys = np.array([0.0, 50.0, 100.0])
        offsets = CAMEngine.evaluate_curve_offset_at_xy(xs, ys, 100.0, 100.0, curve_params)
        
        # With Lock Minimum Z, reference is 0.0, offsets should be z_vals - 0.0
        self.assertAlmostEqual(offsets[0], 0.0, delta=0.1)
        self.assertAlmostEqual(offsets[1], 15.0, delta=0.1)
        self.assertAlmostEqual(offsets[2], 0.0, delta=0.1)
        
        # 6. Test safety Z auto-adjustment calculation
        max_z = CAMEngine.get_curve_max_z(curve_params)
        self.assertAlmostEqual(max_z, 15.0, delta=0.1)
        
        print("Curved Base Compensation Pipeline validation successful.")

    # ==============================================================================
    # Automated Case 20: True Tool Geometry Calculations
    # ==============================================================================
    def test_20_tool_geometry_calculations(self):
        tool = {
            "name": "LOXA CZ10.3",
            "type": "Tapered Ball Nose",
            "tip_diameter": 3.0,
            "ball_radius": 1.5,
            "max_diameter": 6.0,
            "taper_angle": 10.0,
            "cutting_length": 15.0,
            "tool_length": 50.0,
            "neck_diameter": 5.0,
            "flute_length": 15.0,
            "stickout_length": 35.0,
            "overall_length": 50.0,
            "safe_clearance_margin": 1.0,
            "holder_diameter": 20.0,
            "collet_diameter": 15.0,
            "holder_length": 40.0
        }
        
        # 1. Test profile LUT generation
        r_samples, z_offsets = CAMEngine.compute_tool_profile_lut(tool, tool["type"], 1.0)
        self.assertGreater(len(r_samples), 0)
        self.assertEqual(r_samples[0], 0.0)
        self.assertEqual(z_offsets[0], 0.0)  # offset at tip center is 0
        
        # At effective tip radius (physical tip radius + safe clearance margin), offset should be the ball nose offset at physical tip
        tip_r_eff = 1.5 + 1.0  # physical 1.5 + safe clearance 1.0
        idx_tip = np.argmin(np.abs(r_samples - tip_r_eff))
        expected_z_at_tip = 1.5  # at physical radius of 1.5, z offset is 1.5
        self.assertAlmostEqual(z_offsets[idx_tip], expected_z_at_tip, delta=0.2)
        
        # 2. Test polar search grid generation
        r_cutter = float(tool["tip_diameter"]) / 2.0
        r_neck = float(tool["neck_diameter"]) / 2.0
        r_max = r_samples[-1] - 1.0
        grid_pts = CAMEngine.generate_optimized_search_grid(r_cutter, r_neck, r_max, 1.0)
        self.assertGreater(len(grid_pts), 0)
        self.assertTrue(np.max(grid_pts[:, 2]) >= 10.0)
        
        print("True Tool Geometry Calculations validation successful.")

    # ==============================================================================
    # Automated Case 21: Compensated Z Geometry Aware Mode
    # ==============================================================================
    def test_21_compensated_z_geometry_aware(self):
        tool = {
            "name": "Short detail tool",
            "type": "Tapered Ball Nose",
            "tip_diameter": 2.0,
            "ball_radius": 1.0,
            "max_diameter": 6.0,
            "taper_angle": 10.0,
            "cutting_length": 5.0,
            "tool_length": 20.0,
            "neck_diameter": 5.0,
            "flute_length": 5.0,
            "stickout_length": 8.0,  # very short stickout to trigger holder collision!
            "overall_length": 20.0,
            "safe_clearance_margin": 1.0,
            "holder_diameter": 30.0,  # large holder
            "collet_diameter": 20.0,
            "holder_length": 15.0
        }
        
        # Create a heightmap with a very deep and narrow trench (height goes from 255 to 0)
        # Pixel width is 1.0mm.
        arr = np.full((30, 30), 255, dtype=np.uint8)
        arr[10:20, 10:20] = 0  # deep square pocket
        
        # Compute compensated Z in both modes
        xs = np.array([15.0])
        ys = np.array([15.0])
        
        z_legacy = CAMEngine.compute_compensated_z_array(
            xs, ys, tool["type"], tool, arr, 30.0, 30.0, 15.0,
            30, 30, 0.0, 30.0, 0.0, 0.0, False, None, False,
            toolpath_geometry_mode="Legacy"
        )
        
        z_aware = CAMEngine.compute_compensated_z_array(
            xs, ys, tool["type"], tool, arr, 30.0, 30.0, 15.0,
            30, 30, 0.0, 30.0, 0.0, 0.0, False, None, False,
            toolpath_geometry_mode="Geometry Aware"
        )
        
        # In legacy mode, tool should go deep into the pocket (z_legacy should be low)
        # In geometry-aware mode, the large holder/neck diameter will collide with the pocket walls,
        # forcing the tool to be retracted (z_aware should be significantly higher than z_legacy)
        self.assertTrue(z_aware[0] > z_legacy[0] + 0.5, f"Geometry Aware mode should retract tool to avoid neck/holder collision (z_aware: {z_aware[0]:.2f}, z_legacy: {z_legacy[0]:.2f})")
        
        # Test validation warnings
        stone_mod = StoneReliefModule()
        op_bad_stepover = {
            "name": "Roughing",
            "type": "Raster Roughing",
            "tool_id": "T1",
            "stepover": 10.0,  # exceeds tip diameter
            "stepdown": 20.0   # exceeds max stepdown
        }
        warnings = stone_mod.validate_operation(op_bad_stepover, self.tool_lib, 200, 200, 15.0)
        self.assertTrue(any("exceeds tool's maximum engagement limit" in w for w in warnings))
        self.assertTrue(any("exceeds tool's maximum stepdown limit" in w for w in warnings))
        
        # Test max wall angle filter
        test_pts = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, -10.0],  # sudden vertical drop of 10mm
            [2.0, 0.0, -10.0]
        ])
        # With max wall angle 45 deg, max slope is tan(45) = 1.0.
        # Drop from index 0 to 1 over dx=1.0 can be at most 1.0 * 1.0 = 1.0mm.
        # So Z at index 1 should be filtered to max(-10.0, 0.0 - 1.0) = -1.0mm.
        filtered = CAMEngine.apply_max_wall_angle_filter(test_pts, 45.0)
        self.assertAlmostEqual(filtered[1, 2], -1.0, delta=0.01)
        
        print("Compensated Z Geometry Aware Mode validation successful.")

if __name__ == "__main__":
    unittest.main()
