const DESIGN_WIDTH = 1600;
const DESIGN_HEIGHT = 1000;
const ASPECT = 8 / 5;
const ASPECT_TOLERANCE = 0.0025;

const canvas = document.getElementById("cardCanvas");
const ctx = canvas.getContext("2d");
const statusText = document.getElementById("statusText");

const controls = {
  packageImport: document.getElementById("packageImport"),
  assetRoleMode: document.getElementById("assetRoleMode"),
  baseUpload: document.getElementById("baseUpload"),
  fontUpload: document.getElementById("fontUpload"),
  layerList: document.getElementById("layerList"),
  layerOpacity: document.getElementById("layerOpacity"),
  layerVisible: document.getElementById("layerVisible"),
  removeLayer: document.getElementById("removeLayer"),
  moveLayerUp: document.getElementById("moveLayerUp"),
  moveLayerDown: document.getElementById("moveLayerDown"),
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
  nudgeStep: document.getElementById("nudgeStep"),
  previewZoom: document.getElementById("previewZoom"),
  zoomValue: document.getElementById("zoomValue"),
  resetZoom: document.getElementById("resetZoom"),
  layoutName: document.getElementById("layoutName"),
  jsonOutput: document.getElementById("jsonOutput"),
  loadSample: document.getElementById("loadSample"),
  downloadPng: document.getElementById("downloadPng"),
  downloadPackage: document.getElementById("downloadPackage"),
  copyJson: document.getElementById("copyJson")
};

const FIELD_PRESETS = {
  master: [
    ["name", "Character Name", 180, 220, 126, "#ff1b16", "Caveat, Georgia, serif", "la", 720, 132],
    ["role", "Master", 430, 450, 70, "#f5f5f5", "Georgia", "ma", 420, 78],
    ["username", "@username", 430, 525, 52, "#f5f5f5", "Courier New", "ma", 420, 58],
    ["affiliation", "Affiliation", 1380, 735, 56, "#f5f5f5", "Courier New", "ra", 560, 62],
    ["occupation", "Occupation", 1380, 820, 56, "#f5f5f5", "Courier New", "ra", 560, 62],
    ["alignment", "Alignment", 1380, 905, 56, "#f5f5f5", "Courier New", "ra", 560, 62],
    ["footer_text", "Footer Text", 800, 970, 42, "#f5f5f5", "Courier New", "mm", 900, 48]
  ],
  servant: [
    ["name", "Character Name", 180, 220, 126, "#ff1b16", "Caveat, Georgia, serif", "la", 720, 132],
    ["role", "Servant", 430, 450, 70, "#f5f5f5", "Georgia", "ma", 420, 78],
    ["username", "@username", 430, 525, 52, "#f5f5f5", "Courier New", "ma", 420, 58],
    ["class", "Class", 1380, 735, 56, "#f5f5f5", "Courier New", "ra", 560, 62],
    ["nationality", "Nationality", 1380, 820, 56, "#f5f5f5", "Courier New", "ra", 560, 62],
    ["alignment", "Alignment", 1380, 905, 56, "#f5f5f5", "Courier New", "ra", 560, 62],
    ["footer_text", "Footer Text", 800, 970, 42, "#f5f5f5", "Courier New", "mm", 900, 48]
  ]
};

const state = {
  roleMode: "master",
  layersByRole: {
    master: [],
    servant: []
  },
  selectedLayerIdByRole: {
    master: null,
    servant: null
  },
  textByRole: {
    master: [],
    servant: []
  },
  selectedTextId: null,
  fonts: [
    { label: "Arial", family: "Arial" },
    { label: "Georgia", family: "Georgia" },
    { label: "Trebuchet MS", family: "Trebuchet MS" },
    { label: "Courier New", family: "Courier New" }
  ],
  draggingTextId: null,
  dragOffset: { x: 0, y: 0 },
  previewZoom: 1
};

function uid(prefix) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function setStatus(message) {
  statusText.textContent = message;
}

