/**
 * UI Strings (Localization)
 * 
 * Central source of truth for all user-facing text in the application.
 */
const UI_STRINGS = {
  app: {
    title: "Character Compendium Card Designer",
    tagline: "Drag text and avatar directly on the preview.",
    canvasSizePrefix: "Canvas: ",
    canvasAriaLabel: "Card preview canvas",
    statusReady: "Ready.",
    packageImportLabel: "Import",
    zoomLabel: "Zoom ",
    zoomFit: "Fit",
    sampleButton: "Sample",
    sampleStatus: "Loaded sample base images for both Master and Servant roles."
  },
  tabs: {
    assets: "Assets",
    layers: "Layers",
    avatar: "Avatar",
    text: "Text",
    export: "Export"
  },
  roles: {
    master: "Master",
    servant: "Servant"
  },
  assets: {
    roleLabel: "Selected role",
    roleHint: "Each role has its own base image stack.",
    baseLabel: "Base images",
    baseHint: "Base images are uploaded separately for Master and Servant. Only images with an 8:5 ratio are accepted.",
    avatarLabel: "Avatar preview",
    avatarHint: "Used only in the preview. It is not exported in the design package.",
    fontLabel: "Fonts",
    fontHint: "Uploaded fonts become available in the text controls. Only .ttf fonts are accepted.",
    errorRatio: (name) => `Rejected ${name}: image ratio must match canvas.`,
    errorLoadFont: (name) => `Could not load font ${name}.`,
    statusAddedLayers: (count) => `Added ${count} layer${count === 1 ? "" : "s"}.`,
    statusLoadedAvatar: (name) => `Loaded avatar preview ${name}.`,
    statusLoadedFonts: (count) => `Loaded ${count} font${count === 1 ? "" : "s"}.`
  },
  layers: {
    roleLabel: "Selected role",
    listLabel: "Base image layers",
    listBadge: "Included in export",
    selectedHeading: "Selected base image layer",
    noSelection: "No layer selected",
    moveUp: "Move Layer Up",
    moveDown: "Move Layer Down",
    opacityLabel: "Layer opacity",
    visibleLabel: "Visible in preview and export",
    visibleHint: "When off, the layer is omitted from the exported design package.",
    customBgLabel: "Allow custom image for selected layer",
    customBgHint: "Allows other users to replace this selected layer with their own custom image. (Hint: works best if the selected layer is the background.)",
    removeLayer: "Remove Selected Layer",
    statusShown: "shown",
    statusHidden: "hidden"
  },
  avatar: {
    heading: "Avatar preview",
    badge: "Preview only; omitted in export",
    shape: "Shape",
    x: "X",
    y: "Y",
    width: "Width",
    height: "Height",
    size: "Size",
    shapes: {
      circle: "Circle",
      square: "Square",
      rectangle: "Rectangle",
      diamond: "Diamond",
      oval: "Oval",
      rounded: "Rounded rectangle"
    }
  },
  text: {
    roleLabel: "Selected role",
    listLabel: "Text elements",
    listBadge: "Included in export",
    field: "Field name",
    value: "Text preview",
    font: "Font",
    size: "Size",
    color: "Color",
    anchor: "Alignment",
    x: "X",
    y: "Y",
    maxWidth: "Text box width",
    lineHeight: "Text line height",
    snapLabel: "Snap dragged positions to grid",
    gridSize: "Grid size",
    anchors: {
      ls: "Left",
      ms: "Center",
      rs: "Right",
      lt: "Top left",
      mt: "Top center",
      rt: "Top right",
      lm: "Middle left",
      mm: "Middle",
      rm: "Middle right"
    }
  },
  export: {
    designName: "Card design name",
    downloadPng: "Download Preview PNG",
    downloadPackage: "Download Design Package",
    hint: "Exports design config JSON, ordered image layers, custom fonts, and preview PNG.",
    jsonLabel: "Design config JSON",
    statusExported: (count, name) => `Exported ${count} files in ${name}_card_design.zip.`,
    statusImported: (name) => `Imported ${name}.`,
    manifestNotes: [
      "Layer order is bottom to top.",
      "Layer paths in config are relative to the design folder.",
      "Hidden layers are not included in config or package exports.",
      "Layers marked customizable: background can be replaced by one-time Discord custom background renders.",
      "Avatar shape and dimensions are exported into config.avatar; avatar preview images are local-only and are not packaged.",
      "Layer filenames begin with 01, 02, 03 so file browsing preserves draw order.",
      "Copy the designs and fonts folders into character-compendium before using the config."
    ]
  }
};

/**
 * Injects UI strings into the DOM based on data-ui attributes.
 */
function applyUiStrings() {
  document.querySelectorAll("[data-ui]").forEach((el) => {
    const [section, key] = el.dataset.ui.split(".");
    const value = UI_STRINGS[section]?.[key];
    if (value) {
      if (typeof value === "string") {
        el.textContent = value;
      }
    }
  });

  // Sync metadata
  document.title = UI_STRINGS.app.title;
  controls.loadSample.title = UI_STRINGS.app.sampleButton;
  canvas.setAttribute("aria-label", UI_STRINGS.app.canvasAriaLabel);
  controls.removeLayer.title = UI_STRINGS.layers.removeLayer;

  // Sync role options
  document.querySelectorAll("#assetRoleMode option, #layerRoleMode option, #roleMode option").forEach(opt => {
    opt.textContent = UI_STRINGS.roles[opt.value] || opt.textContent;
  });

  // Sync anchor options
  document.querySelectorAll("#anchor option").forEach(opt => {
    opt.textContent = UI_STRINGS.text.anchors[opt.value] || opt.textContent;
  });

  // Sync shape options
  document.querySelectorAll("#avatarShape option").forEach(opt => {
    opt.textContent = UI_STRINGS.avatar.shapes[opt.value] || opt.textContent;
  });
}
