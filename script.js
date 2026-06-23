// Clock logic
function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
    document.getElementById('clock').innerText = timeStr;
    
    // Update timestamp overlay
    const dateStr = now.toISOString().split('T')[0];
    const activeCam = document.querySelector('.cyber-btn.active').innerText;
    document.getElementById('cam-timestamp').innerText = `${dateStr} ${timeStr} ${activeCam}`;
}
setInterval(updateClock, 1000);
updateClock();

// Cam Switching Logic
const camButtons = document.querySelectorAll('.feed-controls .cyber-btn');
const mainCamImg = document.getElementById('main-cam-img');
const mainCamVideo = document.getElementById('main-cam-video');
const boxAuth = document.getElementById('box-auth');
const boxUnknown = document.getElementById('box-unknown');

let currentStream = null;

async function startWebcam() {
    try {
        currentStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } } });
        mainCamVideo.srcObject = currentStream;
        mainCamVideo.style.display = 'block';
        mainCamImg.style.display = 'none';
        
        // Add a filter to the video to match the aesthetic
        mainCamVideo.style.filter = 'contrast(1.2) brightness(0.9) sepia(0.2) hue-rotate(150deg)';
        addLog('WEBCAM LINK ESTABLISHED', 'normal');
    } catch (err) {
        console.error("Error accessing webcam:", err);
        addLog('WEBCAM ACCESS DENIED', 'alert');
        mainCamVideo.style.display = 'none';
        mainCamImg.style.display = 'block';
    }
}

function stopWebcam() {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
    }
    mainCamVideo.style.display = 'none';
    mainCamImg.style.display = 'block';
}

const camFeeds = {
    '1': 'assets/feed1.png',
    '2': 'assets/feed2.png',
    '3': 'assets/feed3.png',
    '4': 'assets/feed4.png'
};

camButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
        // Reset active state
        camButtons.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        
        const camId = e.target.getAttribute('data-cam');
        
        if (camId === '1') {
            startWebcam();
        } else {
            stopWebcam();
            
            // Change image
            mainCamImg.src = camFeeds[camId] || camFeeds['1'];
            
            // Add glitch effect
            mainCamImg.style.filter = 'contrast(2) brightness(1.5) grayscale(1)';
            setTimeout(() => {
                mainCamImg.style.filter = 'contrast(1.2) brightness(0.9) sepia(0.2) hue-rotate(150deg)';
            }, 150);
        }
        
        // Hide boxes initially
        boxAuth.style.display = 'none';
        boxUnknown.style.display = 'none';
    });
});

// Initialize with webcam on CAM-01
startWebcam();

// AI Simulation & Real Detection Logic
let modelsLoaded = false;
let labeledDescriptors = [];
let faceMatcher = null;

// Object Detection Worker
let objectWorker = new Worker('object-detector.js');
let objectDetectorReady = false;
let isDetectingObjects = false;
const hiddenCanvas = document.createElement('canvas');
const hiddenCtx = hiddenCanvas.getContext('2d');

objectWorker.onmessage = (e) => {
    if (e.data.type === 'ready') {
        objectDetectorReady = true;
        addLog('COCO-SSD Weapon Model Online.', 'normal');
    } else if (e.data.type === 'result') {
        isDetectingObjects = false;
        const objDetections = e.data.predictions;
        objDetections.forEach(obj => {
            const dangerousClasses = ['knife', 'scissors', 'baseball bat', 'gun'];
            if (dangerousClasses.includes(obj.class)) {
                // Scale bbox from 416x416 downscale to display size
                const scaleX = mainCamVideo.clientWidth / 416;
                const scaleY = mainCamVideo.clientHeight / 416;
                const scaledBox = [
                    obj.bbox[0] * scaleX,
                    obj.bbox[1] * scaleY,
                    obj.bbox[2] * scaleX,
                    obj.bbox[3] * scaleY
                ];
                triggerWeaponDetection(scaledBox, obj.class);
            }
        });
    } else if (e.data.type === 'error') {
        isDetectingObjects = false;
        console.error("Worker error:", e.data.message);
    }
};

