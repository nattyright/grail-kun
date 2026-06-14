/**
 * Canvas Rendering Engine
 * 
 * Logic for drawing layers, avatars, and text elements to the design canvas.
 */

/**
 * Draws the background/design layers.
 */
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

/**
 * Draws the avatar preview with clipping masks.
 */
function drawAvatar(showSelection = true) {
  if (!state.avatar.image) {
    return;
  }

  const x = Number(state.avatar.x) || 0;
  const y = Number(state.avatar.y) || 0;
  const width = Number(state.avatar.width) || 1;
  const height = Number(state.avatar.height) || 1;
  const shape = String(state.avatar.shape || "rectangle").replace(/[-\s]+/g, "_").toLowerCase();

  ctx.save();
  ctx.beginPath();
  if (shape === "circle" || shape === "oval" || shape === "ellipse") {
    ctx.ellipse(x + width / 2, y + height / 2, width / 2, height / 2, 0, 0, Math.PI * 2);
    ctx.clip();
  } else if (shape === "diamond") {
    ctx.moveTo(x + width / 2, y);
    ctx.lineTo(x + width, y + height / 2);
    ctx.lineTo(x + width / 2, y + height);
    ctx.lineTo(x, y + height / 2);
    ctx.closePath();
    ctx.clip();
  } else if (shape === "rounded_rectangle" || shape === "rounded_rect" || shape === "rounded") {
    roundedRectPath(x, y, width, height, Math.min(width, height) / 8);
    ctx.clip();
  } else {
    ctx.rect(x, y, width, height);
    ctx.clip();
  }

  drawImageCover(state.avatar.image, x, y, width, height);
  ctx.restore();

  if (showSelection) {
    ctx.save();
    ctx.strokeStyle = "#7db7ff";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    ctx.strokeRect(x, y, width, height);
    ctx.restore();
  }
}

/**
 * Helper to draw a rounded rectangle path.
 */
function roundedRectPath(x, y, width, height, radius) {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2));
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/**
 * Draws an image to fill the target box while maintaining ratio (Center Crop).
 */
function drawImageCover(image, x, y, width, height) {
  const imgWidth = image.naturalWidth || image.width;
  const imgHeight = image.naturalHeight || image.height;
  const scale = Math.max(width / imgWidth, height / imgHeight);
  const drawWidth = imgWidth * scale;
  const drawHeight = imgHeight * scale;
  ctx.drawImage(image, x + (width - drawWidth) / 2, y + (height - drawHeight) / 2, drawWidth, drawHeight);
}

/**
 * Converts element font settings to a CSS font string.
 */
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

/**
 * Parses the 2-character anchor string into horizontal and vertical components.
 */
function anchorPoint(item) {
  const anchor = item.anchor || "ls";
  const horizontal = anchor[0] || "l";
  const vertical = anchor[1] || "s";
  return { horizontal, vertical };
}

/**
 * Applies text alignment and baseline to the canvas context.
 */
function applyAnchor(item) {
  const { horizontal, vertical } = anchorPoint(item);
  ctx.textAlign = horizontal === "m" ? "center" : horizontal === "r" ? "right" : "left";
  // 's' maps to alphabetic baseline
  ctx.textBaseline = vertical === "t" ? "top" : vertical === "m" ? "middle" : "alphabetic";
}

/**
 * Basic word-wrapping logic for the canvas.
 */
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

/**
 * Draws a single text element.
 */
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

/**
 * Calculates the bounding box of a text element for hit testing and selection highlighting.
 */
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
  if (vertical === "a" || vertical === "s") y -= Number(item.fontSize);

  ctx.restore();
  return { x, y, width, height };
}

/**
 * Main draw loop.
 */
function render(showIndicators = true) {
  updatePreviewZoom();
  drawBase();
  drawAvatar(showIndicators);
  activeText().forEach((item) => {
    drawTextItem(item, showIndicators && item.id === state.selectedTextId);
  });
  if (showIndicators) {
    updateJson();
  }
}
