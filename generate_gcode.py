import os
import numpy as np
from PIL import Image

# ==============================================================================
# CONFIGURATION PARAMETERS (High-Performance Stone Relief Carving)
# ==============================================================================

# Input Image Path (Vertical Technical Heightmap)
INPUT_IMAGE_PATH = r"c:\Users\pc\Desktop\cnc\cnc_displacement_map_vertical.png"

# Physical Dimensions of your Workpiece (in mm)
STOCK_X = 300.0   # Width along X-axis
STOCK_Y = 1000.0  # Length along Y-axis
MAX_DEPTH = 25.0  # Maximum depth of carving (Z excursion from 0 to -25 mm)

# ------------------------------------------------------------------------------
# 1. ROUGHING PASS PARAMETERS
# ------------------------------------------------------------------------------
GENERATE_ROUGHING = True
OUTPUT_ROUGHING_PATH = r"c:\Users\pc\Desktop\cnc\cnc_roughing_pass_optimized.tap"
ROUGH_TOOL_DIAMETER = 6.0        # Flat-end mill diameter for material removal
ROUGH_STEPOVER = 3.0             # 50% tool diameter stepover for stone
ROUGH_RESOLUTION_X = 1.0         # Resolution along X (mm)
ROUGH_FEED_RATE = 3000.0         # XY roughing feedrate (mm/min)
ROUGH_PLUNGE_RATE = 800.0        # Plunge rate (mm/min)
ROUGH_ALLOWANCE = 1.0            # Finishing allowance (material left in mm)
ROUGH_Z_STEPS = [-5.0, -10.0, -15.0, -20.0, -25.0]  # 5mm stepdown layers

# ------------------------------------------------------------------------------
# 2. FINISHING PASS PARAMETERS (Tapered Ball Nose End Mill)
# ------------------------------------------------------------------------------
GENERATE_FINISHING = True
OUTPUT_FINISHING_PATH = r"c:\Users\pc\Desktop\cnc\cnc_finishing_pass_optimized.tap"
FINISH_TOOL_TIP_DIAMETER = 3.0   # 3.0 mm tip diameter
FINISH_BALL_RADIUS = 1.5         # 1.5 mm ball radius
FINISH_NOMINAL_STEPOVER = 1.0    # Nominal finishing stepover target (mm)
FINISH_MIN_STEPOVER = 0.4        # Minimum stepover in highly steep/detailed areas (mm)
FINISH_MAX_STEPOVER = 1.2        # Maximum stepover in flat areas (mm)
FINISH_RESOLUTION_X = 0.5        # Base horizontal step size along X (mm)
FINISH_FEED_RATE = 3000.0        # XY finishing feedrate (mm/min)
FINISH_Z_FEED_RATE = 1500.0      # Z vertical feedrate (mm/min)
FINISH_PLUNGE_RATE = 800.0       # Plunge feedrate (mm/min)
FINISH_TOLERANCE = 0.015         # 3D RDP geometric compression tolerance (mm)

# ------------------------------------------------------------------------------
# 3. COMMON G-CODE PARAMETERS
# ------------------------------------------------------------------------------
SAFE_Z = 20.0          # Safe travel height above stock (mm)
SPINDLE_SPEED = 24000  # Spindle Speed (RPM)
PRESERVE_ASPECT_RATIO = True  # Center carving with uniform scale
GRID_RES = 0.5         # High-resolution grid cell size (mm) for CAM calculation

# ==============================================================================
# HEIGHTMAP PROCESSING & BOUNDING BOX DETECTION
# ==============================================================================

print("Loading heightmap image...")
if not os.path.exists(INPUT_IMAGE_PATH):
    raise FileNotFoundError(f"Input image not found at {INPUT_IMAGE_PATH}")

img = Image.open(INPUT_IMAGE_PATH).convert("L")
arr = np.array(img, dtype=np.float32)
img_h, img_w = arr.shape

# Detect carving bounding box (non-black area) using threshold of 15 to filter noise
print("Detecting carving boundaries...")
non_black = np.where(arr > 15)
if len(non_black[0]) > 0:
    min_y, max_y = np.min(non_black[0]), np.max(non_black[0])
    min_x, max_x = np.min(non_black[1]), np.max(non_black[1])
    carving_w = max_x - min_x + 1
    carving_h = max_y - min_y + 1
    print(f"Carving detected at X:[{min_x}, {max_x}] (W:{carving_w}px), Y:[{min_y}, {max_y}] (H:{carving_h}px)")