async function initFaceAPI() {
    const MODEL_URL = './models/';
    try {
        await Promise.all([
            faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
            faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
            faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
        ]);
        modelsLoaded = true;
        document.getElementById('ai-status').innerText = 'ONLINE';
        document.getElementById('ai-status').className = 'text-green';
        addLog('AI Vision Models Loaded.', 'normal');
        
        // Load saved identities from browser memory
        const savedData = localStorage.getItem('aegis_faces');
        if (savedData) {
            const parsed = JSON.parse(savedData);
            labeledDescriptors = parsed.map(data => {
                const descArray = data.descriptors.map(d => new Float32Array(Object.values(d)));
                return new faceapi.LabeledFaceDescriptors(data.label, descArray);
            });
            addLog(`Loaded ${labeledDescriptors.length} identities from Cloud DB.`, 'normal');
        }
        
        // Create an initial face matcher
        faceMatcher = new faceapi.FaceMatcher(labeledDescriptors.length > 0 ? labeledDescriptors : [new faceapi.LabeledFaceDescriptors('placeholder', [new Float32Array(128)])], 0.60);
    } catch(e) {
        console.error("Error loading models", e);
        document.getElementById('ai-status').innerText = 'MODEL ERROR';
        document.getElementById('ai-status').className = 'text-red blink';
    }
}

// Enroll new identity
document.getElementById('enroll-btn').addEventListener('click', async () => {
    try {
        if (!modelsLoaded) return addLog('ERROR: Models still loading...', 'alert');
        if (document.querySelector('.feed-controls .cyber-btn.active').getAttribute('data-cam') !== '1') {
            return addLog('ERROR: Switch to CAM-01 (Live Webcam)', 'alert');
        }
        
        const name = document.getElementById('enroll-name').value.trim().toUpperCase();
        if (!name) return addLog('ERROR: Enter a name to enroll.', 'alert');
        
        const btn = document.getElementById('enroll-btn');
        btn.innerText = "SCANNING...";
        btn.disabled = true;
        
        let face = null;
        for (let i = 0; i < 5; i++) {
            const detections = await faceapi.detectAllFaces(mainCamVideo).withFaceLandmarks().withFaceDescriptors();
            if (detections && detections.length > 0) {
                face = detections.reduce((prev, current) => (prev.detection.box.width > current.detection.box.width) ? prev : current);
                break;
            }
            await new Promise(r => setTimeout(r, 200)); 
        }
        
        if (!face) {
            addLog('ENROLLMENT FAILED: NO FACE DETECTED', 'alert');
            btn.innerText = "SCAN & ENROLL IDENTITY";
            btn.disabled = false;
            return;
        }
        
        const newDescriptor = new faceapi.LabeledFaceDescriptors(name, [face.descriptor]);
        labeledDescriptors.push(newDescriptor);
        
        // Save to browser localStorage to remember across refreshes
        const dataToSave = labeledDescriptors.map(ld => ({
            label: ld.label,
            descriptors: ld.descriptors.map(d => Array.from(d))
        }));
        localStorage.setItem('aegis_faces', JSON.stringify(dataToSave));
        
        // Re-initialize faceMatcher
        faceMatcher = new faceapi.FaceMatcher(labeledDescriptors, 0.60);
        
        addLog(`IDENTITY ENROLLED: ${name}`, 'normal');
        document.getElementById('enroll-name').value = '';
        btn.innerText = "SCAN & ENROLL IDENTITY";
        btn.disabled = false;
        
        document.getElementById('match-status').innerText = 'IDENTITY SAVED';
        document.getElementById('match-status').className = 'neon-green blink';
    } catch (e) {
        console.error(e);
        addLog(`JS ERROR: ${e.message}`, 'alert');
        document.getElementById('enroll-btn').innerText = "SCAN WEBCAM & ENROLL";
        document.getElementById('enroll-btn').disabled = false;
    }
});

