/**
 * VINMEC OVARIAN ULTRASOUND AI SYSTEM - GLOBAL STATE STORE
 */

const AppState = {
    currentUser: null,
    currentStudyId: null,
    currentImageId: null,
    currentPatientId: "ANON-VINMEC-185",
    currentPatientAge: "32",
    
    // File & Sample Selection
    uploadedFileObj: null,
    selectedSampleId: null,
    
    // AI Inference & IQA Data
    iqaResult: null,
    aiPredictionData: null,
    
    // Doctor Sign-off & HITL State
    doctorActionChoice: "ACCEPTED_RAW",
    selectedPathology: "CYSTIC",
    doctorNotes: "",
    activeFacilityKey: "times_city",
    
    // Calipers & Measurements
    calipers: {
        dmax_mm: 0.0,
        dorth_mm: 0.0,
        d3_mm: 0.0,
        area_cm2: 0.0,
        volume_cm3: 0.0
    },
    
    // Canvas & Viewport State
    canvas: {
        zoom: 1.0,
        panX: 0,
        panY: 0,
        tool: "brush",
        brushSize: 16,
        opacity: 0.40,
        maskVisible: true,
        viewMode: "single",
        isDrawing: false,
        isPanning: false,
        undoStack: [],
        redoStack: []
    },
    
    // Active Case for Modal Details & Reports
    modalCaseData: null
};

// Global clinical case object
let currentCase = {
    study_id: null,
    study_code: "STD-" + Math.floor(1000 + Math.random() * 9000),
    patient_id: "BN-VINMEC-185",
    patient_age: "32 (Tuổi sinh sản)",
    study_date: new Date().toISOString().split('T')[0],
    clinical_notes: "",
    image_id: null,
    image_filename: null,
    d3_mm: 0.0,
    volume_cm3: 0.0,
    volume_ml: 0.0,
    doctor_action: "ACCEPTED_RAW",
    selectedPathology: "U nang thanh dịch buồng trứng (Simple Serous Cyst)",
    doctorNotes: ""
};

// Global predictions, view mode, and tool states
let currentPrediction = null;
let currentActiveUser = null;
let currentStudyId = null;
let currentImageId = null;
let uploadedFileObj = null;
let selectedSampleId = null;
let aiPredictionData = null;
let doctorActionChoice = "ACCEPTED_RAW";
let selectedPathology = "CYSTIC";
let activeFacilityKey = "times_city";

// Caliper globals
let currentDmaxMm = 0.0;
let currentDorthMm = 0.0;
let currentD3Mm = 0.0;
let currentAreaCm2 = 0.0;
let currentVolumeCm3 = 0.0;

// Canvas & Viewport Globals
let canvas = null;
let ctx = null;
let maskCanvas = document.createElement('canvas');
maskCanvas.width = 512;
maskCanvas.height = 512;
let maskCtx = maskCanvas.getContext('2d');
let bgImage = new Image();

let currentViewMode = 'single';
let currentTool = 'brush';
let brushSize = 16;
let maskOpacity = 0.40;
let isMaskVisible = true;
let curtainSplitPercent = 50;

let currentZoom = 1.0;
let panOffsetX = 0;
let panOffsetY = 0;
let isPanning = false;
let startPanX = 0;
let startPanY = 0;

let lastX = 0;
let lastY = 0;
let isDrawing = false;
let undoStack = [];
let redoStack = [];
let canvasHistory = [];
let canvasHistoryIndex = -1;

// Case Management & Pagination Globals
let allCases = [];
let filteredCases = [];
let currentCasePage = 1;
const CASE_PAGE_SIZE = 10;