else:
    min_y, max_y, min_x, max_x = 0, img_h - 1, 0, img_w - 1
    carving_w, carving_h = img_w, img_h
    print("Warning: No carving boundaries detected. Processing entire image canvas.")

# Calculate uniform scaling and offsets
if PRESERVE_ASPECT_RATIO:
    scale_x = STOCK_X / carving_w
    scale_y = STOCK_Y / carving_h
    scale = min(scale_x, scale_y)
    
    scaled_w = carving_w * scale
    scaled_h = carving_h * scale
    
    offset_x = (STOCK_X - scaled_w) / 2.0
    offset_y = (STOCK_Y - scaled_h) / 2.0
    
    print(f"Applying UNIFORM scale factor of {scale:.4f} mm/pixel:")
    print(f" - Scaled Carving Dimensions: {scaled_w:.2f} mm x {scaled_h:.2f} mm")
    print(f" - Centering Offset: X={offset_x:.2f} mm, Y={offset_y:.2f} mm")
else:
    scale = 1.0
    scaled_w = STOCK_X
    scaled_h = STOCK_Y
    offset_x = 0.0
    offset_y = 0.0
    print(f"Applying NON-UNIFORM scale (stretched to fill {STOCK_X}mm x {STOCK_Y}mm):")

# ==============================================================================
# VECTORIZED PHYSICAL SURFACE GENERATION
# ==============================================================================

print("\nGenerating physical Z-surface grid...")
Nx = int(STOCK_X / GRID_RES) + 1
Ny = int(STOCK_Y / GRID_RES) + 1
print(f"Grid size: {Nx} x {Ny} ({Nx * Ny} nodes at {GRID_RES}mm spacing)")

x_grid = np.linspace(0.0, STOCK_X, Nx)
y_grid = np.linspace(0.0, STOCK_Y, Ny)
X_mesh, Y_mesh = np.meshgrid(x_grid, y_grid)

# Map physical coordinates back to image pixel coordinates
if PRESERVE_ASPECT_RATIO:
    cx = X_mesh - offset_x
    cy = Y_mesh - offset_y
    in_bounds = (cx >= 0) & (cx < scaled_w) & (cy >= 0) & (cy < scaled_h)
    
    px = min_x + (cx / scaled_w) * carving_w
    py = max_y - (cy / scaled_h) * carving_h
else:
    px = (X_mesh / STOCK_X) * (img_w - 1)
    py = (img_h - 1) - (Y_mesh / STOCK_Y) * (img_h - 1)
    in_bounds = np.ones_like(X_mesh, dtype=bool)

# Clamp coordinates safely
px = np.clip(px, 0.0, float(img_w - 1))
py = np.clip(py, 0.0, float(img_h - 1))

# Vectorized Bilinear interpolation from image pixels
x0 = np.floor(px).astype(np.int32)
x1 = np.minimum(img_w - 1, x0 + 1)
y0 = np.floor(py).astype(np.int32)
y1 = np.minimum(img_h - 1, y0 + 1)

dx = px - x0
dy = py - y0

v00 = arr[y0, x0]
v10 = arr[y0, x1]
v01 = arr[y1, x0]
v11 = arr[y1, x1]

val = (1.0 - dx) * (1.0 - dy) * v00 + dx * (1.0 - dy) * v10 + (1.0 - dx) * dy * v01 + dx * dy * v11
Z_surface = -MAX_DEPTH * (1.0 - val / 255.0)

# Make out-of-bounds flat background at the deepest point
Z_surface[~in_bounds] = -MAX_DEPTH

# ==============================================================================
# 3D spherical DILATION (Tool Nose Radius Compensation)
# ==============================================================================

R = FINISH_BALL_RADIUS
N_R = int(np.ceil(R / GRID_RES))

print(f"\nApplying 3D Tool Nose Compensation (Ball Radius R={R} mm)...")
offsets = []
for di in range(-N_R, N_R + 1):
    for dj in range(-N_R, N_R + 1):
        dist = np.sqrt((di * GRID_RES)**2 + (dj * GRID_RES)**2)
        if dist <= R:
            # Spherical Z offset: height = sqrt(R^2 - dist^2) - R
            h_offset = np.sqrt(R**2 - dist**2) - R
            offsets.append((di, dj, h_offset))

Z_compensated = np.full_like(Z_surface, -9999.0)