// Photo Upload Enrollment
document.getElementById('enroll-image').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    if (!modelsLoaded) return addLog('ERROR: Models still loading...', 'alert');
    
    const name = document.getElementById('enroll-name').value.trim().toUpperCase();
    if (!name) return addLog('ERROR: Enter a name before uploading photo.', 'alert');
    
    const btn = document.getElementById('upload-btn');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ANALYZING...';
    btn.disabled = true;
    
    try {
        // Create an image element to read the file
        const img = await faceapi.bufferToImage(file);
        
        // Detect face in the uploaded image
        const detections = await faceapi.detectAllFaces(img).withFaceLandmarks().withFaceDescriptors();
        
        if (!detections || detections.length === 0) {
            addLog('ENROLLMENT FAILED: NO FACE DETECTED IN PHOTO', 'alert');
            btn.innerHTML = '<i class="fa-solid fa-upload"></i> UPLOAD PHOTO';
            btn.disabled = false;
            e.target.value = ''; // clear input
            return;
        }
        
        // Take the largest face if multiple people in photo
        const face = detections.reduce((prev, current) => (prev.detection.box.width > current.detection.box.width) ? prev : current);
        
        const newDescriptor = new faceapi.LabeledFaceDescriptors(name, [face.descriptor]);
        labeledDescriptors.push(newDescriptor);
        
        // Save to browser localStorage
        const dataToSave = labeledDescriptors.map(ld => ({
            label: ld.label,
            descriptors: ld.descriptors.map(d => Array.from(d))
        }));
        localStorage.setItem('aegis_faces', JSON.stringify(dataToSave));
        
        // Re-initialize faceMatcher
        faceMatcher = new faceapi.FaceMatcher(labeledDescriptors, 0.60);
        
        addLog(`PHOTO IDENTITY ENROLLED: ${name}`, 'normal');
        document.getElementById('enroll-name').value = '';
        btn.innerHTML = '<i class="fa-solid fa-upload"></i> UPLOAD PHOTO';
        btn.disabled = false;
        e.target.value = ''; // clear input
        
        document.getElementById('match-status').innerText = 'DB UPDATED';
        document.getElementById('match-status').className = 'neon-green blink';
        
    } catch (err) {
        console.error(err);
        addLog(`PHOTO ERROR: ${err.message}`, 'alert');
        btn.innerHTML = '<i class="fa-solid fa-upload"></i> UPLOAD PHOTO';
        btn.disabled = false;
        e.target.value = '';
    }
});

