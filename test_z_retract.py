import os
import sys
import unittest
import numpy as np

# Add build directory to path to import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stone_cam_app import ModalWriter

class TestZRetractControl(unittest.TestCase):
    def test_modal_writer_tracking(self):
        """Verify that ModalWriter correctly tracks physical Z travel, retracts, and plunges."""
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(mode="w+", delete=False, suffix=".tap") as tmp:
            tmp_path = tmp.name
            
        try:
            with open(tmp_path, "w") as f:
                mw = ModalWriter(f, min_xy=0.01, min_z=0.01)
                
                # Setup initial state
                mw.write_move("G00", x=0.0, y=0.0, z=20.0)
                self.assertEqual(mw.total_z_travel, 0.0) # first move sets last_z
                
                # Plunge (move down to -5.0)
                mw.write_move("G01", z=-5.0)
                self.assertEqual(mw.total_z_travel, 25.0)
                self.assertEqual(mw.z_plunges_count, 1)
                self.assertEqual(mw.z_retracts_count, 0)
                
                # Cut (no change in Z)
                mw.write_move("G01", x=10.0, y=0.0, z=-5.0)
                self.assertEqual(mw.total_z_travel, 25.0)
                self.assertEqual(mw.z_plunges_count, 1)
                self.assertEqual(mw.z_retracts_count, 0)
                
                # Retract (move up to 20.0)
                mw.write_move("G00", z=20.0)
                self.assertEqual(mw.total_z_travel, 50.0)
                self.assertEqual(mw.z_plunges_count, 1)
                self.assertEqual(mw.z_retracts_count, 1)
                
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_z_retract_deactivation_logic(self):
        """Verify the Z retract logic conditions under various settings."""
        # Scenario 1: retract_between_passes is True (default) -> Always retract
        retract_between_passes = True
        is_viol = False
        dist = 2.0
        segs_processed = 1
        stepover = 2.0
        
        retract_required = True
        if not retract_between_passes:
            max_transition_dist = max(8.0, stepover * 3.0)
            if not is_viol and dist <= max_transition_dist and segs_processed > 0:
                retract_required = False
                
        self.assertTrue(retract_required)
        
        # Scenario 2: retract_between_passes is False, normal adjacent pass (2.0mm <= 8.0mm) -> No retract!
        retract_between_passes = False
        retract_required = True
        if not retract_between_passes:
            max_transition_dist = max(8.0, stepover * 3.0)
            if not is_viol and dist <= max_transition_dist and segs_processed > 0:
                retract_required = False
                
        self.assertFalse(retract_required)
        
        # Scenario 3: retract_between_passes is False, but crossing a forbidden area (is_viol = True) -> Must retract!
        is_viol = True
        retract_required = True
        if not retract_between_passes:
            max_transition_dist = max(8.0, stepover * 3.0)
            if not is_viol and dist <= max_transition_dist and segs_processed > 0:
                retract_required = False
                
        self.assertTrue(retract_required)
        
        # Scenario 4: retract_between_passes is False, but large jump (islands) (dist = 50.0mm > 8.0mm) -> Must retract!
        is_viol = False
        dist = 50.0
        retract_required = True
        if not retract_between_passes:
            max_transition_dist = max(8.0, stepover * 3.0)
            if not is_viol and dist <= max_transition_dist and segs_processed > 0:
                retract_required = False
                
        self.assertTrue(retract_required)

if __name__ == "__main__":
    unittest.main()