function updatePreviewZoom() {
  const fitWidth = Math.min(canvas.parentElement.clientWidth - 36, (canvas.parentElement.clientHeight - 36) * ASPECT);
  const safeFitWidth = Math.max(320, Math.floor(fitWidth));
  canvas.style.setProperty("--preview-fit-width", `${safeFitWidth}px`);
  canvas.style.setProperty("--preview-zoom", state.previewZoom);
  controls.zoomValue.textContent = state.previewZoom === 1 ? "Fit" : `${Math.round(state.previewZoom * 100)}%`;
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

function createSampleImage() {
  const sample = document.createElement("canvas");
  sample.width = DESIGN_WIDTH;
  sample.height = DESIGN_HEIGHT;
  const sampleCtx = sample.getContext("2d");

  const sky = sampleCtx.createLinearGradient(0, 0, 0, DESIGN_HEIGHT);
  sky.addColorStop(0, "#101522");
  sky.addColorStop(0.55, "#1a2532");
  sky.addColorStop(1, "#0f1218");
  sampleCtx.fillStyle = sky;
  sampleCtx.fillRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT);

  sampleCtx.fillStyle = "rgba(255,255,255,0.85)";
  for (let i = 0; i < 180; i += 1) {
    const x = Math.random() * DESIGN_WIDTH;
    const y = Math.random() * DESIGN_HEIGHT * 0.52;
    const r = Math.random() * 1.8 + 0.4;
    sampleCtx.beginPath();
    sampleCtx.arc(x, y, r, 0, Math.PI * 2);
    sampleCtx.fill();
  }

  sampleCtx.fillStyle = "#14181d";
  sampleCtx.beginPath();
  sampleCtx.moveTo(0, 510);
  for (let x = 0; x <= DESIGN_WIDTH; x += 80) {
    sampleCtx.lineTo(x, 470 + Math.sin(x / 90) * 24 + Math.random() * 20);
  }
  sampleCtx.lineTo(DESIGN_WIDTH, DESIGN_HEIGHT);
  sampleCtx.lineTo(0, DESIGN_HEIGHT);
  sampleCtx.closePath();
  sampleCtx.fill();

  const lake = sampleCtx.createLinearGradient(0, 520, 0, DESIGN_HEIGHT);
  lake.addColorStop(0, "rgba(47, 67, 83, 0.62)");
  lake.addColorStop(1, "rgba(12, 16, 22, 0.92)");
  sampleCtx.fillStyle = lake;
  sampleCtx.fillRect(0, 520, DESIGN_WIDTH, DESIGN_HEIGHT - 520);

  return sample;
}

function loadSample() {
  const masterImage = createSampleImage();
  const servantImage = createSampleImage();
  state.layersByRole.master = [{
    id: uid("layer"),
    name: "sample_master_base_8x5.png",
    image: masterImage,
    opacity: 1,
    visible: true,
    file: null,
    extension: "png"
  }];
  state.layersByRole.servant = [{
    id: uid("layer"),
    name: "sample_servant_base_8x5.png",
    image: servantImage,
    opacity: 1,
    visible: true,
    file: null,
    extension: "png"
  }];
  state.selectedLayerIdByRole.master = state.layersByRole.master[0].id;
  state.selectedLayerIdByRole.servant = state.layersByRole.servant[0].id;
  setStatus("Loaded sample 8:5 base images for both roles.");
  syncLayerList();
  render();
}

function addDefaultText() {
  state.textByRole.master = FIELD_PRESETS.master.map((preset) => textElement(...preset));
  state.textByRole.servant = FIELD_PRESETS.servant.map((preset) => textElement(...preset));
  state.selectedTextId = activeText()[0].id;
}

function textElement(field, value, x, y, size, color, family, anchor, maxWidth, lineHeight) {
  return {
    id: uid("text"),
    field,
    value,
    x,
    y,
    fontFamily: family,
    fontSize: size,
    color,
    anchor,
    maxWidth,
    lineHeight
  };
}

function syncFontSelect() {
  controls.fontFamily.innerHTML = "";
  state.fonts.forEach((font) => {
    const option = document.createElement("option");
    option.value = font.family;
    option.textContent = font.label;
    controls.fontFamily.appendChild(option);
  });
}

function syncLayerList() {
  controls.layerList.innerHTML = "";
  const layers = activeLayers();
  const names = exportLayerNames(state.roleMode);
  layers.forEach((layer, index) => {
    const option = document.createElement("option");
    option.value = layer.id;
    option.textContent = `${layer.visible ? "shown" : "hidden"}  ${Math.round(layer.opacity * 100)}%  ${names[index]?.path || layer.name}`;
    option.selected = layer.id === selectedLayerId();
    controls.layerList.appendChild(option);
  });
  const layer = selectedLayer();
  controls.layerOpacity.value = layer ? Math.round(layer.opacity * 100) : 100;
  controls.layerVisible.checked = layer ? layer.visible !== false : false;
}

