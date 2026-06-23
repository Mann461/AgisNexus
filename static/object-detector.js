/**
 * SolarShield AI — COCO-SSD Object Detection Web Worker
 * Runs TensorFlow.js COCO-SSD model in a background thread for real-time
 * weapon and dangerous object detection from webcam frames.
 * 
 * Feature 3: Added confidence threshold filtering, expanded dangerous class list,
 * and auto-retry model loading on failure.
 */

importScripts('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs');
importScripts('https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd');

let model = null;
let isLoading = false;

// Confidence threshold — only report detections above this level
const CONFIDENCE_THRESHOLD = 0.60;

// Expanded list of dangerous/weapon-adjacent object classes from COCO dataset
const DANGEROUS_CLASSES = [
    'knife', 'scissors', 'baseball bat', 'gun',
    'tennis racket', 'bottle', 'fork',  // Potential improvised weapons
];

async function loadModel(retryCount = 0) {
    if (isLoading) return;
    isLoading = true;
    
    const MAX_RETRIES = 3;
    
    try {
        model = await cocoSsd.load({
            base: 'lite_mobilenet_v2'  // Lighter model for faster inference in worker
        });
        postMessage({ type: 'ready' });
        console.log('[Worker] COCO-SSD model loaded successfully');
    } catch (err) {
        console.error(`[Worker] Model load error (attempt ${retryCount + 1}):`, err);
        
        if (retryCount < MAX_RETRIES) {
            console.log(`[Worker] Retrying model load in ${(retryCount + 1) * 2} seconds...`);
            setTimeout(() => {
                isLoading = false;
                loadModel(retryCount + 1);
            }, (retryCount + 1) * 2000);
        } else {
            postMessage({ type: 'error', message: `Failed to load model after ${MAX_RETRIES} attempts: ${err.message}` });
        }
    } finally {
        isLoading = false;
    }
}

// Initialize model on worker start
loadModel();

self.onmessage = async (e) => {
    if (!model || e.data.type !== 'detect') return;
    
    try {
        const predictions = await model.detect(e.data.imageData);
        
        // Filter predictions by confidence threshold and flag dangerous items
        const filteredPredictions = predictions
            .filter(pred => pred.score >= CONFIDENCE_THRESHOLD)
            .map(pred => ({
                class: pred.class,
                score: pred.score,
                bbox: pred.bbox,
                isDangerous: DANGEROUS_CLASSES.includes(pred.class)
            }));
        
        postMessage({ type: 'result', predictions: filteredPredictions });
    } catch(err) {
        postMessage({ type: 'error', message: err.message });
    }
};
