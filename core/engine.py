import numpy as np
import heapq

class NaturalCubicSpline:
    def __init__(self, x, y):
        self.x = np.asanyarray(x, dtype=float)
        self.y = np.asanyarray(y, dtype=float)
        n = len(x)
        self.n = n
        if n < 2:
            raise ValueError("Need at least 2 points")
        if n == 2:
            self.a = self.y[:-1]
            self.b = (self.y[1:] - self.y[:-1]) / max(1e-5, self.x[1:] - self.x[:-1])
            self.c = np.zeros(1)
            self.d = np.zeros(1)
            return
            
        h = np.diff(self.x)
        h = np.maximum(h, 1e-5) # prevent division by zero
        A = np.zeros((n, n))
        B = np.zeros(n)
        A[0, 0] = 1.0
        A[-1, -1] = 1.0
        for i in range(1, n - 1):
            A[i, i - 1] = h[i - 1]
            A[i, i] = 2.0 * (h[i - 1] + h[i])
            A[i, i + 1] = h[i]
            B[i] = 3.0 * ((self.y[i + 1] - self.y[i]) / h[i] - (self.y[i] - self.y[i - 1]) / h[i - 1])
            
        try:
            c = np.linalg.solve(A, B)
        except Exception:
            c = np.zeros(n)
            
        self.a = self.y[:-1]
        self.c = c[:-1]
        self.d = (c[1:] - c[:-1]) / (3.0 * h)
        self.b = (self.y[1:] - self.y[:-1]) / h - h * (c[1:] + 2.0 * c[:-1]) / 3.0

    def evaluate(self, t):
        t = np.asanyarray(t, dtype=float)
        idx = np.searchsorted(self.x, t) - 1
        idx = np.clip(idx, 0, self.n - 2)
        dx = t - self.x[idx]
        return self.a[idx] + self.b[idx] * dx + self.c[idx] * (dx ** 2) + self.d[idx] * (dx ** 3)

class HeightmapGeometrySource:
    """
    A generic geometric representation of the heightmap surface.
    Conforms to future mesh/STL/voxel extensions.
    """
    def __init__(self, arr, stock_x, stock_y, max_depth, carving_w, carving_h, 
                 min_x, min_y, offset_x, offset_y, preserve_aspect, base_color=None, 
                 invert_check=False, curve_params=None):
        self.arr = arr
        self.stock_x = stock_x
        self.stock_y = stock_y
        self.max_depth = max_depth
        self.carving_w = carving_w
        self.carving_h = carving_h
        self.min_x = min_x
        self.min_y = min_y
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.preserve_aspect = preserve_aspect
        self.base_color = base_color
        self.invert_check = invert_check
        self.curve_params = curve_params
        
    def get_z_at(self, xs, ys):
        return CAMEngine.compute_surface_z_vectorized(
            xs, ys, self.arr, self.stock_x, self.stock_y, self.max_depth,
            self.carving_w, self.carving_h, self.min_x, self.min_y, 
            self.offset_x, self.offset_y, self.preserve_aspect, 
            self.base_color, self.invert_check, curve_params=self.curve_params
        )

