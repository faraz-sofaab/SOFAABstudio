import cv2
import numpy as np
import os
import glob
import argparse

def process_texture(image_path, output_dir):
    """
    Generates PBR maps (Albedo, Normal, Roughness, Specular, AO) from a single base fabric texture.
    """
    print(f"Processing: {image_path}")
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error loading image: {image_path}")
        return

    # Extract filename without extension
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # 1. Base Color / Albedo
    # Usually just the original image, maybe with some slight denoising (bilateral filter preserves edges)
    albedo = cv2.bilateralFilter(img, 9, 75, 75)
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_albedo.jpg"), albedo)

    # Convert to grayscale for subsequent maps
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Normal Map
    # Use Sobel filters to calculate gradients
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    # Create normal map
    # Z channel is usually constant or derived. We use a constant strong Z.
    strength = 2.0 # Adjust for stronger/weaker normals
    normal_x = (sobel_x * strength)
    normal_y = (sobel_y * strength)
    normal_z = np.full(gray.shape, 255.0)

    # OpenCV uses BGR, normal maps use RGB mapping where R=X, G=Y, B=Z
    # So B=Z, G=Y, R=X
    normal_map = np.stack([normal_z, normal_y, normal_x], axis=-1)
    
    # Normalize the vectors
    norm = np.linalg.norm(normal_map, axis=-1, keepdims=True)
    # Prevent division by zero
    norm[norm == 0] = 1 
    normal_map = normal_map / norm
    
    # Map from [-1, 1] to [0, 255]
    normal_map = ((normal_map + 1) * 127.5).astype(np.uint8)
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_normal.jpg"), normal_map)

    # 3. Roughness Map
    # Fabric usually has high roughness. Lighter = rougher, darker = smoother
    # We adjust the levels of grayscale to be mostly bright.
    roughness = cv2.normalize(gray, None, alpha=150, beta=255, norm_type=cv2.NORM_MINMAX)
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_roughness.jpg"), roughness)

    # 4. Specular Level Map
    # Specular controls the reflection intensity. Fabric has low specularity.
    # We use a darkened version of the grayscale map.
    specular = cv2.normalize(gray, None, alpha=10, beta=80, norm_type=cv2.NORM_MINMAX)
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_specular.jpg"), specular)

    # 5. Ambient Occlusion (AO) Map
    # AO adds soft shadows in crevices. We approximate this by dividing the original by a blurred version.
    blurred = cv2.GaussianBlur(gray, (21, 21), 0)
    ao = cv2.divide(gray, blurred, scale=255)
    
    # Increase contrast to emphasize the deep crevices
    # Darken shadows and keep bright areas bright
    ao = cv2.normalize(ao, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    
    # Optionally apply gamma correction to tweak the AO map
    gamma = 1.5
    ao = np.array(255 * (ao / 255) ** gamma, dtype='uint8')
    cv2.imwrite(os.path.join(output_dir, f"{base_name}_ao.jpg"), ao)
    
    print(f"Successfully generated maps for {base_name} in {output_dir}/")

def main():
    parser = argparse.ArgumentParser(description="Generate PBR maps from fabric textures.")
    parser.add_argument("--input_dir", default=".", help="Directory containing the input fabric texture images.")
    parser.add_argument("--output_dir", default="./output_maps", help="Directory to save the generated PBR maps.")
    
    args = parser.parse_args()
    
    # Supported image formats
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff']:
        image_files.extend(glob.glob(os.path.join(args.input_dir, ext)))
        # check uppercase extensions too
        image_files.extend(glob.glob(os.path.join(args.input_dir, ext.upper())))
        
    if not image_files:
        print(f"No image files found in {args.input_dir}")
        return
        
    for img_path in image_files:
        process_texture(img_path, args.output_dir)

if __name__ == "__main__":
    main()