function syncTextList() {
  controls.textList.innerHTML = "";
  activeText().forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.field}: ${item.value}`;
    option.selected = item.id === state.selectedTextId;
    controls.textList.appendChild(option);
  });
  syncTextControls();
}

function syncTextControls() {
  const item = selectedText();
  const disabled = !item;
  [
    controls.fieldName,
    controls.textValue,
    controls.fontFamily,
    controls.fontSize,
    controls.fontColor,
    controls.anchor,
    controls.textX,
    controls.textY,
    controls.maxWidth,
    controls.lineHeight
  ].forEach((control) => {
    control.disabled = disabled;
  });

  if (!item) {
    return;
  }

  controls.fieldName.value = item.field;
  controls.textValue.value = item.value;
  controls.fontFamily.value = item.fontFamily;
  controls.fontSize.value = item.fontSize;
  controls.fontColor.value = item.color;
  controls.anchor.value = item.anchor;
  controls.textX.value = Math.round(item.x);
  controls.textY.value = Math.round(item.y);
  controls.maxWidth.value = item.maxWidth || 0;
  controls.lineHeight.value = item.lineHeight || item.fontSize;
}

function selectedLayer() {
  return activeLayers().find((layer) => layer.id === selectedLayerId());
}

function selectedLayerId() {
  return state.selectedLayerIdByRole[state.roleMode];
}

function setSelectedLayerId(id) {
  state.selectedLayerIdByRole[state.roleMode] = id;
}

function activeLayers() {
  return state.layersByRole[state.roleMode];
}

function selectedText() {
  return activeText().find((item) => item.id === state.selectedTextId);
}

function activeText() {
  return state.textByRole[state.roleMode];
}

function imageFromFile(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error(`Could not load ${file.name}`));
    };
    image.src = url;
  });
}

function imageFromBlob(blob, name) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error(`Could not load ${name}`));
    };
    image.src = url;
  });
}

async function handleBaseUpload(event) {
  const files = [...event.target.files];
  let accepted = 0;
  for (const file of files) {
    try {
      const image = await imageFromFile(file);
      const ratio = image.naturalWidth / image.naturalHeight;
      if (Math.abs(ratio - ASPECT) > ASPECT_TOLERANCE) {
        setStatus(`Rejected ${file.name}: image must be 8:5.`);
        continue;
      }

      const layer = {
        id: uid("layer"),
        name: file.name,
        image,
        opacity: 1,
        visible: true,
        file,
        extension: extensionFor(file.name, "png")
      };
      activeLayers().push(layer);
      setSelectedLayerId(layer.id);
      accepted += 1;
    } catch (error) {
      setStatus(error.message);
    }
  }
  if (accepted) {
    setStatus(`Added ${accepted} 8:5 image layer${accepted === 1 ? "" : "s"}.`);
  }
  controls.baseUpload.value = "";
  syncLayerList();
  render();
}

async function handleFontUpload(event) {
  const files = [...event.target.files];
  let loaded = 0;
  for (const file of files) {
    const family = `Uploaded_${file.name.replace(/[^a-z0-9]/gi, "_")}_${Date.now()}`;
    const url = URL.createObjectURL(file);
    try {
      const fontFace = new FontFace(family, `url(${url})`);
      await fontFace.load();
      document.fonts.add(fontFace);
      state.fonts.push({ label: file.name, family, file });
      loaded += 1;
    } catch {
      setStatus(`Could not load font ${file.name}.`);
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  if (loaded) {
    setStatus(`Loaded ${loaded} font${loaded === 1 ? "" : "s"}.`);
  }
  controls.fontUpload.value = "";
  syncFontSelect();
  syncTextControls();
  render();
}

function drawBase() {
  ctx.clearRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT);
  ctx.fillStyle = "#141414";
  ctx.fillRect(0, 0, DESIGN_WIDTH, DESIGN_HEIGHT);

  activeLayers().filter((layer) => layer.visible !== false).forEach((layer) => {
    ctx.save();
    ctx.globalAlpha = layer.opacity;
    ctx.drawImage(layer.image, 0, 0, DESIGN_WIDTH, DESIGN_HEIGHT);
    ctx.restore();
  });
}

function canvasFont(item) {
  return `${item.fontSize}px ${quoteFont(item.fontFamily)}`;
}

function quoteFont(family) {
  if (family.includes(",")) {
    return family;
  }
  if (family.startsWith("Uploaded_") || /\s/.test(family)) {
    return `"${family}"`;
  }
  return family;
}

function anchorPoint(item) {
  const anchor = item.anchor || "la";
  const horizontal = anchor[0] || "l";
  const vertical = anchor[1] || "a";
  return { horizontal, vertical };
}

function applyAnchor(item) {
  const { horizontal, vertical } = anchorPoint(item);
  ctx.textAlign = horizontal === "m" ? "center" : horizontal === "r" ? "right" : "left";
  ctx.textBaseline = vertical === "t" ? "top" : vertical === "m" ? "middle" : "alphabetic";
}

function wrapLines(item) {
  const maxWidth = Number(item.maxWidth) || 0;
  if (!maxWidth) {
    return String(item.value).split("\n");
  }

  const lines = [];
  const input = String(item.value).split("\n");
  input.forEach((line) => {
    const words = line.split(/\s+/).filter(Boolean);
    let current = "";
    words.forEach((word) => {
      const test = current ? `${current} ${word}` : word;
      if (ctx.measureText(test).width <= maxWidth || !current) {
        current = test;
      } else {
        lines.push(current);
        current = word;
      }
    });
    if (current) {
      lines.push(current);
    }
  });
  return lines.length ? lines : [""];
}

function drawTextItem(item, selected = false) {
  ctx.save();
  ctx.font = canvasFont(item);
  ctx.fillStyle = item.color;
  applyAnchor(item);

  const lines = wrapLines(item);
  const lineHeight = Number(item.lineHeight) || Number(item.fontSize);
  lines.forEach((line, index) => {
    ctx.fillText(line, item.x, item.y + index * lineHeight);
  });

  if (selected) {
    const box = textBounds(item, lines);
    ctx.strokeStyle = "#7db7ff";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    ctx.strokeRect(box.x, box.y, box.width, box.height);
  }
  ctx.restore();
}

function textBounds(item, lines = null) {
  ctx.save();
  ctx.font = canvasFont(item);
  const renderedLines = lines || wrapLines(item);
  const lineHeight = Number(item.lineHeight) || Number(item.fontSize);
  const width = Math.max(...renderedLines.map((line) => ctx.measureText(line).width), 1);
  const height = Math.max(lineHeight * renderedLines.length, Number(item.fontSize));
  const { horizontal, vertical } = anchorPoint(item);
  let x = item.x;
  let y = item.y;

  if (horizontal === "m") x -= width / 2;
  if (horizontal === "r") x -= width;
  if (vertical === "m") y -= height / 2;
  if (vertical === "a") y -= Number(item.fontSize);

  ctx.restore();
  return { x, y, width, height };
}

function render() {
  updatePreviewZoom();
  drawBase();
  activeText().forEach((item) => {
    drawTextItem(item, item.id === state.selectedTextId);
  });
  updateJson();
}

function updateJson() {
  controls.jsonOutput.value = JSON.stringify(buildLayoutConfig(), null, 2);
}

function buildLayoutConfig() {
  const fonts = {};
  const templates = {};
  const designName = safeStem(controls.layoutName.value.trim() || "custom_card");

  Object.entries(state.textByRole).forEach(([role, items]) => {
    const text = {};
    const exportedLayers = exportLayerNames(role, designName);
    items.forEach((item) => {
      const fontKey = fontKeyFor(item, role);
      fonts[fontKey] = {
        path: fontPathFor(item),
        size: Number(item.fontSize),
        color: hexToRgba(item.color)
      };
      text[item.field] = {
        x: Math.round(item.x),
        y: Math.round(item.y),
        font: fontKey,
        anchor: item.anchor
      };
      if (Number(item.maxWidth)) text[item.field].max_width = Number(item.maxWidth);
      if (Number(item.lineHeight)) text[item.field].line_height = Number(item.lineHeight);
    });
    templates[role] = {
      layers: {
        image_layers: exportedLayers.map((layer) => ({
          path: layer.path,
          fit: "stretch",
          opacity: layer.opacity
        }))
      },
      text
    };
  });

  return {
    canvas: {
      width: DESIGN_WIDTH,
      height: DESIGN_HEIGHT
    },
    layers: {},
    fonts,
    avatar: {
      x: 1010,
      y: 70,
      size: 520,
      shape: "circle"
    },
    templates
  };
}

function fontKeyFor(item, role) {
  const raw = `${role}_${item.field || item.fontFamily || "text"}`;
  return raw.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "text";
}

function fontPathFor(item) {
  const font = state.fonts.find((entry) => entry.family === item.fontFamily);
  if (font?.file) {
    return safeFileName(font.file.name);
  }
  return `${safeFileName(item.fontFamily)}.ttf`;
}

function hexToRgba(hex) {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
    255
  ];
}

function removeSelectedLayer() {
  if (!selectedLayerId()) return;
  state.layersByRole[state.roleMode] = activeLayers().filter((layer) => layer.id !== selectedLayerId());
  setSelectedLayerId(activeLayers()[0]?.id || null);
  syncLayerList();
  render();
}

function moveSelectedLayer(direction) {
  const layers = activeLayers();
  const index = layers.findIndex((layer) => layer.id === selectedLayerId());
  if (index === -1) return;
  const target = index + direction;
  if (target < 0 || target >= layers.length) return;
  const [layer] = layers.splice(index, 1);
  layers.splice(target, 0, layer);
  syncLayerList();
  render();
}

function exportLayerNames(role, designName = safeStem(controls.layoutName.value.trim() || "custom_card")) {
  const visibleLayers = state.layersByRole[role].filter((layer) => layer.visible !== false);
  return visibleLayers.map((layer, index) => {
    const order = String(index + 1).padStart(2, "0");
    const layerRole = index === 0 ? "background" : index === visibleLayers.length - 1 ? "foreground" : "overlay";
    const stem = safeStem(layer.name || `layer_${order}`);
    const ext = layer.extension || extensionFor(layer.name, "png");
    return {
      id: layer.id,
      path: `${role}/${order}_${layerRole}_${stem}.${ext}`,
      opacity: Number(layer.opacity.toFixed(3))
    };
  });
}

function safeStem(name) {
  return name
    .replace(/\.[^.]+$/, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "") || "asset";
}

function safeFileName(name) {
  const parts = name.split(".");
  const ext = parts.length > 1 ? parts.pop().toLowerCase().replace(/[^a-z0-9]/g, "") : "";
  const stem = safeStem(parts.join(".") || name);
  return ext ? `${stem}.${ext}` : stem;
}

function extensionFor(name, fallback) {
  const match = /\.([a-z0-9]+)$/i.exec(name || "");
  return match ? match[1].toLowerCase() : fallback;
}

function textFromConfig(role, config, fontFamilies) {
  const defaults = new Map(FIELD_PRESETS[role].map((preset) => [preset[0], preset]));
  const textConfig = config.templates?.[role]?.text || {};

  return FIELD_PRESETS[role].map((preset) => {
    const [field] = preset;
    const item = textElement(...preset);
    const cfg = textConfig[field];
    if (!cfg) {
      return item;
    }

    const fontCfg = config.fonts?.[cfg.font] || {};
    item.x = Number(cfg.x ?? item.x);
    item.y = Number(cfg.y ?? item.y);
    item.anchor = cfg.anchor || item.anchor;
    item.maxWidth = Number(cfg.max_width || item.maxWidth || 0);
    item.lineHeight = Number(cfg.line_height || fontCfg.size || item.lineHeight || item.fontSize);
    item.fontSize = Number(fontCfg.size || item.fontSize);
    item.color = rgbaToHex(fontCfg.color) || item.color;
    item.fontFamily = fontFamilies.get(fontCfg.path) || fontFamilies.get(cfg.font) || item.fontFamily;
    item.value = defaults.get(field)?.[1] || item.value;
    return item;
  });
}

function rgbaToHex(color) {
  if (!Array.isArray(color) || color.length < 3) {
    return null;
  }
  return `#${color.slice(0, 3).map((value) => Number(value).toString(16).padStart(2, "0")).join("")}`;
}

