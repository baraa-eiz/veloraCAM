class BaseModule:
    """
    Abstract Base Class for all CAM modules in Velora CNC.
    Defines common step structures, operational defaults, validation checks,
    and G-code routing wrappers.
    """
    def __init__(self, name="Base Module"):
        self.name = name

    def get_suggested_operations(self, material_preset=None, style_preset=None):
        """
        Returns a list of suggested operations for the module based on presets.
        Must be implemented by subclasses.
        """
        return []

    def validate_operation(self, op, tool_library, stock_x, stock_y, max_depth):
        """
        Performs structural verification checks on a single operation's parameter set.
        """
        warnings = []
        tool_id = op.get("tool_id", "")
        tool = tool_library.get_tool(tool_id) if tool_library else None
        
        if not tool:
            warnings.append("Missing or unassigned cutting tool.")
            return warnings

        # 1. Verification of physical cutting limits
        cutting_len = tool.get("cutting_length", 25.0)
        op_depth = op.get("max_depth", max_depth)
        if op_depth > cutting_len:
            warnings.append(f"Collision Risk: Target depth ({op_depth}mm) exceeds tool cutting length ({cutting_len}mm).")

        # 2. Verification of stepdown safety limits
        stepdown = op.get("stepdown", 1.0)
        tool_dia = tool.get("tip_diameter", 3.0)
        if stepdown > tool_dia * 2.0:
            warnings.append(f"Extreme Stepdown: Cutting depth per pass ({stepdown}mm) exceeds twice tool diameter.")

        # 3. Verification of stepover safety limits
        stepover = op.get("stepover", 1.0)
        if stepover >= tool_dia:
            warnings.append(f"Excessive Stepover: Vector spacing ({stepover}mm) exceeds tool cutting diameter.")

        return warnings

    def compile_toolpath(self, op, arr, project_params, progress_callback=None):
        """
        Compiles the mathematical toolpath vectors for the operation.
        Must be implemented by subclasses.
        """
        return []
