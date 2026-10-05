import { makeZip } from './zip.js';

/** A file-name-safe version of a text: no accents, lower case, dashes. */
export const slug = (text) =>
	String(text ?? '')
		.normalize('NFD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '') || 'equipe';

export const posterFileName = (year) => `equipes-${year}.png`;
export const cardFileName = (index, name) => `equipe-${String(index).padStart(2, '0')}-${slug(name)}.png`;

/** The PNG of a canvas as a Blob. */
export function toPng(canvas) {
	return new Promise((resolve, reject) => {
		canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('The canvas gave no image'))), 'image/png');
	});
}

/** Save a blob as a file: a temporary link to an object URL, revoked right after. */
export function download(blob, name) {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = name;
	document.body.append(link);
	link.click();
	document.body.removeChild(link);
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Save `entries` (`{ name, blob }`) as one store-only ZIP called `zipName`. */
export async function downloadZip(entries, zipName) {
	const files = await Promise.all(
		entries.map(async ({ name, blob }) => ({ name, data: new Uint8Array(await blob.arrayBuffer()) }))
	);
	download(new Blob([makeZip(files)], { type: 'application/zip' }), zipName);
}