function updateSelectedTextFromControls() {
  const item = selectedText();
  if (!item) return;
  item.value = controls.textValue.value;
  item.fontFamily = controls.fontFamily.value;
  item.fontSize = Number(controls.fontSize.value);
  item.color = controls.fontColor.value;
  item.anchor = controls.anchor.value;
  item.x = clamp(snapValue(Number(controls.textX.value)), 0, DESIGN_WIDTH);
  item.y = clamp(snapValue(Number(controls.textY.value)), 0, DESIGN_HEIGHT);
  item.maxWidth = Number(controls.maxWidth.value);
  item.lineHeight = Number(controls.lineHeight.value);
  refreshSelectedTextOption();
  render();
}

function refreshSelectedTextOption() {
  const item = selectedText();
  if (!item) return;
  const option = [...controls.textList.options].find((entry) => entry.value === item.id);
  if (option) {
    option.textContent = `${item.field}: ${item.value}`;
  }
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function snapValue(value) {
  if (!controls.snapEnabled.checked) {
    return value;
  }
  const grid = Math.max(1, Number(controls.gridSize.value) || 1);
  return Math.round(value / grid) * grid;
}

function moveSelectedText(dx, dy) {
  const item = selectedText();
  if (!item) return;
  const step = Math.max(1, Number(controls.nudgeStep.value) || 1);
  item.x = clamp(snapValue(item.x + dx * step), 0, DESIGN_WIDTH);
  item.y = clamp(snapValue(item.y + dy * step), 0, DESIGN_HEIGHT);
  syncTextControls();
  render();
}

function canvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * DESIGN_WIDTH,
    y: ((event.clientY - rect.top) / rect.height) * DESIGN_HEIGHT
  };
}

