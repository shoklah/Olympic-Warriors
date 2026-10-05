const TABLE = (() => {
	const table = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		table[n] = c >>> 0;
	}
	return table;
})();

/** CRC-32 of some bytes (the checksum a ZIP stores for each file). */
export function crc32(bytes) {
	let c = 0xffffffff;
	for (const byte of bytes) c = TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

const dosTime = (d) => (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1);
const dosDate = (d) => ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate();

/**
 * A ZIP archive of `files` (`{ name, data: Uint8Array }`), every file stored uncompressed (PNGs
 * are already compressed), names in UTF-8. Returns the archive's bytes.
 */
export function makeZip(files, now = new Date()) {
	const encoder = new TextEncoder();
	const entries = files.map((file) => ({
		name: encoder.encode(file.name),
		data: file.data,
		crc: crc32(file.data)
	}));
	const time = dosTime(now);
	const date = dosDate(now);
	const localSize = entries.reduce((sum, e) => sum + 30 + e.name.length + e.data.length, 0);
	const centralSize = entries.reduce((sum, e) => sum + 46 + e.name.length, 0);
	const out = new Uint8Array(localSize + centralSize + 22);
	const view = new DataView(out.buffer);

	let offset = 0;
	const offsets = [];
	for (const e of entries) {
		offsets.push(offset);
		view.setUint32(offset, 0x04034b50, true);
		view.setUint16(offset + 4, 20, true); // version needed
		view.setUint16(offset + 6, 0x0800, true); // UTF-8 names
		view.setUint16(offset + 8, 0, true); // stored
		view.setUint16(offset + 10, time, true);
		view.setUint16(offset + 12, date, true);
		view.setUint32(offset + 14, e.crc, true);
		view.setUint32(offset + 18, e.data.length, true);
		view.setUint32(offset + 22, e.data.length, true);
		view.setUint16(offset + 26, e.name.length, true);
		view.setUint16(offset + 28, 0, true);
		out.set(e.name, offset + 30);
		out.set(e.data, offset + 30 + e.name.length);
		offset += 30 + e.name.length + e.data.length;
	}

	const centralStart = offset;
	entries.forEach((e, i) => {
		view.setUint32(offset, 0x02014b50, true);
		view.setUint16(offset + 4, 20, true); // made by
		view.setUint16(offset + 6, 20, true); // needed
		view.setUint16(offset + 8, 0x0800, true);
		view.setUint16(offset + 10, 0, true);
		view.setUint16(offset + 12, time, true);
		view.setUint16(offset + 14, date, true);
		view.setUint32(offset + 16, e.crc, true);
		view.setUint32(offset + 20, e.data.length, true);
		view.setUint32(offset + 24, e.data.length, true);
		view.setUint16(offset + 28, e.name.length, true);
		// extra, comment, disk, internal and external attributes stay zero
		view.setUint32(offset + 42, offsets[i], true);
		out.set(e.name, offset + 46);
		offset += 46 + e.name.length;
	});

	view.setUint32(offset, 0x06054b50, true);
	view.setUint16(offset + 8, entries.length, true);
	view.setUint16(offset + 10, entries.length, true);
	view.setUint32(offset + 12, centralSize, true);
	view.setUint32(offset + 16, centralStart, true);
	return out;
}
