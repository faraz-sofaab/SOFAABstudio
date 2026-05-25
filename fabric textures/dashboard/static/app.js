import * as THREE from 'three';

// --- STATE MANAGEMENT ---
let currentTab = 'fabrics';
let currentAsset = null;
let currentStep = 1;
let engine = null;

// --- INITIALIZATION ---
window.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initUpload();
    initWorkflowNav();
    loadAssets();
});

// --- UI LOGIC ---

function initTabs() {
    document.querySelectorAll('.main-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.main-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTab = btn.getAttribute('data-tab');
            currentAsset = null;
            showEmptyState();
            loadAssets();
        });
    });
}

function initWorkflowNav() {
    document.querySelectorAll('.workflow-step').forEach(btn => {
        btn.addEventListener('click', () => {
            const step = parseInt(btn.getAttribute('data-step'));
            setStep(step);
        });
    });
}

function setStep(step) {
    currentStep = step;
    document.querySelectorAll('.workflow-step').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.getAttribute('data-step')) === step);
    });
    // Handle step view visibility here
    renderWorkspace();
}

function initUpload() {
    const trigger = document.getElementById('btn-upload-trigger');
    const input = document.getElementById('upload-input');
    trigger.addEventListener('click', () => input.click());
    input.addEventListener('change', async (e) => {
        if (e.target.files.length > 0) {
            await handleUpload(e.target.files[0]);
        }
    });
}

async function handleUpload(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.success) loadAssets();
}

async function loadAssets() {
    const list = document.getElementById('asset-list');
    list.innerHTML = '<div class="loading-state">Syncing...</div>';
    
    try {
        const endpoint = currentTab === 'fabrics' ? '/api/textures' : '/api/models';
        const res = await fetch(endpoint);
        const assets = await res.json();
        
        list.innerHTML = '';
        assets.forEach(asset => {
            const item = document.createElement('div');
            item.className = `asset-item ${currentAsset && currentAsset.id === asset.id ? 'active' : ''}`;
            
            const thumb = currentTab === 'fabrics' ? asset.raw_url : '/static/model_icon.png';
            
            item.innerHTML = `
                <img src="${thumb}" class="asset-thumb">
                <div class="asset-info">
                    <h4>${asset.name || asset.id}</h4>
                    <p>${currentTab.toUpperCase()}</p>
                </div>
            `;
            
            item.onclick = () => selectAsset(asset);
            list.appendChild(item);
        });
    } catch (e) {
        list.innerHTML = '<div class="error-state">Connection Lost</div>';
    }
}

function selectAsset(asset) {
    currentAsset = asset;
    document.querySelectorAll('.asset-item').forEach(i => i.classList.remove('active'));
    
    document.getElementById('empty-state').classList.add('hidden');
    
    // Show correct editor
    document.querySelectorAll('.editor-view').forEach(v => v.classList.add('hidden'));
    const editorId = `${currentTab.slice(0, -1)}-editor`;
    document.getElementById(editorId).classList.remove('hidden');
    
    // Update display name
    document.getElementById(`${currentTab.slice(0, -1)}-display-name`).innerText = asset.name || asset.id;
    
    setStep(1);
}

function showEmptyState() {
    document.getElementById('empty-state').classList.remove('hidden');
    document.querySelectorAll('.editor-view').forEach(v => v.classList.add('hidden'));
}

