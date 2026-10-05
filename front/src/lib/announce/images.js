export const LOAD_TIMEOUT = 10000;

/** `promise`, or `fallback` once `ms` have passed (the timer is cleared when the promise wins). */
function within(promise, ms, fallback) {
	let timer;
	const timeout = new Promise((resolve) => (timer = setTimeout(() => resolve(fallback), ms)));
	return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/** An image loaded from `url`, or null when it fails or takes over `timeoutMs` (a missing photo is not an error here). */
export function loadImage(url, timeoutMs = LOAD_TIMEOUT) {
	const loading = new Promise((resolve) => {
		const image = new Image();
		image.onload = () => resolve(image);
		image.onerror = () => resolve(null);
		image.src = url;
	});
	return within(loading, timeoutMs, null);
}

/** The images of `urls` (each distinct url once, blanks and failures left out) as a Map. */
export async function loadImages(urls, timeoutMs = LOAD_TIMEOUT) {
	const unique = [...new Set(urls.filter(Boolean))];
	const loaded = await Promise.all(unique.map(async (url) => [url, await loadImage(url, timeoutMs)]));
	return new Map(loaded.filter(([, image]) => image));
}

const FACES = ['400 40px "Bebas Neue"', '500 20px Inter', '600 20px Inter', '700 20px Inter'];

/** Resolves once the site's fonts are loaded, so the first draw is not in a fallback face. */
export async function fontsReady(timeoutMs = LOAD_TIMEOUT) {
	if (!globalThis.document?.fonts) return;
	await within(Promise.all(FACES.map((face) => document.fonts.load(face).catch(() => []))), timeoutMs, null);
}
