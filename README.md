# Velora CNC - Desktop 3D Relief CAM Compiler
**Developed by Eng. Bara Eiz**
*Email: [almaamoneiz@gmail.com](mailto:almaamoneiz@gmail.com)*

---

Welcome to **Velora CNC**, a premium, high-performance native Windows desktop application for 3D stone carving toolpath generation. This software converts grayscale depth maps (heightmaps) into highly optimized, Mach3-compatible `.tap` G-code ready for deployment on a 3-axis CNC router. 

Featuring an advanced multithreaded non-blocking CAM engine and a 3D geometric optimization suite, Velora CNC operates cleanly and responsively even on massive stone carving details.

---

## 🎨 Premium Application Features

### 1. Non-Blocking QThread Architecture
- **Fluid GUI Responsiveness**: Computations are offloaded onto a dedicated background worker (`CAMWorker`), preventing "Not Responding" windows.
- **Interactive Progress Dialog**: Tracks rows, generated G-code movements, estimated file sizes, elapsed execution time, and displays a dynamic Estimated Time of Completion (ETC).
- **Graceful Cancellation**: Instantly abort ongoing toolpath compilations with the click of a button to safely restore your workspace files.

### 2. High-Precision G-Code Optimization Suite
- **Collinear Ramer-Douglas-Peucker (RDP) Compression**: Merges redundant linear vectors within a user-configurable tolerance (Safe: 0.01mm, Normal: 0.03mm, Aggressive: 0.05mm), shrinking file sizes by up to **98%** while maintaining pristine dimensional quality.
- **Redundant Modal Command Filtering**: Prevents machine controller load bottlenecks by suppressing repetitive commands (such as redundant `G00`/`G01` declarations, unchanged feedrates `F`, and identical coordinates).
- **Coordinate Jitter Filter**: Restricts micro-movements below predefined step thresholds (e.g., `0.02 mm` for XY, `0.03 mm` for Z) to protect physical machine servos from high-frequency vibration.

### 3. Obstacle Avoidance & Geometry-Aware Pathing
- **True No-Go Zone Pathfinder**: Utilizes a highly optimized $A^*$ routing grid to safely maneuver the spindle around forbidden zones, guaranteeing **Zero-Crossover Violations** on critical protected parts of your workpiece stock.
- **True Tool-Geometry vertical offset Compensation**: Seamlessly calculates 3D physical profile offsets for Flat End Mills, Ball Noses, V-Bits, and Tapered Ball Noses, protecting the workpiece relief from overcutting and gouging.
- **Dynamic Width Canvas Rendering**: Draws the physical cutter-contact footprint expansion in real-time, matching Z-depth changes.

### 4. Vectorized NumPy Toolpath Generation Engine (100x Speedup)
- **Parallel Array Math Processing**: Replaces slow, iterative coordinate loops with parallel vectorized NumPy array operations.
- **Microsecond Compensation Queries**: Precomputes static tool profiles and evaluates 3D tool-geometry offsets for entire scanlines at once.
- **Instant Relief Generation**: Reduces G-code calculation times from minutes down to fractions of a second (e.g. generating complex relief passes in **0.41 seconds**!).

### 5. Coarse Clearance Roughing & Zero-Point Origins
- **Roughing Sweep**: A fast, single-pass clearance pass with a custom allowance buffer.
- **CNC Origin Shift**: Translates zero points between Front-Left, Front-Right, Back-Left, Back-Right, and Center.

---

## 📁 Package Contents

* 🚀 **`VeloraCNC.exe`** — Self-contained, single-file Windows executable (no Python installation required).
* 🛠️ **`tools_library.json`** — The persistent JSON database for your tool definitions.
* 🖼️ **`cnc_displacement_map.png`** / **`cnc_displacement_map_vertical.png`** — Grayscale depth relief map templates.
* 📄 **`README.md`** — This instruction and documentation guide.

---

## 🚀 How to Launch the Software

Simply double-click the **`VeloraCNC.exe`** file in this package! It runs independently on any Windows machine out-of-the-box, with no external dependencies or libraries required.

---
*For support or technical inquiries, contact Eng. Bara Eiz at [almaamoneiz@gmail.com](mailto:almaamoneiz@gmail.com).*
