import os
import glob
import cv2
import numpy as np
import zipfile
import io
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration
import mimetypes
mimetypes.add_type('image/vnd.radiance', '.hdr')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
GENERATED_FOLDER = os.path.join(BASE_DIR, 'generated')
DB_PATH = os.path.join(BASE_DIR, 'database.db')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER
app.config['DB_PATH'] = DB_PATH

def init_db():
    conn = sqlite3.connect(app.config['DB_PATH'])
    c = conn.cursor()
    # Texture Settings Table
    c.execute('''CREATE TABLE IF NOT EXISTS textures
                 (id TEXT PRIMARY KEY, name TEXT, original_file TEXT, 
                  brightness REAL, contrast REAL, hue REAL, saturation REAL,
                  edge_crop REAL, mirror_tiling INTEGER, normal_strength REAL,
                  resolution INTEGER, has_maps INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # 3D Model Table
    c.execute('''CREATE TABLE IF NOT EXISTS models
                 (id TEXT PRIMARY KEY, name TEXT, file_path TEXT, 
                  leg_configs TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    return conn
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max for high-res scans

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def adjust_color(img, brightness=0, contrast=1.0, hue=0, saturation=1.0):
    # Adjust brightness and contrast
    # img = contrast * img + brightness
    img = cv2.convertScaleAbs(img, alpha=contrast, beta=brightness)
    
    # Adjust hue and saturation
    if hue != 0 or saturation != 1.0:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        
        # Shift hue
        if hue != 0:
            h = np.mod(h + hue, 180) # OpenCV hue is 0-179
            
        # Scale saturation
        if saturation != 1.0:
            s = np.clip(s * saturation, 0, 255)
            
        hsv = cv2.merge([h, s, v])
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
    return img

def delight_image(img):
    """
    Industry Standard High-Pass Delighting: Removes both global and local 
    lighting gradients to ensure the texture is perfectly flat for tiling.
    """
    # Convert to float for math
    img_float = img.astype(np.float32)
    
    # 1. Global lighting (Large Sigma) - Use BORDER_REPLICATE to avoid edge halos!
    sigma_global = max(img.shape) // 4
    blur_global = cv2.GaussianBlur(img_float, (0, 0), sigmaX=sigma_global, borderType=cv2.BORDER_REPLICATE)
    
    # 2. Local lighting (Small Sigma)
    sigma_local = max(img.shape) // 10
    blur_local = cv2.GaussianBlur(img_float, (0, 0), sigmaX=sigma_local, borderType=cv2.BORDER_REPLICATE)
    
    # Hybrid Delighting: Base + (Original - Mixed Blur)
    mean_val = np.mean(img_float, axis=(0,1))
    
    # High-pass = Original - (Weighted Blurs) + Mean
    # This keeps the details but kills the gradients
    delighted = img_float - (0.7 * blur_global + 0.3 * blur_local) + mean_val
    
    return np.clip(delighted, 0, 255).astype(np.uint8)

def make_seamless(img, feather_ratio=0.25, mirror=False):
    """
    Tiling Engine:
    - Mirror Mode: Flips the image at the edges for zero-seam continuity.
    - Sigmoid Mode: Uses cross-fade with an S-curve to hide joins.
    """
    if mirror:
        # Mirror Tiling (Industry Standard for Patternless Fabrics)
        h, w = img.shape[:2]
        # Create 2x2 mirrored grid
        top_left = img
        top_right = cv2.flip(img, 1)
        bottom_left = cv2.flip(img, 0)
        bottom_right = cv2.flip(cv2.flip(img, 0), 1)
        
        top = np.concatenate([top_left, top_right], axis=1)
        bottom = np.concatenate([bottom_left, bottom_right], axis=1)
        full = np.concatenate([top, bottom], axis=0)
        
        # Resize back to original resolution
        return cv2.resize(full, (w, h), interpolation=cv2.INTER_AREA)

    # Sigmoid-based seamless tiling...
    h, w = img.shape[:2]
    offset_img = np.roll(img, (h//2, w//2), axis=(0, 1))
    
    def sigmoid(x):
        return 1 / (1 + np.exp(-10 * (x - 0.5)))
    
    def blend_window(size, feather):
        window = np.ones(size, dtype=np.float32)
        f_pixels = int(size * feather / 2)
        if f_pixels > 0:
            # Sigmoid ramp
            ramp = sigmoid(np.linspace(0, 1, f_pixels))
            window[:f_pixels] = ramp
            window[-f_pixels:] = ramp[::-1]
        return window
        
    mask_x = blend_window(w, feather_ratio)
    mask_y = blend_window(h, feather_ratio)
    mask = np.outer(mask_y, mask_x)
    
    if len(img.shape) == 3:
        mask = mask[:, :, np.newaxis]
        
    result = img.astype(np.float32) * mask + offset_img.astype(np.float32) * (1 - mask)
    return result.astype(np.uint8)

def generate_pbr(image_path, base_name, options):
    img = cv2.imread(image_path)
    if img is None:
        return False, "Failed to load image"

    # Color Adjustments
    brightness = float(options.get('brightness', 0))
    contrast = float(options.get('contrast', 1.0))
    hue = float(options.get('hue', 0))
    saturation = float(options.get('saturation', 1.0))
    resolution = int(options.get('resolution', 2048))
    edge_crop = float(options.get('edge_crop', 10)) / 100.0
    tint_hex = options.get('tint_color', '#ffffff')
    
    img = adjust_color(img, brightness, contrast, hue, saturation)

    # 0. Center Fabric Extraction (Avoid flatbed white borders and light leaks)
    h, w = img.shape[:2]
    
    # We want to take a square from the absolute center of the scan.
    # To be completely safe from scanner borders, we take a square that is 
    # only 60% of the shortest dimension.
    safe_dim = int(min(h, w) * 0.6)
    
    # Apply user's edge crop on top of the safe dimension if they want to zoom in more
    if edge_crop > 0:
        safe_dim = int(safe_dim * (1.0 - edge_crop))
        
    start_x = (w - safe_dim) // 2
    start_y = (h - safe_dim) // 2
    
    img_square = img[start_y:start_y+safe_dim, start_x:start_x+safe_dim]
    img_resized = cv2.resize(img_square, (resolution, resolution), interpolation=cv2.INTER_AREA)

    # 1.5 Flatten lighting gradients to prevent dark/light grid patterns
    img_resized = delight_image(img_resized)

    # 2. Make Seamless
    mirror_tiling = options.get('mirror_tiling', False)
    if isinstance(mirror_tiling, str):
        mirror_tiling = mirror_tiling.lower() == 'true'
        
    seamless_albedo = make_seamless(img_resized, feather_ratio=0.25, mirror=mirror_tiling)

    # 1. Base Color (Diffuse)
    # No bilateral filter - we must retain 100% of the raw thread crispness for Poliigon quality.
    albedo = seamless_albedo.copy()
    
    # Convert to grayscale for height generation
    gray = cv2.cvtColor(albedo, cv2.COLOR_BGR2GRAY)
    
    # Enhance micro-contrast without creating grid artifacts (No CLAHE)
    gray_enhanced = gray.copy()

    # 3. Normal Map (Ultra-Crisp for 3D engine)
    # Using Sobel with ksize=3 gives the best balance of thread detail without noise
    grad_x = cv2.Sobel(gray_enhanced, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray_enhanced, cv2.CV_64F, 0, 1, ksize=3)
    
    # Scale controls the "depth" of the weave. 
    strength = float(options.get('normal_strength', 2.0))
    normal_x = grad_x * strength
    # Invert Y for OpenGL (Three.js uses OpenGL standard where Y is UP)
    normal_y = -grad_y * strength 
    # Z should be proportional to the max possible gradient (255 * 8 for Sobel) to keep it balanced
    normal_z = np.full(gray.shape, 2048.0 / max(1.0, strength)) 

    normal_map = np.stack([normal_z, normal_y, normal_x], axis=-1)
    norm = np.linalg.norm(normal_map, axis=-1, keepdims=True)
    norm[norm == 0] = 1 
    normal_map = normal_map / norm
    # Remap from [-1, 1] to [0, 255]
    normal_map = ((normal_map + 1.0) * 127.5).astype(np.uint8)

    # 4. Roughness (High Contrast for Realism)
    # The key to Poliigon realism is micro-reflections. 
    # Threads are somewhat shiny (lower roughness), gaps are completely matte (high roughness).
    gray_inv = 255 - gray_enhanced
    # Expand range to [120, 240] so it doesn't create glowing mirror dots (0)
    roughness = cv2.normalize(gray_inv, None, alpha=120, beta=240, norm_type=cv2.NORM_MINMAX)

    # 5. Ambient Occlusion (Deep Shadows)
    # Use BORDER_REPLICATE to prevent edge halos
    blurred_ao = cv2.GaussianBlur(gray, (15, 15), 0, borderType=cv2.BORDER_REPLICATE)
    blurred_ao[blurred_ao == 0] = 1
    ao = cv2.divide(gray, blurred_ao, scale=255)
    # Map mid-tones to white, but keep deep shadows black
    ao = cv2.normalize(ao, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    # Apply a gamma curve to push the AO deeper
    ao = np.power(ao.astype(np.float32) / 255.0, 2.0) * 255.0
    ao = ao.astype(np.uint8)

    # 6. Maps Generation for UI
    metallic = np.zeros_like(gray)
    
    # Standard ORM (Occlusion, Roughness, Metallic)
    orm_packed = np.stack([metallic, roughness, ao], axis=-1)
    
    # Specific Metallic-Roughness (B=Metallic, G=Roughness, R=0)
    mr_packed = np.stack([metallic, roughness, np.zeros_like(gray)], axis=-1)

    # Save
    out_dir = os.path.join(app.config['GENERATED_FOLDER'], base_name)
    os.makedirs(out_dir, exist_ok=True)
    
    cv2.imwrite(os.path.join(out_dir, f"{base_name}_diffuse.jpg"), albedo)
    cv2.imwrite(os.path.join(out_dir, f"{base_name}_normal.jpg"), normal_map)
    cv2.imwrite(os.path.join(out_dir, f"{base_name}_roughness.jpg"), roughness)
    cv2.imwrite(os.path.join(out_dir, f"{base_name}_occlusion.jpg"), ao)
    cv2.imwrite(os.path.join(out_dir, f"{base_name}_metallic_roughness.jpg"), mr_packed)
    cv2.imwrite(os.path.join(out_dir, f"{base_name}_orm.jpg"), orm_packed) # Keep ORM just in case
    
    return True, "Success"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/textures', methods=['GET'])
def list_textures():
    db = get_db()
    rows = db.execute('SELECT * FROM textures ORDER BY created_at DESC').fetchall()
    
    textures = []
    existing_ids_in_db = []
    
    for row in rows:
        base_name = row['id']
        existing_ids_in_db.append(base_name)
        has_maps = row['has_maps']
        
        textures.append({
            'id': base_name,
            'name': row['name'],
            'raw_url': f'/uploads/{row["original_file"]}',
            'has_maps': bool(has_maps),
            'settings': {
                'brightness': row['brightness'],
                'contrast': row['contrast'],
                'hue': row['hue'],
                'saturation': row['saturation'],
                'edge_crop': row['edge_crop'],
                'mirror_tiling': bool(row['mirror_tiling']),
                'normal_strength': row['normal_strength'],
                'resolution': row['resolution']
            },
            'maps': {
                'basecolor': f'/generated/{base_name}/{base_name}_diffuse.jpg' if has_maps else None,
                'normal': f'/generated/{base_name}/{base_name}_normal.jpg' if has_maps else None,
                'orm': f'/generated/{base_name}/{base_name}_orm.jpg' if has_maps else None,
            }
        })
    
    # Sync filesystem to DB (initial scan)
    new_found = False
    for ext in ('*.png', '*.jpg', '*.jpeg', '*.tif', '*.tiff'):
        for path in glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], ext)):
            filename = os.path.basename(path)
            tid = os.path.splitext(filename)[0]
            if tid not in existing_ids_in_db:
                db.execute('INSERT INTO textures (id, name, original_file, brightness, contrast, hue, saturation, edge_crop, mirror_tiling, normal_strength, resolution, has_maps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (tid, tid, filename, 0, 1.0, 0, 1.0, 0.1, 0, 2.0, 2048, 0))
                new_found = True
    
    if new_found:
        db.commit()
        return list_textures()
            
    return jsonify(textures)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    filename = secure_filename(file.filename)
    tid = os.path.splitext(filename)[0]
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    db = get_db()
    db.execute('INSERT OR REPLACE INTO textures (id, name, original_file, brightness, contrast, hue, saturation, edge_crop, mirror_tiling, normal_strength, resolution, has_maps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
               (tid, tid, filename, 0, 1.0, 0, 1.0, 0.1, 0, 2.0, 2048, 0))
    db.commit()
    
    return jsonify({'success': True, 'id': tid})

@app.route('/api/generate/<base_name>', methods=['POST'])
def generate_maps(base_name):
    data = request.json or {}
    
    db = get_db()
    db.execute('''UPDATE textures SET 
                  brightness=?, contrast=?, hue=?, saturation=?, 
                  edge_crop=?, mirror_tiling=?, normal_strength=?, resolution=?, has_maps=1 
                  WHERE id=?''', 
               (data.get('brightness', 0), data.get('contrast', 1.0), data.get('hue', 0),
                data.get('saturation', 1.0), data.get('edge_crop', 0.1), 
                1 if data.get('mirror_tiling') else 0, data.get('normal_strength', 2.0),
                data.get('resolution', 2048), base_name))
    db.commit()
    
    row = db.execute('SELECT * FROM textures WHERE id=?', (base_name,)).fetchone()
    if not row:
        return jsonify({'error': 'Texture not found'}), 404
        
    raw_path = os.path.join(app.config['UPLOAD_FOLDER'], row['original_file'])
    success, msg = generate_pbr(raw_path, base_name, data)
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': msg}), 500

@app.route('/api/models', methods=['GET', 'POST'])
def manage_models():
    db = get_db()
    if request.method == 'POST':
        # Handled in multi-part for file upload
        if 'file' in request.files:
            file = request.files['file']
            filename = secure_filename(file.filename)
            mid = os.path.splitext(filename)[0]
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            db.execute('INSERT OR REPLACE INTO models (id, name, file_path) VALUES (?, ?, ?)',
                       (mid, mid, filename))
            db.commit()
            return jsonify({'success': True, 'id': mid})
        
        # Or JSON for saving config
        data = request.json
        if 'leg_configs' in data:
            db.execute('UPDATE models SET leg_configs=? WHERE id=?', (json.dumps(data['leg_configs']), data['id']))
            db.commit()
            return jsonify({'success': True})
        
    rows = db.execute('SELECT * FROM models ORDER BY created_at DESC').fetchall()
    models = []
    for row in rows:
        models.append({
            'id': row['id'],
            'name': row['name'],
            'url': f'/uploads/{row["file_path"]}',
            'leg_configs': json.loads(row['leg_configs']) if row['leg_configs'] else None
        })
    return jsonify(models)

@app.route('/api/export/<base_name>', methods=['GET'])
def export_maps(base_name):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        generated_dir = os.path.join(app.config['GENERATED_FOLDER'], base_name)
        if not os.path.exists(generated_dir):
            return "Not generated yet", 404
            
        map_files = [
            '_diffuse.jpg', 
            '_normal.jpg', 
            '_roughness.jpg', 
            '_occlusion.jpg', 
            '_metallic_roughness.jpg',
            '_orm.jpg'
        ]
        for ext in map_files:
            filepath = os.path.join(generated_dir, base_name + ext)
            if os.path.exists(filepath):
                zf.write(filepath, base_name + ext)
    
    memory_file.seek(0)
    return send_file(memory_file, download_name=f"{base_name}_all_maps.zip", as_attachment=True)

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/generated/<path:filename>')
def serve_generated(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=8081)
