class PostProcessor:
    """
    Handles translation of physical operations and toolpaths into controller-specific G-code files.
    Formats coordinate lines, headers, footers, and tool-change pause macros.
    """
    @staticmethod
    def get_header(processor_type, job_name, stock_x, stock_y, max_depth, tool_name, spindle_speed, safe_z):
        lines = []
        if processor_type == "Mach3":
            lines.append("%")
            lines.append(f"(FILENAME: {job_name}.tap)")
            lines.append(f"(SYSTEM: VELORA CNC CAM ENGINE)")
            lines.append(f"(STOCK WIDTH: {stock_x} mm, LENGTH: {stock_y} mm, DEPTH: {max_depth} mm)")
            lines.append(f"(TOOL IN USE: {tool_name})")
            lines.append("G90 (Absolute Distance Mode)")
            lines.append("G21 (Metric Units - mm)")
            lines.append("G17 (XY Circular Plane)")
            lines.append("G64 (Continuous Velocity Mode)")
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append(f"M03 S{spindle_speed} (Spindle ON)")
            lines.append("G04 P3.000 (Spindle warm up dwell)")
        elif processor_type == "GRBL":
            lines.append(f"; FILENAME: {job_name}.nc")
            lines.append(f"; STOCK: X={stock_x}mm, Y={stock_y}mm, Z={max_depth}mm")
            lines.append(f"; TOOL: {tool_name}")
            lines.append("G90 ; Absolute positioning")
            lines.append("G21 ; Units: mm")
            lines.append("G17 ; XY Plane")
            lines.append("G94 ; Feedrate per minute")
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append(f"M3 S{spindle_speed} ; Spindle ON CW")
            lines.append("G4 P3 ; Dwell 3 seconds")
        elif processor_type == "NCStudio":
            lines.append(f"'{job_name}.nc")
            lines.append(f"'STOCK SIZE: X={stock_x:.2f}, Y={stock_y:.2f}, Z={max_depth:.2f}")
            lines.append(f"'TOOL: {tool_name}")
            lines.append("G90")
            lines.append("G21")
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append(f"M03 S{spindle_speed}")
        else: # Generic ISO G-code
            lines.append("%")
            lines.append(f"(JOB: {job_name})")
            lines.append(f"(TOOL: {tool_name})")
            lines.append("G90")
            lines.append("G21")
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append(f"M03 S{spindle_speed}")
        return lines

    @staticmethod
    def get_footer(processor_type, safe_z):
        lines = []
        if processor_type == "Mach3":
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append("M05 (Stop Spindle)")
            lines.append("G00 X0.000 Y0.000 (Return Home)")
            lines.append("M30 (End of Program)")
            lines.append("%")
        elif processor_type == "GRBL":
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append("M5 ; Spindle OFF")
            lines.append("G00 X0 Y0 ; Return Home")
            lines.append("M30 ; Program End")
        elif processor_type == "NCStudio":
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append("M05")
            lines.append("G00 X0.000 Y0.000")
            lines.append("M30")
        else:
            lines.append(f"G00 Z{safe_z:.3f}")
            lines.append("M05")
            lines.append("M30")
        return lines

    @staticmethod
    def get_pause_code(processor_type, tool_name, tool_id, safe_z, tool_change_pos=None):
        lines = []
        comment_symbol = ";" if processor_type == "GRBL" else "'" if processor_type == "NCStudio" else ""
        
        # Spindle stop
        lines.append("M05" + (" ; Spindle OFF" if processor_type == "GRBL" else " (Stop Spindle)" if processor_type == "Mach3" else ""))
        
        # Z safe retract
        if processor_type == "Mach3":
            lines.append(f"G00 Z{safe_z:.3f} (Safe Retract)")
        elif processor_type == "GRBL":
            lines.append(f"G00 Z{safe_z:.3f} ; Safe Retract")
        else:
            lines.append(f"G00 Z{safe_z:.3f}")
            
        # Optional tool change position travel
        if tool_change_pos:
            tx = tool_change_pos.get("x", None)
            ty = tool_change_pos.get("y", None)
            if tx is not None or ty is not None:
                coord_parts = []
                if tx is not None: coord_parts.append(f"X{tx:.3f}")
                if ty is not None: coord_parts.append(f"Y{ty:.3f}")
                lines.append(f"G00 {' '.join(coord_parts)}")
                
        # Pause execution command
        if processor_type == "Mach3":
            lines.append(f"(CHANGE TO TOOL: {tool_name} ID: {tool_id})")
            lines.append("(RESET Z HEIGHT BEFORE RESUMING)")
            lines.append("M00 (Operator Pause)")
        elif processor_type == "GRBL":
            lines.append(f"; CHANGE TO TOOL: {tool_name} ID: {tool_id}")
            lines.append("; RESET Z HEIGHT BEFORE RESUMING")
            lines.append("M0 ; Pause")
        elif processor_type == "NCStudio":
            lines.append(f"'CHANGE TO TOOL: {tool_name} ID: {tool_id}")
            lines.append("M00")
        else:
            lines.append("M00")
            
        return lines
