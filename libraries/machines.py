class MachineLibrary:
    """
    Manages custom machine profiles for Velora CNC.
    Enforces safe cutting boundaries, spindle limitations, and tool change pauses.
    """
    def __init__(self):
        self.machines = {
            "Generic Stone Router": {
                "name": "Generic Stone Router",
                "x_limit": 1200.0,
                "y_limit": 2400.0,
                "z_limit": 300.0,
                "safe_z": 25.0,
                "tool_change_x": 0.0,
                "tool_change_y": 0.0,
                "tool_change_z": 50.0,
                "spindle_min": 6000,
                "spindle_max": 24000,
                "controller": "Mach3",
                "post_processor": "Mach3",
                "probe_thickness": 10.0,
                "z_zero_type": "Workpiece Top"
            },
            "Desktop Wood CNC": {
                "name": "Desktop Wood CNC",
                "x_limit": 300.0,
                "y_limit": 300.0,
                "z_limit": 80.0,
                "safe_z": 15.0,
                "tool_change_x": 0.0,
                "tool_change_y": 150.0,
                "tool_change_z": 30.0,
                "spindle_min": 8000,
                "spindle_max": 24000,
                "controller": "GRBL",
                "post_processor": "GRBL",
                "probe_thickness": 0.0,
                "z_zero_type": "Workpiece Top"
            },
            "Industrial 4-Axis Router": {
                "name": "Industrial 4-Axis Router",
                "x_limit": 2000.0,
                "y_limit": 4000.0,
                "z_limit": 400.0,
                "safe_z": 40.0,
                "tool_change_x": 1000.0,
                "tool_change_y": 0.0,
                "tool_change_z": 100.0,
                "spindle_min": 3000,
                "spindle_max": 18000,
                "controller": "NCStudio",
                "post_processor": "NCStudio",
                "probe_thickness": 20.0,
                "z_zero_type": "Spoilboard"
            }
        }

    def get_machine(self, name):
        return self.machines.get(name, self.machines["Generic Stone Router"])

    def get_all_names(self):
        return list(self.machines.keys())