// Detection Loop
async function detectFaces() {
    if (!modelsLoaded) return;
    
    const activeCamId = document.querySelector('.cyber-btn.active').getAttribute('data-cam');
    const displaySize = { width: mainCamVideo.clientWidth || mainCamImg.clientWidth || 800, height: mainCamVideo.clientHeight || mainCamImg.clientHeight || 500 };
    const dynamicBoxes = document.getElementById('dynamic-boxes');
    
    if (activeCamId === '1' && currentStream) {
        // Run real detection on webcam FIRST so it doesn't blink
        const detections = await faceapi.detectAllFaces(mainCamVideo).withFaceLandmarks().withFaceDescriptors();
        const resizedDetections = faceapi.resizeResults(detections, displaySize);
        
        // NOW clear old face boxes instantly
        const oldFaces = document.querySelectorAll('.face-box');
        oldFaces.forEach(f => f.remove());
        
        // --- ADD OBJECT DETECTION VIA WORKER ---
        if (objectDetectorReady && !isDetectingObjects) {
            isDetectingObjects = true;
            hiddenCanvas.width = 416;
            hiddenCanvas.height = 416;
            if (mainCamVideo.videoWidth > 0) {
                hiddenCtx.drawImage(mainCamVideo, 0, 0, 416, 416);
                const imgData = hiddenCtx.getImageData(0, 0, 416, 416);
                objectWorker.postMessage({ type: 'detect', imageData: imgData });
            } else {
                isDetectingObjects = false;
            }
        }
        
        if (resizedDetections.length > 0) {
            let bestMatchLabel = 'UNKNOWN';
            let bestMatchConf = 0;
            
            resizedDetections.forEach(detection => {
                const match = faceMatcher.findBestMatch(detection.descriptor);
                const box = detection.detection.box;
                
                let isUnknown = match.label === 'unknown' || match.label === 'placeholder';
                let labelText = isUnknown ? `UNKNOWN [${(100 - match.distance * 100).toFixed(0)}%]` : `${match.label} [${(100 - match.distance * 100).toFixed(0)}%]`;
                let boxClass = isUnknown ? 'unknown-user' : 'auth-user';
                
                if(!isUnknown && (100 - match.distance * 100) > bestMatchConf) {
                    bestMatchLabel = match.label;
                    bestMatchConf = (100 - match.distance * 100);
                } else if (isUnknown && bestMatchConf === 0) {
                    bestMatchConf = (100 - match.distance * 100);
                }
                
                // Create custom box
                const div = document.createElement('div');
                div.className = `detection-box face-box ${boxClass}`;
                div.style.top = `${box.y}px`;
                div.style.left = `${box.x}px`;
                div.style.width = `${box.width}px`;
                div.style.height = `${box.height}px`;
                
                const icon = isUnknown ? '<i class="fa-solid fa-triangle-exclamation"></i>' : '<i class="fa-solid fa-check-circle"></i>';
                
                div.innerHTML = `
                    <div class="label">${icon} ${labelText}</div>
                    <div class="corner-tl"></div><div class="corner-tr"></div><div class="corner-bl"></div><div class="corner-br"></div>
                `;
                dynamicBoxes.appendChild(div);
                
                if (isUnknown && Math.random() > 0.95) {
                    addLog('WARNING: UNKNOWN PERSON DETECTED', 'alert');
                    reportAlertToBackend("CRIMINAL_MATCH", "HIGH", { suspect: "Unknown person on webcam scanner", confidence: 0.85 });
                }
            });
            
            // Update UI
            if (bestMatchLabel !== 'UNKNOWN') {
                document.getElementById('match-status').innerText = 'MATCH FOUND';
                document.getElementById('match-status').className = 'text-green';
                document.getElementById('conf-bar').style.width = `${bestMatchConf}%`;
                document.getElementById('conf-bar').className = 'fill neon-green-bg';
                document.getElementById('conf-val').innerText = `${bestMatchConf.toFixed(0)}%`;
            } else {
                document.getElementById('match-status').innerText = 'UNKNOWN IDENTITY';
                document.getElementById('match-status').className = 'text-red blink';
                document.getElementById('conf-bar').style.width = `${bestMatchConf}%`;
                document.getElementById('conf-bar').className = 'fill neon-red-bg';
                document.getElementById('conf-val').innerText = `${bestMatchConf.toFixed(0)}%`;
            }
            
        } else {
            resetFaceUI();
        }
    } else {
        // Run simulated detection for static images
        dynamicBoxes.innerHTML = '';
        simulateStaticImages();
    }
    
    setTimeout(detectFaces, 1500);
}

function resetFaceUI() {
    document.getElementById('match-status').innerText = 'SCANNING...';
    document.getElementById('match-status').className = 'neon-blue blink';
    document.getElementById('conf-bar').style.width = '0%';
    document.getElementById('conf-bar').className = 'fill neon-purple-bg';
    document.getElementById('conf-val').innerText = '0%';
}

function simulateStaticImages() {
    const activeCamId = document.querySelector('.cyber-btn.active').getAttribute('data-cam');
    const dynamicBoxes = document.getElementById('dynamic-boxes');
    
    if (Math.random() > 0.8) {
        const div = document.createElement('div');
        if (activeCamId === '4') { // Server room authorized
            div.className = `detection-box auth-user`;
            div.style.top = `30%`; div.style.left = `45%`; div.style.width = `120px`; div.style.height = `120px`;
            div.innerHTML = `<div class="label"><i class="fa-solid fa-check-circle"></i> ID: SEC-02 [95%]</div>
                             <div class="corner-tl"></div><div class="corner-tr"></div><div class="corner-bl"></div><div class="corner-br"></div>`;
            document.getElementById('match-status').innerText = 'MATCH FOUND';
            document.getElementById('match-status').className = 'text-green';
            document.getElementById('conf-bar').style.width = '95%';
            document.getElementById('conf-bar').className = 'fill neon-green-bg';
            document.getElementById('conf-val').innerText = '95%';
        } else { // Others unknown
            div.className = `detection-box unknown-user`;
            div.style.top = `40%`; div.style.left = `60%`; div.style.width = `100px`; div.style.height = `100px`;
            div.innerHTML = `<div class="label"><i class="fa-solid fa-triangle-exclamation"></i> UNKNOWN [45%]</div>
                             <div class="corner-tl"></div><div class="corner-tr"></div><div class="corner-bl"></div><div class="corner-br"></div>`;
            document.getElementById('match-status').innerText = 'UNKNOWN IDENTITY';
            document.getElementById('match-status').className = 'text-red blink';
            document.getElementById('conf-bar').style.width = '45%';
            document.getElementById('conf-bar').className = 'fill neon-red-bg';
            document.getElementById('conf-val').innerText = '45%';
        }
        dynamicBoxes.appendChild(div);
    } else {
        resetFaceUI();
    }
}

