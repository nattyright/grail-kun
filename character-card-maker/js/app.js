/**
 * Character Card Maker - App Controller
 * 
 * Manages global state, event listeners, and high-level UI interactions.
 */

// --- Application State ---
const state = {
  roleMode: "master",        // "master" or "servant"
  activeTab: "assets",
  layersByRole: {
    master: [],              // Array of layer objects
    servant: []
  },
  selectedLayerIdByRole: {
    master: null,
    servant: null
  },
  textByRole: {
    master: [],              // Array of textElement objects
    servant: []
  },
  selectedTextId: null,
  fonts: [
    { label: "Arial", family: "Arial" },
    { label: "Georgia", family: "Georgia" },
    { label: "Trebuchet MS", family: "Trebuchet MS" },
    { label: "Courier New", family: "Courier New" }
  ],
  avatar: {
    x: 1010,
    y: 70,
    width: 520,
    height: 520,
    shape: "circle",
    image: null              // HTMLImageElement
  },
  dragTarget: null,          // "avatar", "text", or null
  dragOffset: { x: 0, y: 0 },
  previewZoom: 1
};

// --- General Helpers ---

function uid(prefix) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function setStatus(message) {
  statusText.textContent = message;
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

// --- UI Logic & Tab Management ---

function updatePreviewZoom() {
  const fitWidth = Math.min(canvas.parentElement.clientWidth - 36, (canvas.parentElement.clientHeight - 36) * ASPECT);
  const safeFitWidth = Math.max(320, Math.floor(fitWidth));
  canvas.style.setProperty("--preview-fit-width", `${safeFitWidth}px`);
  canvas.style.setProperty("--preview-zoom", state.previewZoom);
  const zoomText = state.previewZoom === 1 ? UI_STRINGS.app.zoomFit : `${Math.round(state.previewZoom * 100)}%`;
  controls.zoomValue.textContent = zoomText;
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
      state.activeTab = tab.dataset.tab;
    });
  });
}

/**
 * Factory for text element objects.
 */
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

function addDefaultText() {
  state.textByRole.master = FIELD_PRESETS.master.map((preset) => textElement(...preset));
  state.textByRole.servant = FIELD_PRESETS.servant.map((preset) => textElement(...preset));
  state.selectedTextId = activeText()[0].id;
}

// --- UI Synchronization ---

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
    const customLabel = layer.customizable === "background" ? "  custom-bg" : "";
    const visibilityLabel = layer.visible ? UI_STRINGS.layers.statusShown : UI_STRINGS.layers.statusHidden;
    option.textContent = `${visibilityLabel}  ${Math.round(layer.opacity * 100)}%${customLabel}  ${names[index]?.path || layer.name}`;
    option.selected = layer.id === selectedLayerId();
    controls.layerList.appendChild(option);
  });
  const layer = selectedLayer();
  controls.layerOpacity.value = layer ? Math.round(layer.opacity * 100) : 100;
  controls.layerVisible.checked = layer ? layer.visible !== false : false;
  controls.layerCustomBackground.checked = layer ? layer.customizable === "background" : false;
  controls.selectedLayerName.textContent = layer ? layer.name : UI_STRINGS.layers.noSelection;
  controls.layerOpacity.disabled = !layer;
  controls.layerVisible.disabled = !layer;
  controls.layerCustomBackground.disabled = !layer;
  controls.removeLayer.disabled = !layer;
  controls.moveLayerUp.disabled = !layer;
  controls.moveLayerDown.disabled = !layer;
}

