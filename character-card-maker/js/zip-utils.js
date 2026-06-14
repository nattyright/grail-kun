/**
 * ZIP & CRC Utilities
 * 
 * Implements a minimal, uncompressed ZIP (Store) generator and parser
 * for maximum portability without external library dependencies.
 */

/**
 * Converts a string to a Uint8Array.
 */
function stringBytes(value) {
  return new TextEncoder().encode(value);
}

/**
 * Builds a ZIP Blob from an array of file objects {name: string, data: Uint8Array}.
 * Uses uncompressed 'Store' method (Compression 0).
 */
function buildZip(files) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  files.forEach((file) => {
    const nameBytes = stringBytes(file.name);
    const data = file.data;
    const crc = crc32(data);

    // 1. Create Local File Header (30 bytes + name)
    const local = new Uint8Array(30 + nameBytes.length);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034b50, true);   // Header Signature (PK\x03\x04)
    localView.setUint16(4, 20, true);           // Minimum Version (2.0)
    localView.setUint16(6, 0, true);            // General Purpose Bit Flags
    localView.setUint16(8, 0, true);            // Compression Method (0 = Store)
    localView.setUint16(10, 0, true);           // Last Mod File Time (0)
    localView.setUint16(12, 0, true);           // Last Mod File Date (0)
    localView.setUint32(14, crc, true);         // CRC-32 Checksum
    localView.setUint32(18, data.length, true); // Compressed Size
    localView.setUint32(22, data.length, true); // Uncompressed Size
    localView.setUint16(26, nameBytes.length, true);
    localView.setUint16(28, 0, true);           // Extra Field Length (0)
    local.set(nameBytes, 30);
    localParts.push(local, data);

    // 2. Create Central Directory Header (46 bytes + name)
    const central = new Uint8Array(46 + nameBytes.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014b50, true);   // Header Signature (PK\x01\x02)
    centralView.setUint16(4, 20, true);           // Version Made By (2.0)
    centralView.setUint16(6, 20, true);           // Version Needed (2.0)
    centralView.setUint16(8, 0, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint16(12, 0, true);
    centralView.setUint16(14, 0, true);           // Skip mod time/date
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, data.length, true);
    centralView.setUint32(24, data.length, true);
    centralView.setUint16(28, nameBytes.length, true);
    centralView.setUint16(30, 0, true);           // Extra Field Length
    centralView.setUint16(32, 0, true);           // File Comment Length
    centralView.setUint16(34, 0, true);           // Disk Number Start
    centralView.setUint16(36, 0, true);           // Internal File Attributes
    centralView.setUint32(38, 0, true);           // External File Attributes
    centralView.setUint32(42, offset, true);      // Relative Offset of Local Header
    central.set(nameBytes, 46);
    centralParts.push(central);

    // Increment offset by local header + file data size
    offset += local.length + data.length;
  });

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  
  // 3. Create End of Central Directory Record (22 bytes)
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);     // Record Signature (PK\x05\x06)
  endView.setUint16(4, 0, true);               // Number of this disk
  endView.setUint16(6, 0, true);               // Disk where central directory starts
  endView.setUint16(8, files.length, true);    // Number of central directory records on this disk
  endView.setUint16(10, files.length, true);   // Total number of central directory records
  endView.setUint32(12, centralSize, true);    // Size of central directory
  endView.setUint32(16, offset, true);         // Offset of central directory relative to disk start
  endView.setUint16(20, 0, true);              // Comment Length

  return new Blob([...localParts, ...centralParts, end], { type: "application/zip" });
}

/**
 * Minimal ZIP parser for uncompressed packages.
 * Scans through local file headers and extracts data segments.
 * 
 * @param {Uint8Array} bytes The ZIP file content.
 * @returns {Array} List of extracted entries {name, data}.
 */
function readZipEntries(bytes) {
  const entries = [];
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 0;

  while (offset + 30 <= bytes.length) {
    const signature = view.getUint32(offset, true);
    if (signature !== 0x04034b50) {
      // Reached central directory or end of data
      break;
    }

    const method = view.getUint16(offset + 8, true);
    if (method !== 0) {
      throw new Error("Only uncompressed (Store) ZIP packages are supported.");
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

// --- CRC-32 Implementation ---
// Required for ZIP file integrity fields.

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

/**
 * Computes the CRC-32 checksum for a Uint8Array.
 */
function crc32(data) {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
