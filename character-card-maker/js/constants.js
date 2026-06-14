/**
 * App Constants & Configuration
 * 
 * Global settings and element references used across the application.
 */

let DESIGN_WIDTH = 1600;
let DESIGN_HEIGHT = 1000;
let ASPECT = 8 / 5;
const ASPECT_TOLERANCE = 0.0025; // Tolerance for ratio validation

const canvas = document.getElementById("cardCanvas");
const ctx = canvas.getContext("2d");
const statusText = document.getElementById("statusText");
const canvasSizeLabel = document.getElementById("canvasSizeLabel");

/**
 * Updates the internal design dimensions and updates the UI labels.
 */
function setCanvasSize(width, height) {
  DESIGN_WIDTH = width;
  DESIGN_HEIGHT = height;
  ASPECT = width / height;
  canvas.width = width;
  canvas.height = height;
  if (canvasSizeLabel) {
    const prefix = UI_STRINGS.app.canvasSizePrefix || "Canvas: ";
    canvasSizeLabel.innerHTML = `<span data-ui="app.canvasSizePrefix">${prefix}</span>${width} x ${height}`;
  }
}

// --- UI Control Mappings ---
const controls = {
  // Global actions
  packageImport: document.getElementById("packageImport"),
  
  // Assets Tab
  assetRoleMode: document.getElementById("assetRoleMode"),
  baseUpload: document.getElementById("baseUpload"),
  avatarUpload: document.getElementById("avatarUpload"),
  fontUpload: document.getElementById("fontUpload"),
  
  // Layers Tab
  layerRoleMode: document.getElementById("layerRoleMode"),
  layerList: document.getElementById("layerList"),
  selectedLayerName: document.getElementById("selectedLayerName"),
  layerOpacity: document.getElementById("layerOpacity"),
  layerVisible: document.getElementById("layerVisible"),
  layerCustomBackground: document.getElementById("layerCustomBackground"),
  removeLayer: document.getElementById("removeLayer"),
  moveLayerUp: document.getElementById("moveLayerUp"),
  moveLayerDown: document.getElementById("moveLayerDown"),
  
  // Avatar Tab
  avatarShape: document.getElementById("avatarShape"),
  avatarX: document.getElementById("avatarX"),
  avatarY: document.getElementById("avatarY"),
  avatarWidthLabel: document.getElementById("avatarWidthLabel"),
  avatarWidth: document.getElementById("avatarWidth"),
  avatarHeightLabel: document.getElementById("avatarHeightLabel"),
  avatarHeight: document.getElementById("avatarHeight"),
  
  // Text Tab
  roleMode: document.getElementById("roleMode"),
  textList: document.getElementById("textList"),
  fieldName: document.getElementById("fieldName"),
  textValue: document.getElementById("textValue"),
  fontFamily: document.getElementById("fontFamily"),
  fontSize: document.getElementById("fontSize"),
  fontColor: document.getElementById("fontColor"),
  anchor: document.getElementById("anchor"),
  textX: document.getElementById("textX"),
  textY: document.getElementById("textY"),
  maxWidth: document.getElementById("maxWidth"),
  lineHeight: document.getElementById("lineHeight"),
  snapEnabled: document.getElementById("snapEnabled"),
  gridSize: document.getElementById("gridSize"),
  
  // Workspace / View controls
  previewZoom: document.getElementById("previewZoom"),
  zoomValue: document.getElementById("zoomValue"),
  resetZoom: document.getElementById("resetZoom"),
  
  // Export Tab
  layoutName: document.getElementById("layoutName"),
  jsonOutput: document.getElementById("jsonOutput"),
  loadSample: document.getElementById("loadSample"),
  downloadPng: document.getElementById("downloadPng"),
  downloadPackage: document.getElementById("downloadPackage")
};

// --- Default Values & Presets ---
const FIELD_PRESETS = {
  master: [
    // field, value, x, y, size, color, family, anchor, maxWidth, lineHeight
    ["name", "Character Name", 180, 220, 126, "#ff1b16", "Georgia", "ls", 720, 132],
    ["role", "Master", 430, 450, 70, "#f5f5f5", "Georgia", "ms", 420, 78],
    ["username", "@username", 430, 525, 52, "#f5f5f5", "Courier New", "ms", 420, 58],
    ["affiliation", "Affiliation", 1380, 735, 56, "#f5f5f5", "Courier New", "rs", 560, 62],
    ["occupation", "Occupation", 1380, 820, 56, "#f5f5f5", "Courier New", "rs", 560, 62],
    ["alignment", "Alignment", 1380, 905, 56, "#f5f5f5", "Courier New", "rs", 560, 62],
    ["footer_text", "Footer Text", 800, 970, 42, "#f5f5f5", "Courier New", "mm", 900, 48]
  ],
  servant: [
    ["name", "Character Name", 180, 220, 126, "#ff1b16", "Georgia", "ls", 720, 132],
    ["role", "Servant", 430, 450, 70, "#f5f5f5", "Georgia", "ms", 420, 78],
    ["username", "@username", 430, 525, 52, "#f5f5f5", "Courier New", "ms", 420, 58],
    ["class", "Class", 1380, 735, 56, "#f5f5f5", "Courier New", "rs", 560, 62],
    ["nationality", "Nationality", 1380, 820, 56, "#f5f5f5", "Courier New", "rs", 560, 62],
    ["alignment", "Alignment", 1380, 905, 56, "#f5f5f5", "Courier New", "rs", 560, 62],
    ["footer_text", "Footer Text", 800, 970, 42, "#f5f5f5", "Courier New", "mm", 900, 48]
  ]
};