function renderWorkspace() {
    const steps = ['fabric-step-1', 'fabric-step-2', 'fabric-step-3'];
    steps.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });

    const activeId = `fabric-step-${currentStep}`;
    const container = document.getElementById(activeId);
    if (!container || !currentAsset) return;

    container.classList.remove('hidden');
    container.innerHTML = '';

    if (currentStep === 1) {
        container.innerHTML = `
            <div class="step-layout import-view">
                <div class="preview-box">
                    <img src="${currentAsset.raw_url}" id="import-preview">
                </div>
                <div class="info-sidebar">
                    <h3>Import Details</h3>
                    <div class="meta-row"><span>Filename:</span> <span>${currentAsset.id}</span></div>
                    <div class="meta-row"><span>Type:</span> <span>RAW SCAN</span></div>
                    <button class="btn btn-primary" onclick="window.setStep(2)" style="margin-top: 20px; width: 100%;">PROCEED TO 2D ADJUSTMENTS</button>
                </div>
            </div>
        `;
    } else if (currentStep === 2) {
        container.innerHTML = `
            <div class="step-layout adjustment-view">
                <div class="canvas-box">
                    <img src="${currentAsset.raw_url}" id="adjustment-preview">
                </div>
                <div class="controls-sidebar">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3>2D Controls</h3>
                        <button class="btn-text" onclick="resetSettings()">RESET (CTRL+Z)</button>
                    </div>
                    <div class="control-group">
                        <label>Brightness</label>
                        <input type="range" id="adj-brightness" min="-100" max="100" value="${currentAsset.settings?.brightness || 0}">
                    </div>
                    <div class="control-group">
                        <label>Contrast</label>
                        <input type="range" id="adj-contrast" min="0.1" max="3.0" step="0.1" value="${currentAsset.settings?.contrast || 1.0}">
                    </div>
                    <div class="control-group">
                        <label>Saturation</label>
                        <input type="range" id="adj-saturation" min="0" max="2" step="0.1" value="${currentAsset.settings?.saturation || 1.0}">
                    </div>
                    <button class="btn btn-primary" id="btn-save-2d" style="margin-top: 20px; width: 100%;">GENERATE MAPS -> MOVE TO 3D</button>
                </div>
            </div>
        `;
        setTimeout(init2DListeners, 10);
    } else if (currentStep === 3) {
        container.innerHTML = `
            <div class="step-layout three-view">
                <div class="three-box" id="three-container" style="position: relative; background: #fff;">
                </div>
                <div class="controls-sidebar">
                    <h3>3D Material Settings</h3>
                    <div class="control-group">
                        <label>Current Model</label>
                        <div style="display: flex; gap: 10px;">
                            <button class="btn btn-outline" id="btn-load-model" style="font-size: 0.7rem; padding: 5px;">LOAD BROOKLYN</button>
                            <input type="file" id="model-upload-input" hidden accept=".glb">
                            <button class="btn btn-outline" onclick="document.getElementById('model-upload-input').click()" style="font-size: 0.7rem; padding: 5px;">UPLOAD GLB</button>
                        </div>
                    </div>
                    <div class="control-group">
                        <label>Texture Tiling (UV)</label>
                        <input type="range" id="3d-uv" min="1" max="20" value="8">
                    </div>
                    <div class="control-group">
                        <label>Color Tint</label>
                        <input type="color" id="3d-tint" value="#ffffff" style="width: 100%; height: 40px; cursor: pointer;">
                    </div>
                    <div class="control-group">
                        <label>Sheen Level</label>
                        <input type="range" id="3d-sheen" min="0" max="1" step="0.01" value="0.5">
                    </div>
                    <button class="btn btn-primary" id="btn-export-maps" style="margin-top: 20px; width: 100%;">EXPORT FINAL MAPS</button>
                </div>
            </div>
        `;
        setTimeout(init3DEngine, 10);
    }
}

