/**
 * The maths of the photo editor's square crop, with no canvas and no DOM, so it is unit-tested.
 *
 * The crop is `{ zoom, cx, cy }`: the zoom (1 is the cover scale, where the image's shorter
 * side just fills the square, see `visibleSide`) and the point of the source image, in
 * source pixels, at the square's centre. Kept in source pixels rather than screen pixels, it is independent of
 * how big the preview is drawn, so the same crop feeds the preview and the 512px export.
 * The shown square never leaves the image: the photo is stored square and shown as the
 * circle inscribed in it, so covering the square covers the circle with no empty corner.
 */

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;
/** The side of the exported JPEG, the server's large size (it re-encodes it anyway). */
export const OUTPUT_SIZE = 512;
export const OUTPUT_TYPE = 'image/jpeg';
export const OUTPUT_QUALITY = 0.9;
/**
 * What a transparent part of a PNG or WebP turns into: JPEG has no alpha, and the server
 * flattens transparency onto the same grey, so the preview, the export and a file sent
 * as is all agree. Not a theme colour: it ends up in the stored photo.
 */
export const EXPORT_BACKGROUND = 'rgb(128, 128, 128)';
/**
 * The most a source ever needs on its shorter side: at the highest zoom the shown square is
 * that side over MAX_ZOOM, drawn 1:1 into the output. A bigger photo is shrunk to it once,
 * when decoded, rather than kept whole (48 MP is some 190 MB) and redrawn at each move.
 */
export const MAX_SOURCE_SIDE = OUTPUT_SIZE * MAX_ZOOM;

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

/** The zoom within [MIN_ZOOM, MAX_ZOOM]; anything that is not a number is the minimum. */
export const clampZoom = (zoom) => (Number.isFinite(zoom) ? clamp(zoom, MIN_ZOOM, MAX_ZOOM) : MIN_ZOOM);

/**
 * The size to decode a `width` × `height` image at: shrunk so its shorter side is
 * MAX_SOURCE_SIDE, keeping its shape, or as it is when already smaller. The crop is then kept
 * in the pixels of that decoded size.
 */
export function decodeSize(width, height) {
	const scale = Math.min(1, MAX_SOURCE_SIDE / Math.min(width, height));
	return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** The side, in source pixels, of the square shown at `zoom`: the shorter side at zoom 1. */
export const visibleSide = (width, height, zoom) => Math.min(width, height) / clampZoom(zoom);

/** The starting crop: the cover scale, centred. */
export const initialCrop = (width, height) => ({ zoom: MIN_ZOOM, cx: width / 2, cy: height / 2 });

/**
 * `crop` with its zoom in range and its centre moved, if needed, so the shown square stays
 * inside the image (the pan clamping).
 */
export function clampCrop(width, height, crop) {
	const zoom = clampZoom(crop.zoom);
	const half = visibleSide(width, height, zoom) / 2;
	return {
		zoom,
		cx: clamp(Number.isFinite(crop.cx) ? crop.cx : width / 2, half, width - half),
		cy: clamp(Number.isFinite(crop.cy) ? crop.cy : height / 2, half, height - half)
	};
}

/**
 * The crop after dragging by (`dx`, `dy`) screen pixels over a preview `size` pixels wide:
 * the image follows the pointer, so its centre moves the other way in the source.
 */
export function panBy(width, height, crop, dx, dy, size) {
	const perPixel = visibleSide(width, height, crop.zoom) / size;
	return clampCrop(width, height, { ...crop, cx: crop.cx - dx * perPixel, cy: crop.cy - dy * perPixel });
}

/** The crop at another zoom, around the same centre, clamped again. */
export const zoomTo = (width, height, crop, zoom) => clampCrop(width, height, { ...crop, zoom });

/**
 * The source rectangle to draw into the preview or the 512px square
 * (`drawImage(image, sx, sy, sw, sh, 0, 0, side, side)`).
 */
export function sourceRect(width, height, crop) {
	const { zoom, cx, cy } = clampCrop(width, height, crop);
	const side = visibleSide(width, height, zoom);
	return { sx: cx - side / 2, sy: cy - side / 2, sw: side, sh: side };
}