class CAMEngine:
    """
    CAM Mathematics and Vectorized Calculation Engine for Velora CNC.
    Handles bilinear interpolation, 3D tool radius compensation, collinear compression,
    and obstacle avoidance path routing.
    """
    @staticmethod
    def compute_surface_z_vectorized(xs, ys, arr, stock_x, stock_y, max_depth,
                                    carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                                    preserve_aspect, base_color=None, invert_check=False,
                                    curve_params=None):
        """
        Bilinear interpolation of displacement map height values using vectorized NumPy operations.
        """
        is_scalar = isinstance(xs, (int, float)) or np.isscalar(xs)
        if is_scalar:
            xs_arr = np.array([xs], dtype=float)
            ys_arr = np.array([ys], dtype=float)
        else:
            xs_arr = np.asanyarray(xs, dtype=float)
            ys_arr = np.asanyarray(ys, dtype=float)
            
        img_h, img_w = arr.shape
        
        if preserve_aspect:
            scaled_w = carving_w * (stock_x / carving_w if stock_x/carving_w < stock_y/carving_h else stock_y/carving_h)
            scaled_h = carving_h * (stock_x / carving_w if stock_x/carving_w < stock_y/carving_h else stock_y/carving_h)
            
            cx = xs_arr - offset_x
            cy = ys_arr - offset_y
            in_bounds = (cx >= 0) & (cx < scaled_w) & (cy >= 0) & (cy < scaled_h)
            
            px = np.zeros_like(cx)
            py = np.zeros_like(cy)
            
            px[in_bounds] = min_x + (cx[in_bounds] / scaled_w) * carving_w
            py[in_bounds] = min_y - (cy[in_bounds] / scaled_h) * carving_h
        else:
            px = (xs_arr / stock_x) * (img_w - 1)
            py = (img_h - 1) - (ys_arr / stock_y) * (img_h - 1)
            in_bounds = np.ones_like(px, dtype=bool)
            
        px = np.clip(px, 0.0, float(img_w - 1))
        py = np.clip(py, 0.0, float(img_h - 1))
        
        x0 = np.floor(px).astype(int)
        x1 = np.minimum(img_w - 1, x0 + 1)
        y0 = np.floor(py).astype(int)
        y1 = np.minimum(img_h - 1, y0 + 1)
        
        dx = px - x0
        dy = py - y0
        
        v00 = arr[y0, x0]
        v10 = arr[y0, x1]
        v01 = arr[y1, x0]
        v11 = arr[y1, x1]
        
        val = (1.0 - dx) * (1.0 - dy) * v00 + dx * (1.0 - dy) * v10 + (1.0 - dx) * dy * v01 + dx * dy * v11
        
        if base_color is not None:
            if invert_check:
                if base_color <= 0.0:
                    z_val = -max_depth * (1.0 - val / 255.0)
                else:
                    z_val = np.zeros_like(val)
                    z_val[val >= base_color] = 0.0
                    z_val[val <= 0.0] = -max_depth
                    
                    middle = (val > 0.0) & (val < base_color)
                    if np.any(middle):
                        factor = val[middle] / float(base_color)
                        z_val[middle] = -max_depth * (1.0 - factor)
            else:
                if base_color >= 255.0:
                    z_val = -max_depth * (1.0 - val / 255.0)
                else:
                    z_val = np.zeros_like(val)
                    z_val[val <= base_color] = -max_depth
                    z_val[val >= 255.0] = 0.0
                    
                    middle = (val > base_color) & (val < 255.0)
                    if np.any(middle):
                        factor = (val[middle] - base_color) / float(255.0 - base_color)
                        z_val[middle] = -max_depth * (1.0 - factor)
        else:
            z_val = -max_depth * (1.0 - val / 255.0)
            
        if preserve_aspect:
            z_val[~in_bounds] = -max_depth
            
        if curve_params is not None and curve_params.get("curve_enabled", False):
            offsets = CAMEngine.evaluate_curve_offset_at_xy(xs_arr, ys_arr, stock_x, stock_y, curve_params)
            z_val = z_val + offsets
            
        return z_val[0] if is_scalar else z_val

    @staticmethod
    def get_tool_profile_z_offset(ttype, r, tool_params):
        """
        Calculates vertical offset offset (Z) for tool profiles based on center radius r.
        """
        if ttype == "Flat End Mill":
            R_max = tool_params.get("tip_diameter", 3.0) / 2.0
            if r <= R_max:
                return 0.0
            return 9999.0
        elif ttype == "Ball Nose":
            R_ball = tool_params.get("ball_radius", 1.5)
            R_max = tool_params.get("tip_diameter", 3.0) / 2.0
            if r <= R_ball:
                return R_ball - np.sqrt(max(0.0, R_ball**2 - r**2))
            elif r <= R_max:
                return R_ball
            return 9999.0
        elif ttype == "V-Bit":
            R_tip = tool_params.get("tip_diameter", 0.0) / 2.0
            R_max = tool_params.get("max_diameter", 10.0) / 2.0
            angle = tool_params.get("taper_angle", 60.0)
            theta = np.radians(angle / 2.0)
            if r <= R_tip:
                return 0.0
            elif r <= R_max:
                return (r - R_tip) / max(1e-5, np.tan(theta))
            return 9999.0
        elif ttype == "Tapered Ball Nose":
            R_tip = tool_params.get("ball_radius", 1.5)
            R_max = tool_params.get("max_diameter", 10.0) / 2.0
            angle = tool_params.get("taper_angle", 10.0)
            theta = np.radians(angle)
            r_tangent = R_tip * np.cos(theta)
            z_tangent = R_tip - R_tip * np.sin(theta)
            if r <= r_tangent:
                return R_tip - np.sqrt(max(0.0, R_tip**2 - r**2))
            elif r <= R_max:
                return z_tangent + (r - r_tangent) / max(1e-5, np.tan(theta))
            return 9999.0
        return 0.0

    @staticmethod
    def compute_compensated_z_array(xs, ys, ttype, tool_params, arr, stock_x, stock_y, max_depth,
                                   carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                                   preserve_aspect, base_color=None, invert_check=False,
                                   curve_params=None, toolpath_geometry_mode="Legacy"):
        """
        Precomputes the tool profile offsets and evaluates maximum compensated vertical Z points in parallel.
        Supports both Legacy center-point nose compensation and Tool Geometry Aware modeling.
        """
        if toolpath_geometry_mode == "Geometry Aware":
            safe_margin = float(tool_params.get("safe_clearance_margin", 1.0))
            r_samples, z_offsets = CAMEngine.compute_tool_profile_lut(tool_params, ttype, safe_margin)
            
            r_cutter = float(tool_params.get("tip_diameter", 3.0)) / 2.0
            r_neck = float(tool_params.get("neck_diameter", tool_params.get("max_diameter", 6.0))) / 2.0
            r_max = r_samples[-1] - safe_margin
            
            grid_pts = CAMEngine.generate_optimized_search_grid(r_cutter, r_neck, r_max, safe_margin)
            grid_dx = grid_pts[:, 0]
            grid_dy = grid_pts[:, 1]
            grid_r = grid_pts[:, 2]
            
            grid_z_offsets = np.interp(grid_r, r_samples, z_offsets)
            
            N = len(xs)
            max_zs = np.full(N, -9999.0)
            
            for dx, dy, z_off in zip(grid_dx, grid_dy, grid_z_offsets):
                local_xs = xs + dx
                local_ys = ys + dy
                z_surfs = CAMEngine.compute_surface_z_vectorized(
                    local_xs, local_ys, arr, stock_x, stock_y, max_depth,
                    carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                    preserve_aspect, base_color, invert_check, curve_params=curve_params
                )
                max_zs = np.maximum(max_zs, z_surfs - z_off)
                
            return max_zs

        # Determine R_max (Legacy Mode)
        tip_dia = tool_params.get("tip_diameter", 3.0)
        ball_rad = tool_params.get("ball_radius", 1.5)
        max_dia = tool_params.get("max_diameter", 10.0)
        
        if ttype == "Flat End Mill":
            R_max = tip_dia / 2.0
        elif ttype == "Ball Nose":
            R_max = tip_dia / 2.0
        else:
            R_max = max_dia / 2.0
            
        R_max = max(0.1, R_max)
        search_step = max(0.1, min(0.5, R_max / 8.0))
        search_range = np.arange(-R_max, R_max + search_step, search_step)
        
        grid_dx, grid_dy = np.meshgrid(search_range, search_range)
        grid_dx = grid_dx.flatten()
        grid_dy = grid_dy.flatten()
        grid_r = np.sqrt(grid_dx**2 + grid_dy**2)
        
        mask = grid_r <= R_max
        grid_dx = grid_dx[mask]
        grid_dy = grid_dy[mask]
        grid_r = grid_r[mask]
        
        grid_z_offsets = np.array([CAMEngine.get_tool_profile_z_offset(ttype, r, tool_params) for r in grid_r])
        valid = grid_z_offsets < 9000.0
        grid_dx = grid_dx[valid]
        grid_dy = grid_dy[valid]
        grid_z_offsets = grid_z_offsets[valid]
        
        N = len(xs)
        max_zs = np.full(N, -9999.0)
        
        for dx, dy, z_off in zip(grid_dx, grid_dy, grid_z_offsets):
            local_xs = xs + dx
            local_ys = ys + dy
            z_surfs = CAMEngine.compute_surface_z_vectorized(
                local_xs, local_ys, arr, stock_x, stock_y, max_depth,
                carving_w, carving_h, min_x, min_y, offset_x, offset_y,
                preserve_aspect, base_color, invert_check, curve_params=curve_params
            )
            max_zs = np.maximum(max_zs, z_surfs - z_off)
            
        return max_zs

    @staticmethod
    def compress_path_3d(points, tolerance):
        """
        Recursive Ramer-Douglas-Peucker (RDP) algorithm for 3D trajectory compression.
        """
        if len(points) < 3 or tolerance <= 0.0:
            return points
            
        start = points[0]
        end = points[-1]
        
        line_vec = end - start
        line_len = np.linalg.norm(line_vec)
        
        if line_len < 1e-8:
            dists = np.linalg.norm(points[1:-1] - start, axis=1)
        else:
            t = np.dot(points[1:-1] - start, line_vec) / (line_len ** 2)
            t = np.clip(t, 0.0, 1.0)
            proj = start + t[:, np.newaxis] * line_vec
            dists = np.linalg.norm(points[1:-1] - proj, axis=1)
            
        if len(dists) == 0:
            return points
            
        max_idx = np.argmax(dists)
        max_dist = dists[max_idx]
        
        if max_dist > tolerance:
            split_idx = max_idx + 1
            left = CAMEngine.compress_path_3d(points[:split_idx+1], tolerance)
            right = CAMEngine.compress_path_3d(points[split_idx:], tolerance)
            return np.vstack((left[:-1], right))
        else:
            return np.array([start, end])

    @staticmethod
    def find_avoidance_path(start_xy, end_xy, obstacle_grid, grid_size, stock_x, stock_y):
        """
        Runs highly optimized grid-based A* routing to detour around No-Go obstacles safely.
        """
        def to_grid(gx, gy):
            c = int(np.floor(gx / grid_size))
            r = int(np.floor(gy / grid_size))
            c = max(0, min(obstacle_grid.shape[1] - 1, c))
            r = max(0, min(obstacle_grid.shape[0] - 1, r))
            return r, c
            
        def to_world(r, c):
            return (c + 0.5) * grid_size, (r + 0.5) * grid_size
            
        start_r, start_c = to_grid(start_xy[0], start_xy[1])
        end_r, end_c = to_grid(end_xy[0], end_xy[1])
        
        rows, cols = obstacle_grid.shape
        
        # A* Pathfinder search variables
        open_set = []
        heapq.heappush(open_set, (0, start_r, start_c))
        
        came_from = {}
        g_score = {(start_r, start_c): 0.0}
        
        def heuristic(r1, c1, r2, c2):
            return np.sqrt((r2 - r1)**2 + (c2 - c1)**2)
            
        found = False
        while open_set:
            _, r, c = heapq.heappop(open_set)
            
            if r == end_r and c == end_c:
                found = True
                break
                
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if obstacle_grid[nr, nc]:
                        continue # Forbidden cell!
                        
                    step_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
                    tentative_g = g_score[(r, c)] + step_cost
                    
                    if (nr, nc) not in g_score or tentative_g < g_score[(nr, nc)]:
                        g_score[(nr, nc)] = tentative_g
                        f_score = tentative_g + heuristic(nr, nc, end_r, end_c)
                        came_from[(nr, nc)] = (r, c)
                        heapq.heappush(open_set, (f_score, nr, nc))
                        
        if not found:
            return [start_xy, end_xy]  # Fallback to direct routing if blocked
            
        # Reconstruct path
        curr = (end_r, end_c)
        grid_path = [curr]
        while curr in came_from:
            curr = came_from[curr]
            grid_path.append(curr)
            
        grid_path.reverse()
        
        # Convert path points back to world coords
        world_path = [start_xy]
        for step in grid_path[1:-1]:
            world_path.append(to_world(step[0], step[1]))
        world_path.append(end_xy)
        
        return world_path

    @staticmethod
    def dilate_mask(mask, R):
        if R <= 0:
            return mask.copy()
        rows, cols = mask.shape
        dilated = np.copy(mask)
        Y, X = np.ogrid[-R:R+1, -R:R+1]
        disk = X**2 + Y**2 <= R**2
        for dy in range(-R, R+1):
            for dx in range(-R, R+1):
                if not disk[dy+R, dx+R]:
                    continue
                shifted = np.zeros_like(mask)
                r_start = max(0, dy)
                r_end = min(rows, rows + dy)
                c_start = max(0, dx)
                c_end = min(cols, cols + dx)
                
                mr_start = max(0, -dy)
                mr_end = min(rows, rows - dy)
                mc_start = max(0, -dx)
                mc_end = min(cols, cols - dx)
                
                shifted[r_start:r_end, c_start:c_end] = mask[mr_start:mr_end, mc_start:mc_end]
                dilated |= shifted
        return dilated

    @staticmethod
    def filter_small_islands(mask, min_area):
        if min_area <= 1:
            return mask.copy()
        rows, cols = mask.shape
        visited = np.zeros_like(mask, dtype=bool)
        output_mask = np.copy(mask)
        
        for r in range(rows):
            for c in range(cols):
                if mask[r, c] and not visited[r, c]:
                    comp = []
                    stack = [(r, c)]
                    visited[r, c] = True
                    too_large = False
                    
                    while stack:
                        curr_r, curr_c = stack.pop()
                        comp.append((curr_r, curr_c))
                        if len(comp) >= min_area:
                            too_large = True
                            break
                        
                        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                            nr, nc = curr_r + dr, curr_c + dc
                            if 0 <= nr < rows and 0 <= nc < cols:
                                if mask[nr, nc] and not visited[nr, nc]:
                                    visited[nr, nc] = True
                                    stack.append((nr, nc))
                                    
                    if too_large:
                        large_stack = stack
                        while large_stack:
                            curr_r, curr_c = large_stack.pop()
                            for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                                nr, nc = curr_r + dr, curr_c + dc
                                if 0 <= nr < rows and 0 <= nc < cols:
                                    if mask[nr, nc] and not visited[nr, nc]:
                                        visited[nr, nc] = True
                                        large_stack.append((nr, nc))
                    else:
                        for cr, cc in comp:
                            output_mask[cr, cc] = False
        return output_mask

    @staticmethod
    def box_blur(arr, R):
        if R <= 0:
            return arr.copy()
        rows, cols = arr.shape
        accum = np.zeros_like(arr, dtype=float)
        count = 0
        for dy in range(-R, R+1):
            for dx in range(-R, R+1):
                r_start = max(0, dy)
                r_end = min(rows, rows + dy)
                c_start = max(0, dx)
                c_end = min(cols, cols + dx)
                
                mr_start = max(0, -dy)
                mr_end = min(rows, rows - dy)
                mc_start = max(0, -dx)
                mc_end = min(cols, cols - dx)
                
                shifted = np.zeros_like(arr, dtype=float)
                shifted[r_start:r_end, c_start:c_end] = arr[mr_start:mr_end, mc_start:mc_end]
                accum += shifted
                count += 1
        return (accum / count).astype(arr.dtype)

    @staticmethod
    def optimize_surface(arr, project):
        """
        Runs the full surface optimization pipeline on the 2D heightmap array.
        """
        # Make a copy to avoid mutating raw image data
        out = arr.copy().astype(float)
        rows, cols = arr.shape
        
        # 1. Base Detection
        base_mask = np.zeros_like(arr, dtype=bool)
        
        # Selected Base Color
        if project.opt_flatten_selected_base and project.base_color is not None:
            base_mask |= (np.abs(arr.astype(float) - project.base_color) <= project.opt_base_tolerance)
            
        # Auto Flat Areas detection (low gradient)
        if project.opt_flatten_all_flat:
            dy = np.zeros_like(arr, dtype=float)
            dx = np.zeros_like(arr, dtype=float)
            dy[1:-1, :] = (arr[2:, :].astype(float) - arr[:-2, :].astype(float)) / 2.0
            dx[:, 1:-1] = (arr[:, 2:].astype(float) - arr[:, :-2].astype(float)) / 2.0
            dy[0, :] = arr[1, :].astype(float) - arr[0, :].astype(float)
            dy[-1, :] = arr[-1, :].astype(float) - arr[-2, :].astype(float)
            dx[:, 0] = arr[:, 1].astype(float) - arr[:, 0].astype(float)
            dx[:, -1] = arr[:, -1].astype(float) - arr[:, -2].astype(float)
            
            gradient = np.sqrt(dx**2 + dy**2)
            base_mask |= (gradient <= project.opt_flat_slope_tol)
            
        # Store initial mask for preview
        detected_base_raw = base_mask.copy()
        
        # 2. Base Cleanup (Island Filter)
        if project.opt_min_region_size > 1:
            base_mask = CAMEngine.filter_small_islands(base_mask, project.opt_min_region_size)
            
        # 3. Edge Protection
        if project.opt_preserve_edges and project.opt_edge_distance_mm > 0.0:
            # Convert mm to pixels based on stock dimension
            pixel_size_x = project.stock_x / max(1, cols)
            erosion_pixels = int(np.round(project.opt_edge_distance_mm / pixel_size_x))
            erosion_pixels = max(1, min(erosion_pixels, 50)) # Clamp to sane range
            
            # Erode the base mask (which dilates the relief / non-base)
            base_mask = ~CAMEngine.dilate_mask(~base_mask, erosion_pixels)
            
        # 4. Surface Smoothing
        # Level mapping to box filter radius
        smooth_radius = 0
        if project.opt_smoothing_level == "Light":
            smooth_radius = 1
        elif project.opt_smoothing_level == "Medium":
            smooth_radius = 2
        elif project.opt_smoothing_level == "Aggressive":
            smooth_radius = 4
            
        if smooth_radius > 0:
            smoothed = CAMEngine.box_blur(out, smooth_radius)
            # Apply smoothing only on non-base areas to keep base perfectly flat
            out[~base_mask] = smoothed[~base_mask]
            
        # 5. Base Flattening
        # Set all remaining base pixels to the base color
        if np.any(base_mask):
            target_val = project.base_color if project.base_color is not None else 0.0
            out[base_mask] = target_val
            
        return out, detected_base_raw, base_mask, out

    @staticmethod
    def apply_min_z_variation_filter(points, min_z_var):
        if len(points) < 2 or min_z_var <= 0.0:
            return points
        filtered = np.copy(points)
        last_z = filtered[0, 2]
        for i in range(1, len(filtered)):
            if np.abs(filtered[i, 2] - last_z) < min_z_var:
                filtered[i, 2] = last_z
            else:
                last_z = filtered[i, 2]
        return filtered

    @staticmethod
    def get_normalized_u(x, y, stock_x, stock_y, direction, diagonal_dir="Top Left -> Bottom Right"):
        if direction == "X Axis":
            return np.clip(x / max(1e-5, stock_x), 0.0, 1.0)
        elif direction == "Y Axis":
            return np.clip(y / max(1e-5, stock_y), 0.0, 1.0)
        elif direction == "Diagonal":
            denom = max(1e-5, stock_x**2 + stock_y**2)
            if diagonal_dir == "Top Left -> Bottom Right":
                u = (x * stock_x - (y - stock_y) * stock_y) / denom
            else: # "Bottom Left -> Top Right"
                u = (x * stock_x + y * stock_y) / denom
            return np.clip(u, 0.0, 1.0)
        return 0.0

    @staticmethod
    def evaluate_curve(u, control_pts, interpolation_type, smoothness, stock_len=1.0):
        pts = sorted(control_pts, key=lambda p: p["pos"])
        if len(pts) < 2:
            is_scalar = isinstance(u, (int, float)) or np.isscalar(u)
            return 0.0 if is_scalar else np.zeros_like(u, dtype=float)
            
        x_pts = np.array([p["pos"] / 100.0 for p in pts])
        y_pts = np.array([p["z"] for p in pts])
        
        u_arr = np.asanyarray(u, dtype=float)
        is_scalar = isinstance(u, (int, float)) or np.isscalar(u)
        
        y_linear = np.interp(u_arr, x_pts, y_pts)
        
        if interpolation_type == "Linear":
            res = y_linear
        elif interpolation_type == "Smooth Spline":
            try:
                spline = NaturalCubicSpline(x_pts, y_pts)
                y_spline = spline.evaluate(u_arr)
            except Exception:
                y_spline = y_linear
            s = smoothness / 100.0
            res = (1.0 - s) * y_linear + s * y_spline
        elif interpolation_type == "Rounded / Soft Curve":
            y_rounded = np.zeros_like(u_arr)
            for i in range(len(x_pts) - 1):
                x0, x1 = x_pts[i], x_pts[i+1]
                y0, y1 = y_pts[i], y_pts[i+1]
                if i == len(x_pts) - 2:
                    mask = (u_arr >= x0) & (u_arr <= x1)
                else:
                    mask = (u_arr >= x0) & (u_arr < x1)
                if np.any(mask):
                    t = (u_arr[mask] - x0) / max(1e-5, x1 - x0)
                    ft = (1.0 - np.cos(t * np.pi)) * 0.5
                    y_rounded[mask] = y0 * (1.0 - ft) + y1 * ft
            y_rounded[u_arr < x_pts[0]] = y_pts[0]
            y_rounded[u_arr > x_pts[-1]] = y_pts[-1]
            s = smoothness / 100.0
            res = (1.0 - s) * y_linear + s * y_rounded
        else:
            res = y_linear
            
        return float(res) if is_scalar else res

    @staticmethod
    def get_curve_reference_offset(control_pts, interpolation_type, smoothness, reference_mode):
        sample_u = np.linspace(0.0, 1.0, 200)
        sample_z = CAMEngine.evaluate_curve(sample_u, control_pts, interpolation_type, smoothness)
        start_z = sample_z[0]
        end_z = sample_z[-1]
        min_z = np.min(sample_z)
        max_z = np.max(sample_z)
        
        if reference_mode == "Lock Start Point":
            return start_z
        elif reference_mode == "Lock End Point":
            return end_z
        elif reference_mode == "Lock Minimum Z":
            return min_z
        elif reference_mode == "Lock Maximum Z":
            return max_z
        elif reference_mode == "Lock Center Plane":
            return (min_z + max_z) / 2.0
        return 0.0

    @staticmethod
    def evaluate_curve_offset_at_xy(x, y, stock_x, stock_y, curve_params):
        if not curve_params or not curve_params.get("curve_enabled", False):
            is_scalar = isinstance(x, (int, float)) or np.isscalar(x)
            return 0.0 if is_scalar else np.zeros_like(x, dtype=float)
            
        direction = curve_params.get("curve_direction", "X Axis")
        diagonal_dir = curve_params.get("curve_diagonal_dir", "Top Left -> Bottom Right")
        control_pts = curve_params.get("curve_control_points", [])
        interpolation_type = curve_params.get("curve_interpolation_type", "Smooth Spline")
        smoothness = curve_params.get("curve_smoothness", 50.0)
        reference_mode = curve_params.get("curve_reference_mode", "Lock Center Plane")
        
        u = CAMEngine.get_normalized_u(x, y, stock_x, stock_y, direction, diagonal_dir)
        raw_z = CAMEngine.evaluate_curve(u, control_pts, interpolation_type, smoothness)
        ref_offset = CAMEngine.get_curve_reference_offset(control_pts, interpolation_type, smoothness, reference_mode)
        
        return raw_z - ref_offset

    @staticmethod
    def get_curve_max_z(curve_params):
        if not curve_params or not curve_params.get("curve_enabled", False):
            return 0.0
        control_pts = curve_params.get("curve_control_points", [])
        interpolation_type = curve_params.get("curve_interpolation_type", "Smooth Spline")
        smoothness = curve_params.get("curve_smoothness", 50.0)
        reference_mode = curve_params.get("curve_reference_mode", "Lock Center Plane")
        
        sample_u = np.linspace(0.0, 1.0, 200)
        raw_z = CAMEngine.evaluate_curve(sample_u, control_pts, interpolation_type, smoothness)
        ref_offset = CAMEngine.get_curve_reference_offset(control_pts, interpolation_type, smoothness, reference_mode)
        comp_z = raw_z - ref_offset
        return float(np.max(comp_z))

    @staticmethod
    def get_tool_radius_at_z(z, tool_params, ttype):
        """
        Computes the physical tool radius (in mm) at a given local Z height above the tip.
        Handles flat, ball, tapered, V-bit, and holder profiles.
        """
        tip_dia = float(tool_params.get("tip_diameter", 3.0))
        max_dia = float(tool_params.get("max_diameter", 6.0))
        taper_angle = float(tool_params.get("taper_angle", 0.0))
        flute_len = float(tool_params.get("flute_length", tool_params.get("cutting_length", 15.0)))
        stickout = float(tool_params.get("stickout_length", tool_params.get("tool_length", 35.0)))
        neck_dia = float(tool_params.get("neck_diameter", max_dia))
        collet_dia = float(tool_params.get("collet_diameter", 15.0))
        holder_dia = float(tool_params.get("holder_diameter", 20.0))
        
        if z < flute_len:
            if ttype == "Flat End Mill":
                r = tip_dia / 2.0
            elif ttype == "Ball Nose":
                r_ball = float(tool_params.get("ball_radius", tip_dia / 2.0))
                if z <= r_ball:
                    r = np.sqrt(max(0.0, r_ball**2 - (r_ball - z)**2))
                else:
                    r = tip_dia / 2.0
            elif ttype == "V-Bit":
                r_tip = tip_dia / 2.0
                theta = np.radians(taper_angle / 2.0)
                r = r_tip + z * np.tan(theta)
            elif ttype == "Tapered Ball Nose":
                r_tip = float(tool_params.get("ball_radius", 1.5))
                theta = np.radians(taper_angle)
                r_tangent = r_tip * np.cos(theta)
                z_tangent = r_tip - r_tip * np.sin(theta)
                if z <= z_tangent:
                    r = np.sqrt(max(0.0, r_tip**2 - (r_tip - z)**2))
                else:
                    r = r_tangent + (z - z_tangent) * np.tan(theta)
            elif ttype == "Tapered End Mill":
                r_tip = tip_dia / 2.0
                theta = np.radians(taper_angle)
                r = r_tip + z * np.tan(theta)
            else:
                r = tip_dia / 2.0
            
            # Cap at max_diameter / 2
            r = min(r, max_dia / 2.0)
        elif z < stickout:
            r = neck_dia / 2.0
        else:
            # Holder / collet zone
            if z < stickout + 15.0:
                r = collet_dia / 2.0
            else:
                r = holder_dia / 2.0
                
        return r

    @staticmethod
    def compute_tool_profile_lut(tool_params, ttype, safe_margin):
        """
        Precomputes the inverse tool profile mapping r -> z_local (height above tip where radius is r).
        """
        stickout = float(tool_params.get("stickout_length", tool_params.get("tool_length", 35.0)))
        holder_len = float(tool_params.get("holder_length", 40.0))
        H_max = stickout + holder_len
        
        # Sane defaults if overall_length or other values are missing
        if H_max <= 0.0:
            H_max = 75.0
            
        z_grid = np.linspace(0.0, H_max, 1000)
        R_grid = np.array([CAMEngine.get_tool_radius_at_z(z, tool_params, ttype) for z in z_grid])
        
        # Effective radius includes safe clearance margin
        R_grid_eff = R_grid + safe_margin
        
        # Generate lookup table for r in [0, R_grid_eff[-1]]
        R_max_check = R_grid_eff[-1]
        r_samples = np.linspace(0.0, R_max_check, 500)
        z_offsets = []
        
        for r in r_samples:
            # Find the first height where effective tool radius is >= r
            mask = R_grid_eff >= r
            if np.any(mask):
                z_offsets.append(z_grid[np.argmax(mask)])
            else:
                z_offsets.append(H_max)
                
        return r_samples, np.array(z_offsets)

    @staticmethod
    def generate_optimized_search_grid(r_cutter, r_neck, r_max, safe_margin):
        """
        Generates a non-uniform multi-resolution search grid of (dx, dy, r) points.
        Fine-grained near the cutter tip, medium for neck, coarse for holder/collet.
        """
        # Define step sizes
        step_fine = max(0.1, min(0.5, r_cutter / 8.0))
        step_med = max(0.5, min(1.0, r_neck / 8.0))
        step_coarse = max(1.0, min(2.5, r_max / 8.0))
        
        grid_points = []
        
        # 1. Fine grid for tip zone
        r_fine_limit = r_cutter + safe_margin
        fine_range = np.arange(-r_fine_limit, r_fine_limit + step_fine, step_fine)
        dx_f, dy_f = np.meshgrid(fine_range, fine_range)
        dx_f = dx_f.flatten()
        dy_f = dy_f.flatten()
        r_f = np.sqrt(dx_f**2 + dy_f**2)
        mask_f = r_f <= r_fine_limit
        for x, y, r in zip(dx_f[mask_f], dy_f[mask_f], r_f[mask_f]):
            grid_points.append((x, y, r))
            
        # 2. Medium grid for neck zone
        if r_neck > r_cutter:
            r_med_limit = r_neck + safe_margin
            med_range = np.arange(-r_med_limit, r_med_limit + step_med, step_med)
            dx_m, dy_m = np.meshgrid(med_range, med_range)
            dx_m = dx_m.flatten()
            dy_m = dy_m.flatten()
            r_m = np.sqrt(dx_m**2 + dy_m**2)
            mask_m = (r_m > r_fine_limit) & (r_m <= r_med_limit)
            for x, y, r in zip(dx_m[mask_m], dy_m[mask_m], r_m[mask_m]):
                grid_points.append((x, y, r))
                
        # 3. Coarse grid for holder/collet zone
        if r_max > r_neck:
            r_max_limit = r_max + safe_margin
            coarse_range = np.arange(-r_max_limit, r_max_limit + step_coarse, step_coarse)
            dx_c, dy_c = np.meshgrid(coarse_range, coarse_range)
            dx_c = dx_c.flatten()
            dy_c = dy_c.flatten()
            r_c = np.sqrt(dx_c**2 + dy_c**2)
            mask_c = (r_c > r_med_limit) & (r_c <= r_max_limit)
            for x, y, r in zip(dx_c[mask_c], dy_c[mask_c], r_c[mask_c]):
                grid_points.append((x, y, r))
                
        return np.array(grid_points)

    @staticmethod
    def apply_max_wall_angle_filter(points, max_wall_angle_deg):
        """
        Limits the maximum slope of the toolpath trajectory to respect the tool's maximum wall angle limit.
        Traverses the path forward and backward to smooth steep drops and rises.
        """
        if len(points) < 2 or max_wall_angle_deg <= 0.0 or max_wall_angle_deg >= 90.0:
            return points
            
        filtered = np.copy(points)
        max_slope = np.tan(np.radians(max_wall_angle_deg))
        
        # Forward pass: limit sudden drops
        for i in range(1, len(filtered)):
            dx = filtered[i, 0] - filtered[i-1, 0]
            dy = filtered[i, 1] - filtered[i-1, 1]
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0.0:
                filtered[i, 2] = max(filtered[i, 2], filtered[i-1, 2] - dist * max_slope)
                
        # Backward pass: limit sudden rises
        for i in range(len(filtered) - 2, -1, -1):
            dx = filtered[i, 0] - filtered[i+1, 0]
            dy = filtered[i, 1] - filtered[i+1, 1]
            dist = np.sqrt(dx**2 + dy**2)
            if dist > 0.0:
                filtered[i, 2] = max(filtered[i, 2], filtered[i+1, 2] - dist * max_slope)
                
        return filtered