# Run fast morphological dilation shift loops
for di, dj, h_offset in offsets:
    shifted = np.pad(Z_surface, ((max(0, -di), max(0, di)), (max(0, -dj), max(0, dj))), 
                     mode='constant', constant_values=-MAX_DEPTH)
    start_y = max(0, -di)
    start_x = max(0, -dj)
    shifted_cropped = shifted[start_y:start_y+Ny, start_x:start_x+Nx]
    Z_compensated = np.maximum(Z_compensated, shifted_cropped + h_offset)

# ==============================================================================
# SLOPE GRADIENT COMPUTATION
# ==============================================================================

print("\nComputing slope gradient map for adaptive stepover...")
dy_grad, dx_grad = np.gradient(Z_surface, GRID_RES)
slope_map = np.sqrt(dx_grad**2 + dy_grad**2)

# ==============================================================================
# FAST GRID INTERPOLATOR
# ==============================================================================

def get_interpolated_z(x, y, grid):
    """
    Interpolates Z coordinate from physical grid (Nx, Ny) corresponding to (STOCK_X, STOCK_Y)
    """
    px = (x / STOCK_X) * (Nx - 1)
    py = (y / STOCK_Y) * (Ny - 1)
    
    px = max(0.0, min(float(Nx - 1), px))
    py = max(0.0, min(float(Ny - 1), py))
    
    x0 = int(np.floor(px))
    x1 = min(Nx - 1, x0 + 1)
    y0 = int(np.floor(py))
    y1 = min(Ny - 1, y0 + 1)
    
    dx = px - x0
    dy = py - y0
    
    v00 = grid[y0, x0]
    v10 = grid[y0, x1]
    v01 = grid[y1, x0]
    v11 = grid[y1, x1]
    
    return (1.0 - dx) * (1.0 - dy) * v00 + dx * (1.0 - dy) * v10 + (1.0 - dx) * dy * v01 + dx * dy * v11

# ==============================================================================
# 3D RAMER-DOUGLAS-PEUCKER (RDP) COMPRESSION FILTER
# ==============================================================================

def compress_path_3d(points, tolerance):
    """
    Ramer-Douglas-Peucker algorithm for 3D trajectory compression.
    points: numpy array of shape (N, 3) where columns are (X, Y, Z)
    tolerance: geometric deviation threshold (epsilon) in mm
    """
    if len(points) < 3:
        return points
        
    start = points[0]
    end = points[-1]
    
    # Vector from start to end
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)
    
    if line_len < 1e-8:
        # Segment is essentially a point
        dists = np.linalg.norm(points[1:-1] - start, axis=1)
    else:
        # Distance of each point to the 3D line AB
        t = np.dot(points[1:-1] - start, line_vec) / (line_len ** 2)
        t = np.clip(t, 0.0, 1.0)
        proj = start + t[:, np.newaxis] * line_vec
        dists = np.linalg.norm(points[1:-1] - proj, axis=1)
        
    if len(dists) == 0:
        return points
        
    max_idx = np.argmax(dists)
    max_dist = dists[max_idx]
    
    if max_dist > tolerance:
        # Split recursively
        split_idx = max_idx + 1
        left = compress_path_3d(points[:split_idx+1], tolerance)
        right = compress_path_3d(points[split_idx:], tolerance)
        return np.vstack((left[:-1], right))
    else:
        return np.array([start, end])

# ==============================================================================
# ROUGHING PASS GENERATION
# ==============================================================================