function syncAvatarControls() {
  const shape = state.avatar.shape || "circle";
  const singleSize = avatarUsesSingleSize(shape);
  controls.avatarShape.value = shape;
  controls.avatarX.value = Math.round(state.avatar.x);
  controls.avatarY.value = Math.round(state.avatar.y);
  controls.avatarWidth.value = Math.round(state.avatar.width);
  controls.avatarHeight.value = Math.round(state.avatar.height);
  controls.avatarWidthLabel.textContent = singleSize ? UI_STRINGS.avatar.size : UI_STRINGS.avatar.width;
  controls.avatarHeightLabel.hidden = singleSize;
  controls.avatarHeight.hidden = singleSize;
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

  if (!item) return;

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

// --- State Accessors ---

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

function avatarUsesSingleSize(shape) {
  return ["circle", "square"].includes(String(shape || "").toLowerCase());
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
    extension: "png",
    customizable: null
  }];
  state.layersByRole.servant = [{
    id: uid("layer"),
    name: "sample_servant_base_8x5.png",
    image: servantImage,
    opacity: 1,
    visible: true,
    file: null,
    extension: "png",
    customizable: null
  }];
  state.selectedLayerIdByRole.master = state.layersByRole.master[0].id;
  state.selectedLayerIdByRole.servant = state.layersByRole.servant[0].id;
  setStatus(UI_STRINGS.app.sampleStatus);
  syncLayerList();
  render();
}

// --- Image & Font Loading ---

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
        setStatus(UI_STRINGS.assets.errorRatio(file.name));
        continue;
      }

      const layer = {
        id: uid("layer"),
        name: file.name,
        image,
        opacity: 1,
        visible: true,
        file,
        extension: extensionFor(file.name, "png"),
        customizable: null
      };
      activeLayers().push(layer);
      setSelectedLayerId(layer.id);
      accepted += 1;
    } catch (error) {
      setStatus(error.message);
    }
  }
  if (accepted) setStatus(UI_STRINGS.assets.statusAddedLayers(accepted));
  controls.baseUpload.value = "";
  syncLayerList();
  render();
}

async function handleAvatarUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    state.avatar.image = await imageFromFile(file);
    setStatus(UI_STRINGS.assets.statusLoadedAvatar(file.name));
  } catch (error) {
    setStatus(error.message);
  } finally {
    controls.avatarUpload.value = "";
  }
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
      setStatus(UI_STRINGS.assets.errorLoadFont(file.name));
    } finally {
      URL.revokeObjectURL(url);
    }
  }
  if (loaded) setStatus(UI_STRINGS.assets.statusLoadedFonts(loaded));
  controls.fontUpload.value = "";
  syncFontSelect();
  syncTextControls();
  render();
}

// --- Import/Export Orchestration ---

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
      const fontKey = fontKeyFor(item);
      if (!fonts[fontKey]) {
        fonts[fontKey] = {
          path: fontPathFor(item),
          size: Number(item.fontSize),
          color: hexToRgba(item.color)
        };
      }
      const textKey = textKeyFor(item);
      text[textKey] = {
        x: Math.round(item.x),
        y: Math.round(item.y),
        font: fontKey,
        anchor: item.anchor
      };
      if (textKey !== item.field) text[textKey].field = item.field;
      if (Number(item.maxWidth)) text[textKey].max_width = Number(item.maxWidth);
      if (Number(item.lineHeight)) text[textKey].line_height = Number(item.lineHeight);
    });
    templates[role] = {
      layers: {
        image_layers: exportedLayers.map((layer) => {
          const cfg = {
            path: layer.path,
            fit: "stretch",
            opacity: layer.opacity
          };
          if (layer.customizable) {
            cfg.id = layer.customizable;
            cfg.customizable = layer.customizable;
          }
          return cfg;
        })
      },
      text
    };
  });

  const avatar = {
    x: Math.round(state.avatar.x),
    y: Math.round(state.avatar.y),
    shape: state.avatar.shape || "circle"
  };
  if (Number(state.avatar.width) === Number(state.avatar.height)) {
    avatar.size = Math.round(state.avatar.width);
  } else {
    avatar.width = Math.round(state.avatar.width);
    avatar.height = Math.round(state.avatar.height);
  }

  return {
    canvas: {
      width: DESIGN_WIDTH,
      height: DESIGN_HEIGHT
    },
    layers: {},
    fonts,
    avatar,
    templates
  };
}

