import { describe, expect, it } from 'vitest';
import { crc32, makeZip } from './zip.js';

const bytes = (text) => new TextEncoder().encode(text);

/** A minimal reader: the entries of a ZIP through its central directory. */
function readZip(zip) {
	const view = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
	let end = zip.length - 22;
	while (view.getUint32(end, true) !== 0x06054b50) end -= 1;
	const count = view.getUint16(end + 10, true);
	let offset = view.getUint32(end + 16, true);
	const out = [];
	for (let i = 0; i < count; i++) {
		expect(view.getUint32(offset, true)).toBe(0x02014b50);
		const flags = view.getUint16(offset + 8, true);
		const method = view.getUint16(offset + 10, true);
		const crc = view.getUint32(offset + 16, true);
		const size = view.getUint32(offset + 20, true);
		const nameLen = view.getUint16(offset + 28, true);
		const local = view.getUint32(offset + 42, true);
		const name = new TextDecoder().decode(zip.subarray(offset + 46, offset + 46 + nameLen));
		expect(view.getUint32(local, true)).toBe(0x04034b50);
		const localNameLen = view.getUint16(local + 26, true);
		const start = local + 30 + localNameLen;
		out.push({ name, flags, method, crc, size, data: zip.slice(start, start + size) });
		offset += 46 + nameLen;
	}
	return out;
}

describe('crc32', () => {
	it('matches the standard check value', () => {
		expect(crc32(bytes('123456789'))).toBe(0xcbf43926);
		expect(crc32(new Uint8Array())).toBe(0);
	});
});

describe('makeZip', () => {
	it('stores each file under its name, with its CRC, uncompressed', () => {
		const zip = makeZip([
			{ name: 'a.png', data: bytes('hello') },
			{ name: 'équipe-2.png', data: new Uint8Array([0, 1, 2, 255]) }
		]);

		const entries = readZip(zip);
		expect(entries.map((e) => e.name)).toEqual(['a.png', 'équipe-2.png']);
		expect(entries.every((e) => e.method === 0 && (e.flags & 0x0800) !== 0)).toBe(true);
		expect(new TextDecoder().decode(entries[0].data)).toBe('hello');
		expect([...entries[1].data]).toEqual([0, 1, 2, 255]);
		expect(entries[0].crc).toBe(crc32(bytes('hello')));
		expect(entries[0].size).toBe(5);
	});

	it('makes an empty but valid archive', () => {
		const zip = makeZip([]);

		expect(zip.length).toBe(22);
		expect(readZip(zip)).toEqual([]);
	});
});
