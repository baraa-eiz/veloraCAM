import unittest
import numpy as np

def calculate_surface_z(val, base_color, max_depth, invert_check):
    if base_color is not None:
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
        z_val = -max_depth * (1.0 - val / 255.0)
        
    return z_val

class TestBaseColorScaling(unittest.TestCase):
    def test_standard_scaling_no_base(self):
        # Fallback standard scaling: pure black (0) -> -25.0, pure white (255) -> 0.0
        self.assertAlmostEqual(calculate_surface_z(0, None, 25.0, False), -25.0)
        self.assertAlmostEqual(calculate_surface_z(255, None, 25.0, False), 0.0)
        self.assertAlmostEqual(calculate_surface_z(127.5, None, 25.0, False), -12.5)

    def test_standard_scaling_with_base_color(self):
        # Base color 40 represents the absolute floor (-25.0 mm)
        # Peak 255 represents the absolute top (0.0 mm)
        base_color = 40
        max_depth = 25.0
        
        # Test floor clamping
        self.assertAlmostEqual(calculate_surface_z(40, base_color, max_depth, False), -25.0)
        self.assertAlmostEqual(calculate_surface_z(20, base_color, max_depth, False), -25.0) # clamped below floor
        
        # Test ceiling
        self.assertAlmostEqual(calculate_surface_z(255, base_color, max_depth, False), 0.0)
        
        # Test mid-point scaling
        mid_val = 40 + (255 - 40) / 2.0  # 147.5
        self.assertAlmostEqual(calculate_surface_z(mid_val, base_color, max_depth, False), -12.5)

    def test_inverted_scaling_with_base_color(self):
        # Inverted mode: Base Color (e.g. 215) is the highest (0.0)
        # Deepest features (0) are the deepest (-25.0)
        base_color = 215
        max_depth = 25.0
        
        # Test peak clamping
        self.assertAlmostEqual(calculate_surface_z(215, base_color, max_depth, True), 0.0)
        self.assertAlmostEqual(calculate_surface_z(230, base_color, max_depth, True), 0.0) # clamped above ceiling
        
        # Test absolute bottom
        self.assertAlmostEqual(calculate_surface_z(0, base_color, max_depth, True), -25.0)
        
        # Test mid-point scaling
        mid_val = 215 / 2.0  # 107.5
        self.assertAlmostEqual(calculate_surface_z(mid_val, base_color, max_depth, True), -12.5)

if __name__ == "__main__":
    unittest.main()