function fontKeyFor(item) {
  const raw = fontGroupKeyFor(item) || item.fontFamily || "text";
  return raw.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "text";
}

function fontGroupKeyFor(item) {
  const key = textKeyFor(item);
  if (["affiliation", "occupation", "class", "nationality", "alignment"].includes(key)) {
    return "detail";
  }
  return key;
}

function textKeyFor(item) {
  return item.field === "footer_text" ? "footer" : item.field;
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

function rgbaToHex(color) {
  if (!Array.isArray(color) || color.length < 3) return null;
  return `#${color.slice(0, 3).map((value) => Number(value).toString(16).padStart(2, "0")).join("")}`;
}

function safeStem(name) {
  return name.replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "asset";
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
      opacity: Number(layer.opacity.toFixed(3)),
      customizable: layer.customizable || null
    };
  });
}

function buildManifest(name, layerNamesByRole) {
  return {
    package: name,
    canvas: { width: DESIGN_WIDTH, height: DESIGN_HEIGHT, ratio: "8:5" },
    config: `designs/${name}/config.json`,
    previews: {
      master: `preview/${name}_master_preview.png`,
      servant: `preview/${name}_servant_preview.png`
    },
    layers: layerNamesByRole,
    fonts: state.fonts.filter((f) => f.file).map((f) => ({
      original_name: f.file.name,
      path: `fonts/${safeFileName(f.file.name)}`
    })),
    notes: UI_STRINGS.export.manifestNotes
  };
}