// Initialize models and start detection loop
initFaceAPI();
setInterval(detectFaces, 500); // 500ms for performance

// Log System
const scanLogs = document.getElementById('scan-logs');
let allLogs = []; // Store all logs in memory for PDF export

function addLog(msg, type) {
    const timeStr = new Date().toLocaleTimeString('en-US', { hour12: false });
    const dateStr = new Date().toISOString().split('T')[0];
    
    allLogs.push({ date: dateStr, time: timeStr, msg: msg, type: type });
    
    const li = document.createElement('li');
    if (type === 'alert') li.className = 'alert blink';
    li.innerHTML = `<span>[${timeStr}]</span> <span>${msg}</span>`;
    
    scanLogs.prepend(li);
    if (scanLogs.children.length > 5) {
        scanLogs.removeChild(scanLogs.lastChild);
    }
}

// Export PDF Logic
document.getElementById('export-logs-btn').addEventListener('click', () => {
    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        doc.setFont("courier", "bold");
        doc.setFontSize(22);
        doc.setTextColor(0, 150, 150);
        doc.text("AEGIS NEXUS: SURVEILLANCE REPORT", 10, 20);
        
        doc.setFontSize(10);
        doc.setTextColor(100, 100, 100);
        doc.text(`Generated: ${new Date().toLocaleString()}`, 10, 28);
        
        let y = 40;
        
        allLogs.forEach((log) => {
            if (y > 280) { // Add new page if content exceeds height
                doc.addPage();
                y = 20;
            }
            
            let prefix = `[${log.date} ${log.time}]`;
            if (log.type === 'alert') {
                doc.setTextColor(220, 0, 0); // Red text for threats
                doc.setFont("courier", "bold");
            } else {
                doc.setTextColor(30, 30, 30); // Dark gray for normal
                doc.setFont("courier", "normal");
            }
            
            // Handle long messages by splitting them
            const splitMsg = doc.splitTextToSize(`${prefix} ${log.msg}`, 190);
            doc.text(splitMsg, 10, y);
            y += (7 * splitMsg.length);
        });
        
        doc.save("Aegis_Incident_Report.pdf");
        addLog("Security logs exported to PDF.", "normal");
    } catch(err) {
        console.error("PDF Export Error:", err);
        addLog("Failed to export PDF.", "alert");
    }
});

// Initial logs
addLog('System initialization complete.', 'normal');
addLog('Connected to Cloud DB.', 'normal');
addLog('Face encoding model loaded.', 'normal');

// Solar Battery Simulation
let battLevel = 85;
setInterval(() => {
    battLevel += (Math.random() > 0.5 ? 1 : -1);
    if(battLevel > 100) battLevel = 100;
    if(battLevel < 0) battLevel = 0;
    
    document.getElementById('batt-text').innerText = `${battLevel}%`;
    document.getElementById('batt-circle').setAttribute('stroke-dasharray', `${battLevel}, 100`);
    
    // Change color based on level
    const chart = document.querySelector('.circular-chart');
    if (battLevel > 60) chart.className = 'circular-chart green';
    else if (battLevel > 30) chart.className = 'circular-chart yellow';
    else chart.className = 'circular-chart red';
    
}, 5000);

// ==========================================
// DEMONSTRATION HACK: Weapon Detection
// ==========================================
document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'w') {
        triggerWeaponDetection();
    }
});

let weaponTimeout = null;