if GENERATE_ROUGHING:
    print("\n--- Generating Roughing Toolpath (Z-Slice) ---")
    rough_lines = []
    
    # Write Mach3-compatible Header
    rough_lines.append("%")
    rough_lines.append("(CNC RELIEF ROUGHING PASS - MULTI-LAYER Z-SLICE)")
    rough_lines.append(f"(Workpiece Dimensions: X={STOCK_X} mm, Y={STOCK_Y} mm, Depth={MAX_DEPTH} mm)")
    rough_lines.append(f"(Tool: {ROUGH_TOOL_DIAMETER} mm Flat Endmill)")
    rough_lines.append(f"(Z Stepdown: 5 mm layers)")
    rough_lines.append(f"(Finishing Stock Allowance: {ROUGH_ALLOWANCE} mm)")
    rough_lines.append("G90 (Absolute coordinates)")
    rough_lines.append("G21 (Metric units - mm)")
    rough_lines.append("G17 (XY plane)")
    rough_lines.append("G64 (Continuous Velocity Mode)")
    rough_lines.append(f"G00 Z{SAFE_Z:.3f} (Move to safe Z height)")
    rough_lines.append(f"M03 S{SPINDLE_SPEED} (Start Spindle)")
    rough_lines.append("G04 P3.000 (Dwell 3s for warmup)")
    
    y_coords = np.arange(0.0, STOCK_Y + ROUGH_STEPOVER, ROUGH_STEPOVER)
    x_coords_forward = np.arange(0.0, STOCK_X + ROUGH_RESOLUTION_X, ROUGH_RESOLUTION_X)
    x_coords_reverse = x_coords_forward[::-1]
    
    rough_total = 0
    rough_saved = 0
    
    # Slice layer by layer
    for slice_idx, target_z_limit in enumerate(ROUGH_Z_STEPS):
        print(f"Processing Roughing Layer {slice_idx + 1}/{len(ROUGH_Z_STEPS)}: Z = {target_z_limit:.2f} mm")
        rough_lines.append(f"(--- LAYER Z-SLICE {slice_idx + 1}: Z = {target_z_limit:.2f} mm ---)")
        
        for i, y in enumerate(y_coords):
            forward = (i % 2 == 0)
            x_line = x_coords_forward if forward else x_coords_reverse
            
            raw_points = []
            for x in x_line:
                # Interpolate surface height (uncompensated for flat endmill roughing)
                z_actual = get_interpolated_z(x, y, Z_surface)
                # Apply 1.0mm allowance
                z_target = z_actual + ROUGH_ALLOWANCE
                # Clamp to layer stepdown limit
                z_rough = max(z_target, target_z_limit)
                # Clamp to top of workpiece
                z_rough = min(0.0, z_rough)
                
                raw_points.append((x, y, z_rough))
                rough_total += 1
            
            # Compress roughing moves (tolerance 0.05 mm is extremely safe for roughing)
            compressed = compress_path_3d(np.array(raw_points), 0.05)
            rough_saved += (len(raw_points) - len(compressed))
            
            # Write raster G-code moves
            for idx, (x, y, z) in enumerate(compressed):
                if slice_idx == 0 and i == 0 and idx == 0:
                    rough_lines.append(f"G00 X{x:.3f} Y{y:.3f} (Rapid to start)")
                    rough_lines.append(f"G01 Z{z:.3f} F{ROUGH_PLUNGE_RATE:.0f} (Plunge)")
                elif idx == 0:
                    rough_lines.append(f"G01 X{x:.3f} Y{y:.3f} Z{z:.3f} F{ROUGH_FEED_RATE:.0f}")
                else:
                    rough_lines.append(f"G01 X{x:.3f} Z{z:.3f} F{ROUGH_FEED_RATE:.0f}")
                    
        # Retract to safe height at the end of each slice layer
        rough_lines.append(f"G00 Z{SAFE_Z:.3f} (Retract between layers)")
        
    # Write Footer
    rough_lines.append(f"G00 Z{SAFE_Z:.3f}")
    rough_lines.append("M05 (Stop Spindle)")
    rough_lines.append("G00 X0.000 Y0.000 (Return Home)")
    rough_lines.append("M30 (Program End)")
    rough_lines.append("%")
    
    with open(OUTPUT_ROUGHING_PATH, "w") as f:
        f.write("\n".join(rough_lines))
    print(f"Roughing G-code written: {OUTPUT_ROUGHING_PATH} ({len(rough_lines)} lines)")
    print(f"Roughing points simplified: {rough_saved}/{rough_total} ({ (rough_saved/rough_total)*100:.1f}% reduction)")

# ==============================================================================
# ADAPTIVE HYBRID SCALLOP FINISHING PASS GENERATION
# ==============================================================================