function hitTestText(point) {
  const items = activeText();
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i];
    const box = textBounds(item);
    if (
      point.x >= box.x &&
      point.x <= box.x + box.width &&
      point.y >= box.y &&
      point.y <= box.y + box.height
    ) {
      return item;
    }
  }
  return null;
}

function onPointerDown(event) {
  const point = canvasPoint(event);
  const item = hitTestText(point);
  if (!item) return;
  state.selectedTextId = item.id;
  state.draggingTextId = item.id;
  state.dragOffset.x = point.x - item.x;
  state.dragOffset.y = point.y - item.y;
  canvas.classList.add("dragging");
  syncTextList();
  render();
}

function onPointerMove(event) {
  if (!state.draggingTextId) return;
  const item = selectedText();
  if (!item) return;
  const point = canvasPoint(event);
  item.x = clamp(point.x - state.dragOffset.x, 0, DESIGN_WIDTH);
  item.y = clamp(point.y - state.dragOffset.y, 0, DESIGN_HEIGHT);
  item.x = snapValue(item.x);
  item.y = snapValue(item.y);
  syncTextControls();
  render();
}

function onPointerUp() {
  state.draggingTextId = null;
  canvas.classList.remove("dragging");
}

function downloadPng() {
  const link = document.createElement("a");
  const name = controls.layoutName.value.trim() || "card_preview";
  link.download = `${name}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}

async function downloadPackage() {
  updateJson();
  const name = safeStem(controls.layoutName.value.trim() || "custom_card");
  const files = [];
  const layerNamesByRole = {
    master: exportLayerNames("master", name),
    servant: exportLayerNames("servant", name)
  };

  files.push({
    name: `designs/${name}/config.json`,
    data: stringBytes(controls.jsonOutput.value)
  });

  for (const role of ["master", "servant"]) {
    files.push({
      name: `preview/${name}_${role}_preview.png`,
      data: new Uint8Array(await previewBlobForRole(role).then((blob) => blob.arrayBuffer()))
    });
  }

  for (const role of ["master", "servant"]) {
    for (const layerInfo of layerNamesByRole[role]) {
      const layer = state.layersByRole[role].find((item) => item.id === layerInfo.id);
      files.push({
        name: `designs/${name}/${layerInfo.path}`,
        data: new Uint8Array(await layerBlob(layer).then((blob) => blob.arrayBuffer()))
      });
    }
  }

  for (const font of state.fonts.filter((entry) => entry.file)) {
    files.push({
      name: `fonts/${safeFileName(font.file.name)}`,
      data: new Uint8Array(await font.file.arrayBuffer())
    });
  }

  files.push({
    name: "manifest.json",
    data: stringBytes(JSON.stringify(buildManifest(name, layerNamesByRole), null, 2))
  });

  const zip = buildZip(files);
  triggerDownload(`${name}_card_design.zip`, zip);
  setStatus(`Exported ${files.length} files in ${name}_card_design.zip.`);
}

async function importPackage(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const entries = readZipEntries(new Uint8Array(await file.arrayBuffer()));
    const configEntry = entries.find((entry) => /^designs\/[^/]+\/config\.json$/i.test(entry.name));
    if (!configEntry) {
      throw new Error("Package does not contain designs/*/config.json.");
    }

    const config = JSON.parse(new TextDecoder().decode(configEntry.data));
    const designDir = designDirFromConfigEntry(configEntry.name);
    const fontFamilies = await importFontsFromEntries(entries);
    state.textByRole.master = textFromConfig("master", config, fontFamilies);
    state.textByRole.servant = textFromConfig("servant", config, fontFamilies);

    for (const role of ["master", "servant"]) {
      state.layersByRole[role] = await layersFromConfig(role, config, entries, designDir);
      state.selectedLayerIdByRole[role] = state.layersByRole[role][0]?.id || null;
    }

    controls.layoutName.value = designNameFromConfigEntry(configEntry.name);
    state.roleMode = "master";
    controls.roleMode.value = state.roleMode;
    controls.assetRoleMode.value = state.roleMode;
    state.selectedTextId = activeText()[0]?.id || null;
    syncFontSelect();
    syncTextList();
    syncLayerList();
    render();
    setStatus(`Imported ${file.name}.`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    controls.packageImport.value = "";
  }
}

async function importFontsFromEntries(entries) {
  const families = new Map();
  for (const entry of entries.filter((item) => /^fonts\/.+\.(ttf|otf|woff2?)$/i.test(item.name))) {
    const family = `Uploaded_${safeStem(entry.name)}_${Date.now()}`;
    const blob = new Blob([entry.data]);
    const url = URL.createObjectURL(blob);
    try {
      const fontFace = new FontFace(family, `url(${url})`);
      await fontFace.load();
      document.fonts.add(fontFace);
      const label = entry.name.split("/").pop();
      const file = new File([blob], label);
      state.fonts.push({ label, family, file });
      families.set(entry.name, family);
      families.set(entry.name.replace(/^fonts\//, ""), family);
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  return families;
}

async function layersFromConfig(role, config, entries, designDir = null) {
  const layerConfigs = config.templates?.[role]?.layers?.image_layers || config.layers?.image_layers || [];
  const layers = [];
  for (const cfg of layerConfigs) {
    const entry = entries.find((item) => {
      const entryPath = normalizePath(item.name);
      const cfgPath = normalizePath(cfg.path);
      return (
        entryPath === cfgPath ||
        (designDir && entryPath === `${designDir}/${cfgPath}`)
      );
    });
    if (!entry) {
      continue;
    }
    const blob = new Blob([entry.data]);
    const image = await imageFromBlob(blob, entry.name);
    const name = entry.name.split("/").pop();
    layers.push({
      id: uid("layer"),
      name,
      image,
      opacity: Number(cfg.opacity ?? 1),
      visible: true,
      file: new File([blob], name),
      extension: extensionFor(name, "png")
    });
  }
  return layers;
}

function normalizePath(path) {
  return String(path).replace(/\\/g, "/").replace(/^\.?\//, "");
}

function designDirFromConfigEntry(path) {
  const normalized = normalizePath(path);
  const match = /^designs\/([^/]+)\/config\.json$/i.exec(normalized);
  return match ? `designs/${match[1]}` : null;
}

function designNameFromConfigEntry(path) {
  const normalized = normalizePath(path);
  const match = /^designs\/([^/]+)\/config\.json$/i.exec(normalized);
  if (match) {
    return match[1];
  }
  return safeStem(normalized.split("/").pop().replace(/\.json$/i, ""));
}

function buildManifest(name, layerNamesByRole) {
  return {
    package: name,
    canvas: {
      width: DESIGN_WIDTH,
      height: DESIGN_HEIGHT,
      ratio: "8:5"
    },
    config: `designs/${name}/config.json`,
    previews: {
      master: `preview/${name}_master_preview.png`,
      servant: `preview/${name}_servant_preview.png`
    },
    layers: layerNamesByRole,
    fonts: state.fonts
      .filter((font) => font.file)
      .map((font) => ({
        original_name: font.file.name,
        path: `fonts/${safeFileName(font.file.name)}`
      })),
    notes: [
      "Layer order is bottom to top.",
      "Layer paths in config are relative to the design folder.",
      "Hidden layers are not included in config or package exports.",
      "Layer filenames begin with 01, 02, 03 so file browsing preserves draw order.",
      "Copy the designs and fonts folders into character-compendium before using the config."
    ]
  };
}

function canvasBlob() {
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

async function previewBlobForRole(role) {
  const previousRole = state.roleMode;
  const previousTextId = state.selectedTextId;
  state.roleMode = role;
  state.selectedTextId = activeText()[0]?.id || null;
  render();
  const blob = await canvasBlob();
  state.roleMode = previousRole;
  state.selectedTextId = previousTextId;
  controls.roleMode.value = state.roleMode;
  controls.assetRoleMode.value = state.roleMode;
  syncTextList();
  syncLayerList();
  render();
  return blob;
}

function layerBlob(layer) {
  if (layer.file) {
    return Promise.resolve(layer.file);
  }

  return new Promise((resolve) => {
    const layerCanvas = document.createElement("canvas");
    layerCanvas.width = DESIGN_WIDTH;
    layerCanvas.height = DESIGN_HEIGHT;
    const layerCtx = layerCanvas.getContext("2d");
    layerCtx.drawImage(layer.image, 0, 0, DESIGN_WIDTH, DESIGN_HEIGHT);
    layerCanvas.toBlob(resolve, "image/png");
  });
}

function triggerDownload(name, blob) {
  const link = document.createElement("a");
  link.download = name;
  link.href = URL.createObjectURL(blob);
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 500);
}

function stringBytes(value) {
  return new TextEncoder().encode(value);
}

function buildZip(files) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  files.forEach((file) => {
    const nameBytes = stringBytes(file.name);
    const data = file.data;
    const crc = crc32(data);

    const local = new Uint8Array(30 + nameBytes.length);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034b50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0, true);
    localView.setUint16(8, 0, true);
    localView.setUint16(10, 0, true);
    localView.setUint16(12, 0, true);
    localView.setUint32(14, crc, true);
    localView.setUint32(18, data.length, true);
    localView.setUint32(22, data.length, true);
    localView.setUint16(26, nameBytes.length, true);
    localView.setUint16(28, 0, true);
    local.set(nameBytes, 30);
    localParts.push(local, data);

    const central = new Uint8Array(46 + nameBytes.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014b50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint16(12, 0, true);
    centralView.setUint16(14, 0, true);
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, data.length, true);
    centralView.setUint32(24, data.length, true);
    centralView.setUint16(28, nameBytes.length, true);
    centralView.setUint16(30, 0, true);
    centralView.setUint16(32, 0, true);
    centralView.setUint16(34, 0, true);
    centralView.setUint16(36, 0, true);
    centralView.setUint32(38, 0, true);
    centralView.setUint32(42, offset, true);
    central.set(nameBytes, 46);
    centralParts.push(central);

    offset += local.length + data.length;
  });

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, files.length, true);
  endView.setUint16(10, files.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, offset, true);
  endView.setUint16(20, 0, true);

  return new Blob([...localParts, ...centralParts, end], { type: "application/zip" });
}

function readZipEntries(bytes) {
  const entries = [];
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 0;

  while (offset + 30 <= bytes.length) {
    const signature = view.getUint32(offset, true);
    if (signature !== 0x04034b50) {
      break;
    }

    const method = view.getUint16(offset + 8, true);
    if (method !== 0) {
      throw new Error("Only uncompressed ZIP packages are supported.");
    }

    const compressedSize = view.getUint32(offset + 18, true);
    const nameLength = view.getUint16(offset + 26, true);
    const extraLength = view.getUint16(offset + 28, true);
    const nameStart = offset + 30;
    const dataStart = nameStart + nameLength + extraLength;
    const name = new TextDecoder().decode(bytes.slice(nameStart, nameStart + nameLength));
    const data = bytes.slice(dataStart, dataStart + compressedSize);

    entries.push({ name, data });
    offset = dataStart + compressedSize;
  }

  return entries;
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(data) {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function copyJson() {
  updateJson();
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(controls.jsonOutput.value);
  } else {
    controls.jsonOutput.focus();
    controls.jsonOutput.select();
    document.execCommand("copy");
  }
  setStatus("Copied design config JSON.");
}

function bindEvents() {
  controls.baseUpload.addEventListener("change", handleBaseUpload);
  controls.fontUpload.addEventListener("change", handleFontUpload);
  controls.layerList.addEventListener("change", () => {
    setSelectedLayerId(controls.layerList.value);
    syncLayerList();
    render();
  });
  controls.layerOpacity.addEventListener("input", () => {
    const layer = selectedLayer();
    if (!layer) return;
    layer.opacity = Number(controls.layerOpacity.value) / 100;
    syncLayerList();
    render();
  });
  controls.layerVisible.addEventListener("change", () => {
    const layer = selectedLayer();
    if (!layer) return;
    layer.visible = controls.layerVisible.checked;
    syncLayerList();
    render();
  });
  controls.removeLayer.addEventListener("click", removeSelectedLayer);
  controls.moveLayerUp.addEventListener("click", () => moveSelectedLayer(-1));
  controls.moveLayerDown.addEventListener("click", () => moveSelectedLayer(1));

  controls.roleMode.addEventListener("change", () => {
    state.roleMode = controls.roleMode.value;
    controls.assetRoleMode.value = state.roleMode;
    state.selectedTextId = activeText()[0]?.id || null;
    syncTextList();
    syncLayerList();
    render();
  });
  controls.assetRoleMode.addEventListener("change", () => {
    state.roleMode = controls.assetRoleMode.value;
    controls.roleMode.value = state.roleMode;
    state.selectedTextId = activeText()[0]?.id || null;
    syncTextList();
    syncLayerList();
    render();
  });

  controls.textList.addEventListener("change", () => {
    state.selectedTextId = controls.textList.value;
    syncTextControls();
    render();
  });
  [
    controls.textValue,
    controls.fontFamily,
    controls.fontSize,
    controls.fontColor,
    controls.anchor,
    controls.textX,
    controls.textY,
    controls.maxWidth,
    controls.lineHeight
  ].forEach((control) => {
    control.addEventListener("input", updateSelectedTextFromControls);
  });
  document.querySelectorAll(".nudge-button").forEach((button) => {
    button.addEventListener("click", () => {
      moveSelectedText(Number(button.dataset.dx), Number(button.dataset.dy));
    });
  });
  window.addEventListener("keydown", (event) => {
    if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
    const target = event.target;
    if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return;
    event.preventDefault();
    const delta = {
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0]
    }[event.key];
    moveSelectedText(delta[0], delta[1]);
  });

  controls.loadSample.addEventListener("click", loadSample);
  controls.packageImport.addEventListener("change", importPackage);
  controls.downloadPng.addEventListener("click", downloadPng);
  controls.downloadPackage.addEventListener("click", downloadPackage);
  controls.copyJson.addEventListener("click", copyJson);
  controls.layoutName.addEventListener("input", updateJson);
  controls.previewZoom.addEventListener("input", () => {
    state.previewZoom = Number(controls.previewZoom.value) / 100;
    updatePreviewZoom();
  });
  controls.resetZoom.addEventListener("click", () => {
    state.previewZoom = 1;
    controls.previewZoom.value = 100;
    updatePreviewZoom();
  });
  window.addEventListener("resize", updatePreviewZoom);

  canvas.addEventListener("pointerdown", onPointerDown);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
}

function init() {
  setupTabs();
  controls.roleMode.value = state.roleMode;
  controls.assetRoleMode.value = state.roleMode;
  syncFontSelect();
  addDefaultText();
  loadSample();
  syncTextList();
  bindEvents();
  render();
}

init();
