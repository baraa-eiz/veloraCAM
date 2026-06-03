class ModalWriter:
    """
    Tracks and writes modal G-code coordinates to save file space and avoid controller bottlenecks.
    Includes coordinates jitter filters and statistical metrics for toolpath diagnostics.
    """
    def __init__(self, file_handle, min_xy=0.02, min_z=0.03):
        self.f = file_handle
        self.min_xy = min_xy
        self.min_z = min_z
        self.active_g = None  # None, "G00", or "G01"
        self.active_f = None  # Spindle Feedrate F
        self.last_x = None
        self.last_y = None
        self.last_z = None
        self.g0_count = 0
        self.g1_count = 0
        self.redundant_coords_count = 0
        self.total_lines_written = 0
        self.total_z_travel = 0.0
        self.z_retracts_count = 0
        self.z_plunges_count = 0

    def write_comment(self, txt):
        self.f.write(f"({txt})\n")
        self.total_lines_written += 1

    def write_raw_line(self, line):
        self.f.write(line + "\n")
        self.total_lines_written += 1

    def write_move(self, g_cmd, x=None, y=None, z=None, f_val=None):
        """
        Writes G-code movement vector, applying modal parameters and coordinate jitter filters.
        """
        # Calculate shifts
        dx = abs(x - self.last_x) if (x is not None and self.last_x is not None) else 999.0
        dy = abs(y - self.last_y) if (y is not None and self.last_y is not None) else 999.0
        dz = abs(z - self.last_z) if (z is not None and self.last_z is not None) else 999.0
        
        # Verify significant changes
        change_xy = (x is not None and (self.last_x is None or dx >= self.min_xy)) or \
                    (y is not None and (self.last_y is None or dy >= self.min_xy))
        change_z = (z is not None and (self.last_z is None or dz >= self.min_z))
        
        if not change_xy and not change_z and (f_val is None or f_val == self.active_f) and g_cmd == self.active_g:
            self.redundant_coords_count += 1
            return  # Filter redundant command
            
        # Z travel metrics
        if z is not None and self.last_z is not None and dz >= self.min_z:
            self.total_z_travel += dz
            if z > self.last_z:
                self.z_retracts_count += 1
            elif z < self.last_z:
                self.z_plunges_count += 1
                
        parts = []
        if g_cmd != self.active_g:
            parts.append(g_cmd)
            self.active_g = g_cmd
            
        if x is not None and (self.last_x is None or dx >= self.min_xy):
            parts.append(f"X{x:.3f}")
            self.last_x = x
        if y is not None and (self.last_y is None or dy >= self.min_xy):
            parts.append(f"Y{y:.3f}")
            self.last_y = y
        if z is not None and (self.last_z is None or dz >= self.min_z):
            parts.append(f"Z{z:.3f}")
            self.last_z = z
            
        if f_val is not None and f_val != self.active_f:
            parts.append(f"F{f_val:.0f}")
            self.active_f = f_val
            
        if parts:
            line = " ".join(parts)
            self.f.write(line + "\n")
            self.total_lines_written += 1
            if g_cmd == "G00":
                self.g0_count += 1
            elif g_cmd == "G01":
                self.g1_count += 1

    def write_tool_change(self, tool_id, tool_name, safe_z, tool_change_pos=None, pause_cmd="M0"):
        """
        Injects a safe tool-change sequence including spindle stops, retracts, XY travel, and operator instructions.
        """
        self.write_comment("--------------------------------------------------")
        self.write_comment("TOOL CHANGE REQUIRED")
        self.write_comment(f"CHANGE TO TOOL: {tool_name} (ID: {tool_id})")
        self.write_comment("--------------------------------------------------")
        
        # 1. Stop spindle
        self.write_raw_line("M05 (Stop Spindle)")
        
        # 2. Retract to safe Z clearance
        self.write_move("G00", z=safe_z)
        
        # 3. Optional travel to tool change coordinates
        if tool_change_pos:
            tx = tool_change_pos.get("x", None)
            ty = tool_change_pos.get("y", None)
            self.write_move("G00", x=tx, y=ty)
            
        # 4. Display comments instructing operator and pause
        self.write_comment("RESET Z ZERO / PROBE TOOL HEIGHT BEFORE CONTINUING")
        self.write_comment("PRESS CYCLE START AFTER Z HEIGHT IS SET")
        self.write_raw_line(f"{pause_cmd} (Pause for tool change)")
        
        # 5. Clear active states (forcing full coordinates write on next move)
        self.active_g = None
        self.active_f = None
        self.last_x = None
        self.last_y = None
        self.last_z = None
