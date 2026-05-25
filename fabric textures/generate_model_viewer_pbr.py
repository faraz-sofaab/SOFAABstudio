import cv2
import numpy as np
import os
import glob
import argparse

def make_seamless(img, feather_ratio=0.3):
    """
    Makes an image seamlessly tileable by blending its edges with a shifted version of itself.
    feather_ratio (0.0 to 1.0) controls how much of the image is used to blend the seams.
    """
    h, w = img.shape[:2]
    # Shift the image so the original edges are now in the center (forming a cross seam)
    # The new edges of offset_img are perfectly tileable.
    offset_img = np.roll(img, (h//2, w//2), axis=(0, 1))
    
    # Create a 2D mask that is 1 in the center and 0 at the edges.
    def blend_window(size, feather):
        window = np.ones(size, dtype=np.float32)
        f_pixels = int(size * feather / 2)
        if f_pixels > 0:
            # Smooth step transition (cosine wave) for better blending
            gradient = (1 - np.cos(np.linspace(0, np.pi, f_pixels))) / 2
            window[:f_pixels] = gradient
            window[-f_pixels:] = gradient[::-1]
        return window
        
    mask_x = blend_window(w, feather_ratio)
    mask_y = blend_window(h, feather_ratio)
    mask = np.outer(mask_y, mask_x)
    
    if len(img.shape) == 3:
        mask = mask[:, :, np.newaxis]
        
    # Blend: Use the original image in the center (hiding the offset_img's seams)
    # and use the offset_img at the edges (which are perfectly tileable).
    result = img.astype(np.float32) * mask + offset_img.astype(np.float32) * (1 - mask)
    return result.astype(np.uint8)

def process_texture(image_path, output_dir, resolution=2048):
    print(f"\nProcessing: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error loading image: {image_path}")
        return

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    # 1. Resize/Crop to a Square for 3D textures
    # 2400 DPI scans can be massive. We extract the largest central square, then resize to target resolution (e.g. 2048x2048)
    h, w = img.shape[:2]
    min_dim = min(h, w)
    start_x = (w - min_dim) // 2
    start_y = (h - min_dim) // 2
    img_square = img[start_y:start_y+min_dim, start_x:start_x+min_dim]
    
    print(f"  -> Cropped center square. Resizing to {resolution}x{resolution} for <model-viewer>...")
    img_resized = cv2.resize(img_square, (resolution, resolution), interpolation=cv2.INTER_AREA)

    # 2. Make it Seamless
    print("  -> Generating seamless tileable edges...")
    seamless_albedo = make_seamless(img_resized, feather_ratio=0.3)
    
    # Optional slight denoise to clean up the scan
    albedo = cv2.bilateralFilter(seamless_albedo, 9, 75, 75)
    
    # Convert to grayscale for height calculations
    gray = cv2.cvtColor(seamless_albedo, cv2.COLOR_BGR2GRAY)

    # 3. Generate Normal Map (Bumpiness)
    print("  -> Calculating Normal map...")
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    strength = 2.0 
    normal_x = (sobel_x * strength)
    normal_y = (sobel_y * strength)
    normal_z = np.full(gray.shape, 255.0)

    # OpenCV uses BGR. RGB normal map format maps to: R=X, G=Y, B=Z
    # So for OpenCV saving, we need B=Z, G=Y, R=X
    normal_map = np.stack([normal_z, normal_y, normal_x], axis=-1)
    norm = np.linalg.norm(normal_map, axis=-1, keepdims=True)
    norm[norm == 0] = 1 
    normal_map = normal_map / norm
    normal_map = ((normal_map + 1) * 127.5).astype(np.uint8)

    # 4. Generate Roughness Map
    # Fabric is rough. Dark areas in grayscale are usually crevices (even rougher or shadowing).
    # We tweak levels to be generally bright.
    roughness = cv2.normalize(gray, None, alpha=150, beta=255, norm_type=cv2.NORM_MINMAX)

    # 5. Generate Ambient Occlusion (AO)
    print("  -> Calculating Ambient Occlusion...")
    blurred = cv2.GaussianBlur(gray, (31, 31), 0)
    # Prevent division by zero
    blurred[blurred == 0] = 1
    ao = cv2.divide(gray, blurred, scale=255)
    ao = cv2.normalize(ao, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    # Add a slight gamma to deepen the shadows
    ao = np.array(255 * (ao / 255) ** 1.5, dtype='uint8')

    # 6. ORM Packing for <model-viewer>
    # Red = AO, Green = Roughness, Blue = Metallic
    print("  -> Packing ORM texture (Occlusion, Roughness, Metallic)...")
    metallic = np.zeros_like(gray) # Fabric has 0 metallic
    
    # Stack channels (OpenCV is BGR, so Blue=Metallic, Green=Roughness, Red=AO)
    orm_packed = np.stack([metallic, roughness, ao], axis=-1)

    # Save the 3 required maps for glTF
    print("  -> Saving files...")
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_basecolor.jpg"), albedo)
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_normal.jpg"), normal_map)
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_orm.jpg"), orm_packed)

def main():
    parser = argparse.ArgumentParser(description="Generate Seamless ORM-packed PBR maps for <model-viewer>.")
    parser.add_argument("--input_dir", default=".", help="Directory containing the input scans.")
    parser.add_argument("--output_dir", default="./model_viewer_textures", help="Directory to save the results.")
    parser.add_argument("--resolution", type=int, default=2048, help="Output resolution (default 2048 for 2K). Max recommended for web is 4096.")
    
    args = parser.parse_args()
    
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff']:
        image_files.extend(glob.glob(os.path.join(args.input_dir, ext)))
        image_files.extend(glob.glob(os.path.join(args.input_dir, ext.upper())))
        
    if not image_files:
        print(f"No image files found in {args.input_dir}")
        return
        
    print(f"Found {len(image_files)} images. Starting batch processing...")
    for img_path in image_files:
        process_texture(img_path, args.output_dir, args.resolution)
        
    print("\nBatch complete! Your textures are ready for <model-viewer>.")

if __name__ == "__main__":
    main()