function triggerWeaponDetection(box = null, label = "FIREARM") {
    const dynamicBoxes = document.getElementById('dynamic-boxes');
    const weaponStat = document.getElementById('weapon-stat');
    
    // Create a massive red weapon box near the bottom of the feed
    const div = document.createElement('div');
    div.className = `detection-box unknown-user blink`;
    
    if (box) {
        div.style.left = `${box[0]}px`;
        div.style.top = `${box[1]}px`;
        div.style.width = `${box[2]}px`;
        div.style.height = `${box[3]}px`;
    } else {
        div.style.top = `60%`;
        div.style.left = `40%`;
        div.style.width = `180px`;
        div.style.height = `120px`;
    }
    
    div.style.borderColor = '#ff0000';
    div.style.boxShadow = '0 0 30px #ff0000';
    div.style.zIndex = '999';
    
    div.innerHTML = `
        <div class="label" style="background: #ff0000; color: #fff; font-size: 14px; border: 1px solid #fff;">
            <i class="fa-solid fa-triangle-exclamation"></i> ${label.toUpperCase()} DETECTED [99%]
        </div>
        <div class="corner-tl" style="border-color: #ff0000;"></div><div class="corner-tr" style="border-color: #ff0000;"></div><div class="corner-bl" style="border-color: #ff0000;"></div><div class="corner-br" style="border-color: #ff0000;"></div>
    `;
    
    dynamicBoxes.appendChild(div);
    
    // Add logs and alarms
    addLog(`CRITICAL THREAT: CONCEALED ${label.toUpperCase()} DETECTED`, 'alert');
    reportAlertToBackend("WEAPON", "CRITICAL", { weapon: label, confidence: 0.99, source: "Webcam Edge Node" });
    weaponStat.innerHTML = `<i class="fa-solid fa-gun text-red blink"></i> WEAPON DETECT: <span class="text-red blink" style="font-weight:bold;">THREAT FOUND</span>`;
    weaponStat.style.textShadow = '0 0 10px red';
    
    // Clear previous timeout if spamming 'W'
    if (weaponTimeout) clearTimeout(weaponTimeout);
    
    // Remove after 6 seconds
    weaponTimeout = setTimeout(() => {
        if(dynamicBoxes.contains(div)) dynamicBoxes.removeChild(div);
        weaponStat.innerHTML = '<i class="fa-solid fa-gun text-red"></i> WEAPON DETECT: ON';
        weaponStat.style.textShadow = 'none';
    }, 6000);
}

// --- BACKEND API CENTRALIZATION LINK ---
let backendNodeId = null;

async function registerAegisNode() {
    try {
        const response = await fetch('http://localhost:8000/api/v1/nodes/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_name: "Aegis Local Terminal (Webcam)",
                mac_address: "AA:BB:CC:DD:EE:FF",
                ip_address: "127.0.0.1",
                latitude: 12.9716,
                longitude: 77.5946,
                public_key: "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAv+58zO7d...\n-----END PUBLIC KEY-----"
            })
        });
        if (response.ok) {
            const data = await response.json();
            backendNodeId = data.id;
            console.log("[API LINK] Aegis Node registered with UUID:", backendNodeId);
        } else {
            const listResp = await fetch('http://localhost:8000/api/v1/nodes');
            if (listResp.ok) {
                const nodes = await listResp.json();
                const matched = nodes.find(n => n.mac_address === "AA:BB:CC:DD:EE:FF");
                if (matched) {
                    backendNodeId = matched.id;
                    console.log("[API LINK] Reconnected existing node UUID:", backendNodeId);
                }
            }
        }
    } catch (err) {
        console.log("[API LINK] Server offline. Standalone mode.");
    }
}
registerAegisNode();

async function reportAlertToBackend(alertType, threatLevel, details) {
    if (!backendNodeId) return;
    try {
        await fetch('http://localhost:8000/api/v1/alerts/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: backendNodeId,
                alert_type: alertType,
                threat_level: threatLevel,
                image_url: details.image || "https://images.unsplash.com/photo-1595590424283-b8f17842773f?w=600",
                payload: details,
                latitude: 12.9716,
                longitude: 77.5946,
                signature: "MOCK_SIGNATURE_OK"
            })
        });
    } catch (err) {
        console.error("[API LINK] Alert push failed:", err);
    }
}
