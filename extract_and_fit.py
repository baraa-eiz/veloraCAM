import cv2
import numpy as np
import os

def main():
    # Paths
    workspace_dir = r"c:\Users\pc\Desktop\cnc"
    img1_path = os.path.join(workspace_dir, "image1_source.jpg")
    img2_path = os.path.join(workspace_dir, "image2_target.jpg")
    
    print("Loading source and target images...")
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)
    
    if img1 is None or img2 is None:
        print("Error: Could not load input images.")
        return
        
    # 1. Crop fireplace ornament using calibrated coordinates
    # Scale: 0.9400, X: [135, 450], Y: [81, 574]
    crop_x1, crop_y1 = 135, 81
    crop_w, crop_h = 315, 493
    img_fire_crop = img1[crop_y1:crop_y1+crop_h, crop_x1:crop_x1+crop_w]
    cv2.imwrite(os.path.join(workspace_dir, "fireplace_crop.png"), img_fire_crop)
    print(f"Fireplace ornament cropped. Size: {img_fire_crop.shape}")
    
    # 2. Extract target mask from Image 2 (SolidWorks outline)
    # The blue shape is the panel outline
    hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(hsv2, np.array([90, 20, 50]), np.array([130, 255, 255]))
    
    # Find the largest blue contour
    contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("Error: No target shape found in Image 2.")
        return
    c2 = max(contours, key=cv2.contourArea)
    x2, y2, w2, h2 = cv2.boundingRect(c2)
    mask2_crop = blue_mask[y2:y2+h2, x2:x2+w2]
    
    # 3. Define target high-resolution dimensions (1000x1600 for W:500, H:800 ratio)
    W_target, H_target = 1000, 1600
    print(f"Target dimensions: {W_target}x{H_target}")
    
    # 4. Resize ornament and mask to target dimensions
    # Using high-quality CUBIC interpolation for the ornament photo
    ornament_resized = cv2.resize(img_fire_crop, (W_target, H_target), interpolation=cv2.INTER_CUBIC)
    # Using NEAREST neighbor for the binary mask to preserve sharp edges
    mask_resized = cv2.resize(mask2_crop, (W_target, H_target), interpolation=cv2.INTER_NEAREST)
    
    # 5. Generate Fitted Color Ornament (Option B)
    # A. RGBA version with transparent background
    b_ch, g_ch, r_ch = cv2.split(ornament_resized)
    alpha_ch = mask_resized.copy()
    fitted_color_rgba = cv2.merge([b_ch, g_ch, r_ch, alpha_ch])
    cv2.imwrite(os.path.join(workspace_dir, "cnc_fitted_ornament_color_rgba.png"), fitted_color_rgba)
    
    # B. RGB version with black background
    fitted_color_black_bg = cv2.bitwise_and(ornament_resized, ornament_resized, mask=mask_resized)
    cv2.imwrite(os.path.join(workspace_dir, "cnc_fitted_ornament_color_black_bg.png"), fitted_color_black_bg)
    
    # 6. Generate Grayscale Depth Map / Displacement Map (Option A)
    # Convert ornament to grayscale
    gray_ornament = cv2.cvtColor(ornament_resized, cv2.COLOR_BGR2GRAY)
    
    # Mask grayscale
    fitted_gray = cv2.bitwise_and(gray_ornament, gray_ornament, mask=mask_resized)
    cv2.imwrite(os.path.join(workspace_dir, "cnc_fitted_ornament_gray.png"), fitted_gray)
    
    # Process for CNC Depth Map
    # - Smooth out small high-frequency photographic noise (using Bilateral Filter to preserve sharp edges)
    # - Correct for lighting gradients using morphological top-hat or black-hat operation to flatten base plane
    smooth_gray = cv2.bilateralFilter(gray_ornament, d=9, sigmaColor=75, sigmaSpace=75)
    
    # Morphological opening with a large kernel to estimate the background lighting gradient
    kernel_size = 81  # large kernel for gradient estimation
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    background_estimate = cv2.morphologyEx(smooth_gray, cv2.MORPH_OPEN, kernel)
    
    # Subtract background to flatten base plane
    flattened = cv2.subtract(smooth_gray, background_estimate)
    
    # Equalize and scale to full 0-255 range
    normalized_depth = cv2.normalize(flattened, None, 0, 255, cv2.NORM_MINMAX)
    
    # Apply target shape mask: pixels outside the panel must be exactly 0 (base plane)
    cnc_depth_map = cv2.bitwise_and(normalized_depth, normalized_depth, mask=mask_resized)
    
    # Save the CNC-ready depth map
    cv2.imwrite(os.path.join(workspace_dir, "cnc_fitted_ornament_depth.png"), cnc_depth_map)
    
    # Also save to Desktop for easy access
    desktop_dir = r"c:\Users\pc\Desktop"
    cv2.imwrite(os.path.join(desktop_dir, "cnc_fitted_ornament_color.png"), fitted_color_black_bg)
    cv2.imwrite(os.path.join(desktop_dir, "cnc_fitted_ornament_depth.png"), cnc_depth_map)
    
    print("\nExtraction and fitting process completed successfully!")
    print("Files saved to c:\\Users\\pc\\Desktop\\cnc and c:\\Users\\pc\\Desktop:")
    print("  - cnc_fitted_ornament_color_rgba.png (Transparent background color panel)")
    print("  - cnc_fitted_ornament_color_black_bg.png (Black background color panel)")
    print("  - cnc_fitted_ornament_gray.png (Grayscale masked panel)")
    print("  - cnc_fitted_ornament_depth.png (CNC-ready grayscale displacement depth map)")

if __name__ == "__main__":
    main()