function init2DListeners() {
    const bInput = document.getElementById('adj-brightness');
    const cInput = document.getElementById('adj-contrast');
    const sInput = document.getElementById('adj-saturation');
    
    [bInput, cInput, sInput].forEach(el => {
        if (el) el.addEventListener('input', updateCSSPreview);
    });
    document.getElementById('btn-save-2d').addEventListener('click', async () => {
        const btn = document.getElementById('btn-save-2d');
        btn.innerText = "GENERATING MAPS...";
        btn.disabled = true;
        
        const cropEl = document.getElementById('adj-crop');
        const settings = {
            brightness: parseFloat(document.getElementById('adj-brightness').value),
            contrast: parseFloat(document.getElementById('adj-contrast').value),
            saturation: parseFloat(document.getElementById('adj-saturation').value),
            edge_crop: cropEl ? parseFloat(cropEl.value) / 100 : 0.1
        };
        
        try {
            const res = await fetch(`/api/generate/${currentAsset.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            
            if (res.ok) {
                btn.innerText = "MAPS GENERATED!";
                // Refresh asset to get new map URLs by fetching the list and finding this one
                const assetRes = await fetch(`/api/textures`);
                const allAssets = await assetRes.json();
                currentAsset = allAssets.find(a => a.id === currentAsset.id);
                setTimeout(() => window.setStep(3), 1000);
            } else {
                btn.innerText = "ERROR - CHECK CONSOLE";
                btn.disabled = false;
            }
        } catch (e) {
            btn.innerText = "ERROR - NETWORK";
            btn.disabled = false;
        }
    });
}

function updateCSSPreview() {
    const img = document.getElementById('adjustment-preview');
    if (!img) return;
    const b = document.getElementById('adj-brightness').value;
    const c = document.getElementById('adj-contrast').value;
    const s = document.getElementById('adj-saturation').value;
    
    img.style.filter = `brightness(${1 + b/100}) contrast(${c}) saturate(${s})`;
}

// --- EXPOSE GLOBALS ---
window.setStep = setStep;
window.resetSettings = resetSettings;

// --- RESET & UNDO ---
function resetSettings() {
    if (!currentAsset) return;
    if (currentStep === 2) {
        const b = document.getElementById('adj-brightness');
        const c = document.getElementById('adj-contrast');
        const s = document.getElementById('adj-saturation');
        if (b) b.value = 0;
        if (c) c.value = 1.0;
        if (s) s.value = 1.0;
        updateCSSPreview();
    }
}

window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        resetSettings();
    }
});

// Update init3DEngine to handle model loading
async function init3DEngine() {
    const container = document.getElementById('three-container');
    if (!container || !currentAsset || !currentAsset.has_maps) return;

    if (!window.luxuryEngine) {
        window.luxuryEngine = new LuxuryEngine(container);
    } else {
        window.luxuryEngine.updateContainer(container);
    }

    // Default Model: Brooklyn
    window.luxuryEngine.loadModel('/static/models/brooklyn3smodel.glb');

    // Maps
    window.luxuryEngine.updateTextures(currentAsset.maps);

    // Controls
    document.getElementById('3d-uv').addEventListener('input', (e) => window.luxuryEngine.updateUVScale(parseFloat(e.target.value)));
    document.getElementById('3d-tint').addEventListener('input', (e) => window.luxuryEngine.updateTint(e.target.value));
    document.getElementById('3d-sheen').addEventListener('input', (e) => window.luxuryEngine.updateSheen(parseFloat(e.target.value)));
    
    // Model Upload
    document.getElementById('model-upload-input').addEventListener('change', (e) => {
        if (e.target.files[0]) {
            const url = URL.createObjectURL(e.target.files[0]);
            window.luxuryEngine.loadModel(url);
        }
    });

    document.getElementById('btn-load-model').addEventListener('click', () => {
        window.luxuryEngine.loadModel('/static/models/brooklyn3smodel.glb');
    });
}

class LuxuryEngine {
    constructor(container) {
        this.container = container;
        this.init();
        this.loader = new THREE.TextureLoader();
        this.glbLoader = null; // Will load dynamically
    }

    async init() {
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(45, this.container.clientWidth / this.container.clientHeight, 0.1, 100);
        this.camera.position.set(0, 1, 4);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.container.appendChild(this.renderer.domElement);

        this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        const sun = new THREE.DirectionalLight(0xffffff, 1.2);
        sun.position.set(5, 10, 7);
        this.scene.add(sun);

        this.animate();
    }

    async loadModel(url) {
        const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');
        if (!this.glbLoader) this.glbLoader = new GLTFLoader();

        this.glbLoader.load(url, (gltf) => {
            if (this.currentModel) this.scene.remove(this.currentModel);
            this.currentModel = gltf.scene;
            this.scene.add(this.currentModel);
            
            // Apply current material to the model
            this.currentModel.traverse(node => {
                if (node.isMesh) node.material = this.material;
            });
        }, undefined, (err) => {
            // Fallback to sphere if GLB fails
            if (this.currentModel) this.scene.remove(this.currentModel);
            const geo = new THREE.SphereGeometry(1, 64, 64);
            this.mesh = new THREE.Mesh(geo, this.material);
            this.currentModel = this.mesh;
            this.scene.add(this.mesh);
        });
    }

    updateTextures(maps) {
        if (!this.material) this.material = new THREE.MeshPhysicalMaterial({ color: 0xffffff });
        const ts = Date.now();
        
        ['map', 'normalMap', 'roughnessMap'].forEach(type => {
            const mapUrl = type === 'map' ? maps.basecolor : (type === 'normalMap' ? maps.normal : maps.orm);
            this.loader.load(`${mapUrl}?t=${ts}`, (tex) => {
                tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
                tex.repeat.set(8, 8);
                this.material[type] = tex;
                if (type === 'roughnessMap') this.material.metalnessMap = tex;
                this.material.needsUpdate = true;
            });
        });
    }

    updateUVScale(v) { if (this.material.map) ['map', 'normalMap', 'roughnessMap'].forEach(m => this.material[m].repeat.set(v, v)); }
    updateTint(h) { this.material.color.set(h); }
    updateSheen(v) { this.material.sheen = v; this.material.sheenRoughness = 0.5; }
    updateContainer(c) { 
        this.container = c; 
        this.renderer.setSize(c.clientWidth, c.clientHeight);
        this.camera.aspect = c.clientWidth / c.clientHeight;
        this.camera.updateProjectionMatrix();
        c.appendChild(this.renderer.domElement);
    }
    animate() { requestAnimationFrame(() => this.animate()); this.renderer.render(this.scene, this.camera); }
}