async function downloadPng() {
  render(false);
  const link = document.createElement("a");
  const name = controls.layoutName.value.trim() || "card_preview";
  link.download = `${name}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
  render(true);
}

async function downloadPackage() {
  updateJson();
  const name = safeStem(controls.layoutName.value.trim() || "custom_card");
  const files = [];
  const layerNamesByRole = {
    master: exportLayerNames("master", name),
    servant: exportLayerNames("servant", name)
  };

  files.push({ name: `designs/${name}/config.json`, data: stringBytes(controls.jsonOutput.value) });

  for (const role of ["master", "servant"]) {
    const blob = await previewBlobForRole(role);
    files.push({ name: `preview/${name}_${role}_preview.png`, data: new Uint8Array(await blob.arrayBuffer()) });
  }

  for (const role of ["master", "servant"]) {
    for (const info of layerNamesByRole[role]) {
      const layer = state.layersByRole[role].find((l) => l.id === info.id);
      const blob = await layerBlob(layer);
      files.push({ name: `designs/${name}/${info.path}`, data: new Uint8Array(await blob.arrayBuffer()) });
    }
  }

  for (const font of state.fonts.filter((f) => f.file)) {
    files.push({ name: `fonts/${safeFileName(font.file.name)}`, data: new Uint8Array(await font.file.arrayBuffer()) });
  }

  files.push({ name: "manifest.json", data: stringBytes(JSON.stringify(buildManifest(name, layerNamesByRole), null, 2)) });

  const zip = buildZip(files);
  triggerDownload(`${name}_card_design.zip`, zip);
  setStatus(UI_STRINGS.export.statusExported(files.length, name));
}

async function importPackage(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const entries = readZipEntries(new Uint8Array(await file.arrayBuffer()));
    const configEntry = entries.find((e) => /^designs\/[^/]+\/config\.json$/i.test(e.name));
    if (!configEntry) throw new Error("Package does not contain designs/*/config.json.");

    const config = JSON.parse(new TextDecoder().decode(configEntry.data));
    if (config.canvas?.width && config.canvas?.height) setCanvasSize(config.canvas.width, config.canvas.height);

    const designDir = configEntry.name.split("/").slice(0, 2).join("/");
    const fontFamilies = await importFontsFromEntries(entries);
    state.avatar = avatarFromConfig(config);
    state.textByRole.master = textFromConfig("master", config, fontFamilies);
    state.textByRole.servant = textFromConfig("servant", config, fontFamilies);

    for (const role of ["master", "servant"]) {
      state.layersByRole[role] = await layersFromConfig(role, config, entries, designDir);
      state.selectedLayerIdByRole[role] = state.layersByRole[role][0]?.id || null;
    }

    controls.layoutName.value = configEntry.name.split("/")[1];
    state.roleMode = "master";
    controls.roleMode.value = state.roleMode;
    controls.assetRoleMode.value = state.roleMode;
    controls.layerRoleMode.value = state.roleMode;
    state.selectedTextId = activeText()[0]?.id || null;
    syncFontSelect();
    syncAvatarControls();
    syncTextList();
    syncLayerList();
    render();
    setStatus(UI_STRINGS.export.statusImported(file.name));
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
    const fontFace = new FontFace(family, `url(${URL.createObjectURL(new Blob([entry.data]))})`);
    await fontFace.load();
    document.fonts.add(fontFace);
    const label = entry.name.split("/").pop();
    state.fonts.push({ label, family, file: new File([entry.data], label) });
    families.set(entry.name, family);
    families.set(label, family);
  }
  return families;
}

async function layersFromConfig(role, config, entries, designDir) {
  const layerConfigs = config.templates?.[role]?.layers?.image_layers || [];
  const layers = [];
  for (const cfg of layerConfigs) {
    const entry = entries.find((e) => e.name === cfg.path || e.name === `${designDir}/${cfg.path}`);
    if (!entry) continue;
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
      extension: extensionFor(name, "png"),
      customizable: cfg.customizable || null
    });
  }
  return layers;
}

function avatarFromConfig(config) {
  const cfg = config.avatar || {};
  const width = Number(cfg.width ?? cfg.size ?? 520);
  const height = Number(cfg.height ?? cfg.size ?? 520);
  return { x: Number(cfg.x ?? 1010), y: Number(cfg.y ?? 70), width, height, shape: cfg.shape || "circle" };
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

function textFromConfig(role, config, fontFamilies) {
  const defaults = new Map(FIELD_PRESETS[role].map((p) => [p[0], p]));
  const textConfig = config.templates?.[role]?.text || {};

  return FIELD_PRESETS[role].map((preset) => {
    const [field] = preset;
    const item = textElement(...preset);
    const cfg = textConfig[field] || textConfig[textKeyFor(item)];
    if (!cfg) return item;

    const fontCfg = config.fonts?.[cfg.font] || {};
    item.x = Number(cfg.x ?? item.x);
    item.y = Number(cfg.y ?? item.y);
    item.anchor = cfg.anchor || item.anchor;
    item.maxWidth = Number(cfg.max_width || 0);
    item.lineHeight = Number(cfg.line_height || fontCfg.size || item.fontSize);
    item.fontSize = Number(fontCfg.size || item.fontSize);
    item.color = rgbaToHex(fontCfg.color) || item.color;
    item.fontFamily = fontFamilies.get(fontCfg.path) || fontFamilies.get(cfg.font) || item.fontFamily;
    return item;
  });
}

function previewBlobForRole(role) {
  const prevRole = state.roleMode;
  state.roleMode = role;
  render(false);
  return new Promise((resolve) => {
    canvas.toBlob((blob) => {
      state.roleMode = prevRole;
      render(true);
      resolve(blob);
    });
  });
}

function layerBlob(layer) {
  if (layer.file) return Promise.resolve(layer.file);
  const temp = document.createElement("canvas");
  temp.width = DESIGN_WIDTH;
  temp.height = DESIGN_HEIGHT;
  temp.getContext("2d").drawImage(layer.image, 0, 0);
  return new Promise((resolve) => temp.toBlob(resolve));
}

function triggerDownload(name, blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 500);
}

// --- User Interaction & Events ---

function updateSelectedTextFromControls() {
  const item = selectedText();
  if (!item) return;
  item.value = controls.textValue.value;
  syncSharedFontSettings(item, {
    fontFamily: controls.fontFamily.value,
    fontSize: Number(controls.fontSize.value),
    color: controls.fontColor.value
  });
  item.anchor = controls.anchor.value;
  item.x = clamp(snapValue(Number(controls.textX.value)), 0, DESIGN_WIDTH);
  item.y = clamp(snapValue(Number(controls.textY.value)), 0, DESIGN_HEIGHT);
  item.maxWidth = Number(controls.maxWidth.value);
  item.lineHeight = Number(controls.lineHeight.value);
  refreshSelectedTextOption();
  render();
}

function syncSharedFontSettings(source, settings) {
  const key = fontKeyFor(source);
  Object.values(state.textByRole).forEach((items) => {
    items.filter((i) => fontKeyFor(i) === key).forEach((m) => {
      m.fontFamily = settings.fontFamily;
      m.fontSize = settings.fontSize;
      m.color = settings.color;
    });
  });
}

function updateAvatarFromControls() {
  state.avatar.shape = controls.avatarShape.value;
  state.avatar.x = clamp(snapValue(Number(controls.avatarX.value)), 0, DESIGN_WIDTH);
  state.avatar.y = clamp(snapValue(Number(controls.avatarY.value)), 0, DESIGN_HEIGHT);
  state.avatar.width = clamp(Number(controls.avatarWidth.value) || 1, 1, DESIGN_WIDTH);
  state.avatar.height = avatarUsesSingleSize(state.avatar.shape) ? state.avatar.width : clamp(Number(controls.avatarHeight.value) || 1, 1, DESIGN_HEIGHT);
  syncAvatarControls();
  render();
}

function refreshSelectedTextOption() {
  const item = selectedText();
  if (!item) return;
  const option = [...controls.textList.options].find((o) => o.value === item.id);
  if (option) option.textContent = `${item.field}: ${item.value}`;
}

function canvasPoint(event) {
  const r = canvas.getBoundingClientRect();
  return { x: ((event.clientX - r.left) / r.width) * DESIGN_WIDTH, y: ((event.clientY - r.top) / r.height) * DESIGN_HEIGHT };
}

function hitTestAvatar(p) {
  if (!state.avatar.image) return false;
  const b = { x: Number(state.avatar.x), y: Number(state.avatar.y), w: Number(state.avatar.width), h: Number(state.avatar.height) };
  return p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;
}

function hitTestText(p) {
  const items = activeText();
  for (let i = items.length - 1; i >= 0; i--) {
    const b = textBounds(items[i]);
    if (p.x >= b.x && p.x <= b.x + b.width && p.y >= b.y && p.y <= b.y + b.height) return items[i];
  }
  return null;
}

function onPointerDown(e) {
  const p = canvasPoint(e);
  if (hitTestAvatar(p)) {
    state.dragTarget = "avatar";
    state.dragOffset = { x: p.x - state.avatar.x, y: p.y - state.avatar.y };
    canvas.classList.add("dragging");
    return;
  }
  const item = hitTestText(p);
  if (!item) return;
  state.selectedTextId = item.id;
  state.dragTarget = "text";
  state.dragOffset = { x: p.x - item.x, y: p.y - item.y };
  canvas.classList.add("dragging");
  syncTextList();
  render();
}

function onPointerMove(e) {
  if (!state.dragTarget) return;
  const p = canvasPoint(e);
  if (state.dragTarget === "avatar") {
    state.avatar.x = snapValue(clamp(p.x - state.dragOffset.x, 0, DESIGN_WIDTH));
    state.avatar.y = snapValue(clamp(p.y - state.dragOffset.y, 0, DESIGN_HEIGHT));
    syncAvatarControls();
  } else {
    const item = selectedText();
    if (!item) return;
    item.x = snapValue(clamp(p.x - state.dragOffset.x, 0, DESIGN_WIDTH));
    item.y = snapValue(clamp(p.y - state.dragOffset.y, 0, DESIGN_HEIGHT));
    syncTextControls();
  }
  render();
}

function onPointerUp() {
  state.dragTarget = null;
  canvas.classList.remove("dragging");
}

function bindEvents() {
  controls.baseUpload.addEventListener("change", handleBaseUpload);
  controls.avatarUpload.addEventListener("change", handleAvatarUpload);
  controls.fontUpload.addEventListener("change", handleFontUpload);
  controls.layerList.addEventListener("change", () => { setSelectedLayerId(controls.layerList.value); syncLayerList(); render(); });
  controls.layerOpacity.addEventListener("input", () => { const l = selectedLayer(); if (l) l.opacity = Number(controls.layerOpacity.value) / 100; syncLayerList(); render(); });
  controls.layerVisible.addEventListener("change", () => { const l = selectedLayer(); if (l) l.visible = controls.layerVisible.checked; syncLayerList(); render(); });
  controls.layerCustomBackground.addEventListener("change", () => {
    const l = selectedLayer();
    if (!l) return;
    if (controls.layerCustomBackground.checked) activeLayers().forEach((i) => { if (i !== l && i.customizable === "background") i.customizable = null; });
    l.customizable = controls.layerCustomBackground.checked ? "background" : null;
    syncLayerList(); render();
  });
  controls.removeLayer.addEventListener("click", () => { if (!selectedLayerId()) return; state.layersByRole[state.roleMode] = activeLayers().filter((l) => l.id !== selectedLayerId()); setSelectedLayerId(activeLayers()[0]?.id || null); syncLayerList(); render(); });
  controls.moveLayerUp.addEventListener("click", () => { const l = activeLayers(); const i = l.findIndex((x) => x.id === selectedLayerId()); if (i > 0) { const [x] = l.splice(i, 1); l.splice(i - 1, 0, x); syncLayerList(); render(); } });
  controls.moveLayerDown.addEventListener("click", () => { const l = activeLayers(); const i = l.findIndex((x) => x.id === selectedLayerId()); if (i !== -1 && i < l.length - 1) { const [x] = l.splice(i, 1); l.splice(i + 1, 0, x); syncLayerList(); render(); } });
  [controls.avatarShape, controls.avatarX, controls.avatarY, controls.avatarWidth, controls.avatarHeight].forEach((c) => c.addEventListener("input", updateAvatarFromControls));
  [controls.roleMode, controls.assetRoleMode, controls.layerRoleMode].forEach((c) => c.addEventListener("change", (e) => {
    state.roleMode = e.target.value;
    controls.roleMode.value = state.roleMode;
    controls.assetRoleMode.value = state.roleMode;
    controls.layerRoleMode.value = state.roleMode;
    state.selectedTextId = activeText()[0]?.id || null;
    syncTextList(); syncLayerList(); render();
  }));
  controls.textList.addEventListener("change", () => { state.selectedTextId = controls.textList.value; syncTextControls(); render(); });
  [controls.textValue, controls.fontFamily, controls.fontSize, controls.fontColor, controls.anchor, controls.textX, controls.textY, controls.maxWidth, controls.lineHeight].forEach((c) => c.addEventListener("input", updateSelectedTextFromControls));
  controls.loadSample.addEventListener("click", loadSample);
  controls.packageImport.addEventListener("change", importPackage);
  controls.downloadPng.addEventListener("click", downloadPng);
  controls.downloadPackage.addEventListener("click", downloadPackage);
  controls.layoutName.addEventListener("input", updateJson);
  controls.previewZoom.addEventListener("input", () => { state.previewZoom = Number(controls.previewZoom.value) / 100; updatePreviewZoom(); });
  controls.resetZoom.addEventListener("click", () => { state.previewZoom = 1; controls.previewZoom.value = 100; updatePreviewZoom(); });
  window.addEventListener("resize", updatePreviewZoom);
  canvas.addEventListener("pointerdown", onPointerDown);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
}

function init() {
  applyUiStrings();
  setupTabs();
  controls.roleMode.value = state.roleMode;
  controls.assetRoleMode.value = state.roleMode;
  controls.layerRoleMode.value = state.roleMode;
  syncFontSelect();
  syncAvatarControls();
  addDefaultText();
  loadSample();
  syncTextList();
  bindEvents();
  render();
}

init();