if GENERATE_FINISHING:
    print("\n--- Generating Adaptive Hybrid Raster Finishing Toolpath ---")
    finish_lines = []
    
    # Write Mach3-compatible Header
    finish_lines.append("%")
    finish_lines.append("(CNC RELIEF FINISHING PASS - ADAPTIVE HYBRID SCALLOP)")
    finish_lines.append(f"(Workpiece Dimensions: X={STOCK_X} mm, Y={STOCK_Y} mm, Depth={MAX_DEPTH} mm)")
    finish_lines.append(f"(Tool: {FINISH_TOOL_TIP_DIAMETER} mm Tapered Ball Nose, Radius={FINISH_BALL_RADIUS} mm)")
    finish_lines.append(f"(Strategy: Adaptive Slope-Aware stepover: {FINISH_MIN_STEPOVER} - {FINISH_MAX_STEPOVER} mm)")
    finish_lines.append("G90 (Absolute coordinates)")
    finish_lines.append("G21 (Metric units - mm)")
    finish_lines.append("G17 (XY plane)")
    finish_lines.append("G64 (Continuous Velocity Mode)")
    finish_lines.append(f"G00 Z{SAFE_Z:.3f} (Move to safe Z height)")
    finish_lines.append(f"M03 S{SPINDLE_SPEED} (Start Spindle)")
    finish_lines.append("G04 P3.000 (Dwell 3s for warmup)")
    
    # Dynamic scan line loop
    y = 0.0
    line_idx = 0
    finish_total = 0
    finish_saved = 0
    
    # Base scan coordinates
    x_coords_forward = np.arange(0.0, STOCK_X + FINISH_RESOLUTION_X, FINISH_RESOLUTION_X)
    x_coords_reverse = x_coords_forward[::-1]
    
    while y <= STOCK_Y:
        # Get grid row index corresponding to current y
        j = int(round(y / GRID_RES))
        j = max(0, min(Ny - 1, j))
        
        # Calculate row slope to adjust stepover (90th percentile of slope along this line)
        row_slope = np.percentile(slope_map[j, :], 90)
        
        # Smoothly map slope to stepover using tanh
        stepover_range = FINISH_MAX_STEPOVER - FINISH_MIN_STEPOVER
        k_slope = 1.2  # Sensitivity to details/slopes
        dy = FINISH_MAX_STEPOVER - stepover_range * np.tanh(k_slope * row_slope)
        dy = np.clip(dy, FINISH_MIN_STEPOVER, FINISH_MAX_STEPOVER)
        
        # Alternating direction (zig-zag scan)
        forward = (line_idx % 2 == 0)
        x_line = x_coords_forward if forward else x_coords_reverse
        
        raw_points = []
        for x in x_line:
            # Interpolate from 3D radius compensated grid
            z = get_interpolated_z(x, y, Z_compensated)
            raw_points.append((x, y, z))
            finish_total += 1
            
        # Compress the scan line using 3D RDP
        compressed = compress_path_3d(np.array(raw_points), FINISH_TOLERANCE)
        finish_saved += (len(raw_points) - len(compressed))
        
        # Write moves to G-code
        for idx, (cx, cy, cz) in enumerate(compressed):
            if line_idx == 0 and idx == 0:
                finish_lines.append(f"G00 X{cx:.3f} Y{cy:.3f} (Rapid to start)")
                finish_lines.append(f"G01 Z{cz:.3f} F{FINISH_PLUNGE_RATE:.0f} (Plunge)")
            elif idx == 0:
                # Move to next line start
                finish_lines.append(f"G01 X{cx:.3f} Y{cy:.3f} Z{cz:.3f} F{FINISH_FEED_RATE:.0f}")
            else:
                # Linear machining stroke (X and Z)
                finish_lines.append(f"G01 X{cx:.3f} Z{cz:.3f} F{FINISH_FEED_RATE:.0f}")
                
        # Advance to next scan line adaptively
        if abs(y - STOCK_Y) < 1e-5:
            break
        y += dy
        if y > STOCK_Y:
            y = STOCK_Y  # Force exact boundary finish
        line_idx += 1
        
        if line_idx % 100 == 0 or y == STOCK_Y:
            print(f"Machining Progress: Y = {y:.1f} mm / {STOCK_Y:.1f} mm (Stepover={dy:.3f} mm)")

    # Write Footer
    finish_lines.append(f"G00 Z{SAFE_Z:.3f}")
    finish_lines.append("M05 (Stop Spindle)")
    finish_lines.append("G00 X0.000 Y0.000 (Return Home)")
    finish_lines.append("M30 (Program End)")
    finish_lines.append("%")
    
    with open(OUTPUT_FINISHING_PATH, "w") as f:
        f.write("\n".join(finish_lines))
        
    print(f"\nFinishing G-code written: {OUTPUT_FINISHING_PATH}")
    print(f"Finishing points simplified: {finish_saved}/{finish_total} ({ (finish_saved/finish_total)*100:.1f}% reduction)")
    print(f"Total finishing G-code lines: {len(finish_lines)}")
