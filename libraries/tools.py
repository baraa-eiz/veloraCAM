import os
import json

class ToolLibrary:
    """
    Manages the physical tooling database for Velora CNC.
    Handles loading, saving, editing, and default tool creation.
    """
    def __init__(self, library_path=None):
        if library_path is None:
            self.library_path = r"c:\Users\pc\Desktop\cnc\tools_library.json"
        else:
            self.library_path = library_path
            
        self.tools = []
        self.load()

    def get_default_tools(self):
        """Preloaded industrial tool database for various materials and modules."""
        return [
            {
                "id": "T1",
                "name": "LOXA CZ10.3-60(120)",
                "type": "Tapered Ball Nose",
                "tip_diameter": 3.0,
                "ball_radius": 1.5,
                "max_diameter": 10.0,
                "tool_length": 60.0,
                "cutting_length": 25.0,
                "taper_angle": 10.0,
                "shank_diameter": 10.0,
                "max_depth": 25.0,
                "neck_diameter": 6.0,
                "flute_length": 25.0,
                "stickout_length": 40.0,
                "overall_length": 60.0,
                "safe_clearance_margin": 1.0,
                "max_engagement": 1.5,
                "max_stepdown": 15.0,
                "max_wall_angle": 60.0,
                "min_feature_width": 1.0,
                "holder_diameter": 25.0,
                "collet_diameter": 20.0,
                "holder_length": 30.0,
                "notes": "Default tapered ball nose tool for professional stone relief engraving."
            },
            {
                "id": "T2",
                "name": "Flat Roughing 6mm",
                "type": "Flat End Mill",
                "tip_diameter": 6.0,
                "ball_radius": 0.0,
                "max_diameter": 6.0,
                "tool_length": 50.0,
                "cutting_length": 30.0,
                "taper_angle": 0.0,
                "shank_diameter": 6.0,
                "max_depth": 30.0,
                "neck_diameter": 6.0,
                "flute_length": 30.0,
                "stickout_length": 40.0,
                "overall_length": 50.0,
                "safe_clearance_margin": 1.0,
                "max_engagement": 3.0,
                "max_stepdown": 3.0,
                "max_wall_angle": 45.0,
                "min_feature_width": 3.0,
                "holder_diameter": 20.0,
                "collet_diameter": 15.0,
                "holder_length": 35.0,
                "notes": "Standard flat endmill for fast material removal roughing passes."
            },
            {
                "id": "T3",
                "name": "V-Bit 60 deg 12mm",
                "type": "V-Bit",
                "tip_diameter": 0.2,
                "ball_radius": 0.1,
                "max_diameter": 12.0,
                "tool_length": 45.0,
                "cutting_length": 15.0,
                "taper_angle": 60.0,
                "shank_diameter": 6.0,
                "max_depth": 10.0,
                "neck_diameter": 6.0,
                "flute_length": 15.0,
                "stickout_length": 35.0,
                "overall_length": 45.0,
                "safe_clearance_margin": 1.0,
                "max_engagement": 1.0,
                "max_stepdown": 2.0,
                "max_wall_angle": 45.0,
                "min_feature_width": 0.2,
                "holder_diameter": 20.0,
                "collet_diameter": 15.0,
                "holder_length": 35.0,
                "notes": "60 degree V-Bit for detailed wood V-carving and engraving."
            },
            {
                "id": "T4",
                "name": "ACP V-Groove 90 deg",
                "type": "V-Bit",
                "tip_diameter": 0.5,
                "ball_radius": 0.25,
                "max_diameter": 16.0,
                "tool_length": 50.0,
                "cutting_length": 10.0,
                "taper_angle": 90.0,
                "shank_diameter": 8.0,
                "max_depth": 8.0,
                "neck_diameter": 8.0,
                "flute_length": 10.0,
                "stickout_length": 40.0,
                "overall_length": 50.0,
                "safe_clearance_margin": 1.0,
                "max_engagement": 1.0,
                "max_stepdown": 2.0,
                "max_wall_angle": 45.0,
                "min_feature_width": 0.5,
                "holder_diameter": 20.0,
                "collet_diameter": 15.0,
                "holder_length": 35.0,
                "notes": "90 degree specialized V-groove cutter for Alucobond/ACP folding lines."
            },
            {
                "id": "T5",
                "name": "Single Flute Acrylic 3mm",
                "type": "Single Flute cutter",
                "tip_diameter": 3.0,
                "ball_radius": 0.0,
                "max_diameter": 3.0,
                "tool_length": 40.0,
                "cutting_length": 12.0,
                "taper_angle": 0.0,
                "shank_diameter": 3.175,
                "max_depth": 12.0,
                "neck_diameter": 3.175,
                "flute_length": 12.0,
                "stickout_length": 30.0,
                "overall_length": 40.0,
                "safe_clearance_margin": 1.0,
                "max_engagement": 1.5,
                "max_stepdown": 1.5,
                "max_wall_angle": 45.0,
                "min_feature_width": 3.0,
                "holder_diameter": 20.0,
                "collet_diameter": 15.0,
                "holder_length": 35.0,
                "notes": "High speed single-flute routing bit for clean acrylic and aluminum cutting."
            }
        ]

    def load(self):
        try:
            if os.path.exists(self.library_path):
                with open(self.library_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # Standardize database format and apply unique tool IDs if missing
                self.tools = []
                for idx, t in enumerate(data):
                    tip_dia = float(t.get("tip_diameter", 3.0))
                    max_dia = float(t.get("max_diameter", 6.0))
                    tool_len = float(t.get("tool_length", 50.0))
                    cut_len = float(t.get("cutting_length", 25.0))
                    shank_dia = float(t.get("shank_diameter", 6.0))
                    
                    tool = {
                        "id": t.get("id", f"T{idx+1}"),
                        "name": t.get("name", "Unnamed Tool"),
                        "type": t.get("type", "Flat End Mill"),
                        "tip_diameter": tip_dia,
                        "ball_radius": float(t.get("ball_radius", 0.0)),
                        "max_diameter": max_dia,
                        "tool_length": tool_len,
                        "cutting_length": cut_len,
                        "taper_angle": float(t.get("taper_angle", 0.0)),
                        "shank_diameter": shank_dia,
                        "max_depth": float(t.get("max_depth", 25.0)),
                        
                        # New physical cutter geometry parameters
                        "neck_diameter": float(t.get("neck_diameter", shank_dia)),
                        "flute_length": float(t.get("flute_length", cut_len)),
                        "stickout_length": float(t.get("stickout_length", tool_len - 10.0)),
                        "overall_length": float(t.get("overall_length", tool_len)),
                        "safe_clearance_margin": float(t.get("safe_clearance_margin", 1.0)),
                        "max_engagement": float(t.get("max_engagement", tip_dia * 0.5)),
                        "max_stepdown": float(t.get("max_stepdown", tip_dia * 0.5)),
                        "max_wall_angle": float(t.get("max_wall_angle", 45.0)),
                        "min_feature_width": float(t.get("min_feature_width", tip_dia)),
                        "holder_diameter": float(t.get("holder_diameter", 20.0)),
                        "collet_diameter": float(t.get("collet_diameter", 15.0)),
                        "holder_length": float(t.get("holder_length", 40.0)),
                        "notes": t.get("notes", "")
                    }
                    self.tools.append(tool)
            else:
                self.tools = self.get_default_tools()
                self.save()
        except Exception:
            self.tools = self.get_default_tools()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.library_path), exist_ok=True)
            with open(self.library_path, "w", encoding="utf-8") as f:
                json.dump(self.tools, f, indent=4)
        except Exception:
            pass

    def add_tool(self, tool_dict):
        if "id" not in tool_dict or not tool_dict["id"]:
            # Generate next ID
            ids = [int(t["id"][1:]) for t in self.tools if t["id"].startswith("T") and t["id"][1:].isdigit()]
            next_num = max(ids) + 1 if ids else 1
            tool_dict["id"] = f"T{next_num}"
        self.tools.append(tool_dict)
        self.save()
        return tool_dict["id"]

    def edit_tool(self, tool_id, updated_dict):
        for idx, t in enumerate(self.tools):
            if t["id"] == tool_id:
                updated_dict["id"] = tool_id
                self.tools[idx] = updated_dict
                self.save()
                return True
        return False

    def delete_tool(self, tool_id):
        for t in self.tools:
            if t["id"] == tool_id:
                self.tools.remove(t)
                self.save()
                return True
        return False

    def get_tool(self, tool_id):
        for t in self.tools:
            if t["id"] == tool_id:
                return t
        return None
