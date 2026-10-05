/** An image loaded from `url`, or null when it fails (a missing photo is not an error here). */
export function loadImage(url) {
	return new Promise((resolve) => {
		const image = new Image();
		image.onload = () => resolve(image);
		image.onerror = () => resolve(null);
		image.src = url;
	});
}

/** The images of `urls` (each distinct url once, blanks and failures left out) as a Map. */
export async function loadImages(urls) {
	const unique = [...new Set(urls.filter(Boolean))];
	const loaded = await Promise.all(unique.map(async (url) => [url, await loadImage(url)]));
	return new Map(loaded.filter(([, image]) => image));
}

const FACES = ['400 40px "Bebas Neue"', '500 20px Inter', '600 20px Inter', '700 20px Inter'];

/** Resolves once the site's fonts are loaded, so the first draw is not in a fallback face. */
export async function fontsReady() {
	if (!globalThis.document?.fonts) return;
	await Promise.all(FACES.map((face) => document.fonts.load(face).catch(() => [])));
}
