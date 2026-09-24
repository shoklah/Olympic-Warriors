import { describe, expect, it } from 'vitest';
import {
	EXPORT_BACKGROUND,
	MAX_SOURCE_SIDE,
	MAX_ZOOM,
	MIN_ZOOM,
	OUTPUT_SIZE,
	clampCrop,
	clampZoom,
	decodeSize,
	initialCrop,
	panBy,
	sourceRect,
	visibleSide,
	zoomTo
} from './crop.js';

describe('crop constants', () => {
	it('exports a 512px square on the grey the server flattens transparency onto', () => {
		expect(OUTPUT_SIZE).toBe(512);
		expect(EXPORT_BACKGROUND).toBe('rgb(128, 128, 128)');
		expect(MIN_ZOOM).toBe(1);
		expect(MAX_ZOOM).toBeGreaterThan(MIN_ZOOM);
	});
});

describe('decodeSize', () => {
	it('never needs more than the 512px output at the highest zoom on the shorter side', () => {
		expect(MAX_SOURCE_SIDE).toBe(OUTPUT_SIZE * MAX_ZOOM);
	});

	it('shrinks a big image to that shorter side, keeping its shape', () => {
		expect(decodeSize(8000, 6000)).toEqual({ width: 2731, height: 2048 });
		expect(decodeSize(6000, 8000)).toEqual({ width: 2048, height: 2731 });
		expect(decodeSize(4096, 4096)).toEqual({ width: 2048, height: 2048 });
	});

	it('leaves an image already small enough as it is', () => {
		expect(decodeSize(2048, 3000)).toEqual({ width: 2048, height: 3000 });
		expect(decodeSize(800, 600)).toEqual({ width: 800, height: 600 });
	});

	it('keeps the crop maths in the shrunk pixels consistent: full zoom is 1:1 into the output', () => {
		const { width, height } = decodeSize(8000, 6000);
		expect(visibleSide(width, height, MAX_ZOOM)).toBe(OUTPUT_SIZE);
		expect(sourceRect(width, height, initialCrop(width, height))).toEqual({ sx: 341.5, sy: 0, sw: 2048, sh: 2048 });
	});
});

describe('clampZoom', () => {
	it('keeps the zoom in range, and a non-number at the minimum', () => {
		expect(clampZoom(2.5)).toBe(2.5);
		expect(clampZoom(0.2)).toBe(MIN_ZOOM);
		expect(clampZoom(99)).toBe(MAX_ZOOM);
		expect(clampZoom(Number.NaN)).toBe(MIN_ZOOM);
		expect(clampZoom(undefined)).toBe(MIN_ZOOM);
	});
});

describe('visibleSide', () => {
	it('is the shorter side at zoom 1 and shrinks as the zoom grows', () => {
		expect(visibleSide(800, 600, 1)).toBe(600);
		expect(visibleSide(800, 600, 2)).toBe(300);
		expect(visibleSide(800, 600, 99)).toBe(600 / MAX_ZOOM);
	});
});

describe('initialCrop', () => {
	it('starts centred at the cover scale', () => {
		expect(initialCrop(800, 600)).toEqual({ zoom: 1, cx: 400, cy: 300 });
	});
});

describe('clampCrop', () => {
	it('keeps the shown square inside the image', () => {
		// 600px shown: the centre can slide 100px either way horizontally, not at all vertically.
		expect(clampCrop(800, 600, { zoom: 1, cx: 0, cy: 0 })).toEqual({ zoom: 1, cx: 300, cy: 300 });
		expect(clampCrop(800, 600, { zoom: 1, cx: 9999, cy: 9999 })).toEqual({ zoom: 1, cx: 500, cy: 300 });
		expect(clampCrop(800, 600, { zoom: 2, cx: 790, cy: 10 })).toEqual({ zoom: 2, cx: 650, cy: 150 });
	});

	it('leaves a crop already inside alone', () => {
		expect(clampCrop(800, 600, { zoom: 2, cx: 400, cy: 200 })).toEqual({ zoom: 2, cx: 400, cy: 200 });
	});

	it('clamps the zoom too, and centres a centre that is not a number', () => {
		expect(clampCrop(800, 600, { zoom: 0, cx: Number.NaN, cy: undefined })).toEqual({ zoom: 1, cx: 400, cy: 300 });
	});
});

describe('panBy', () => {
	it('moves the image with the pointer, converting screen pixels to source pixels', () => {
		// At zoom 2, 300 source px fill a 300px preview: 1 screen px is 1 source px.
		const crop = { zoom: 2, cx: 400, cy: 300 };
		expect(panBy(800, 600, crop, 50, -20, 300)).toEqual({ zoom: 2, cx: 350, cy: 320 });
		// At zoom 1, 600 source px fill it: 1 screen px is 2 source px.
		expect(panBy(800, 600, { zoom: 1, cx: 400, cy: 300 }, 30, 0, 300)).toEqual({ zoom: 1, cx: 340, cy: 300 });
	});

	it('stops at the edge of the image', () => {
		expect(panBy(800, 600, { zoom: 1, cx: 400, cy: 300 }, 1000, 1000, 300)).toEqual({ zoom: 1, cx: 300, cy: 300 });
		expect(panBy(800, 600, { zoom: 1, cx: 400, cy: 300 }, -1000, 0, 300)).toEqual({ zoom: 1, cx: 500, cy: 300 });
	});
});

describe('zoomTo', () => {
	it('zooms around the same centre', () => {
		expect(zoomTo(800, 600, { zoom: 1, cx: 420, cy: 300 }, 3)).toEqual({ zoom: 3, cx: 420, cy: 300 });
	});

	it('pulls the centre back in when zooming out near an edge', () => {
		expect(zoomTo(800, 600, { zoom: 4, cx: 780, cy: 80 }, 1)).toEqual({ zoom: 1, cx: 500, cy: 300 });
	});

	it('keeps the zoom in range', () => {
		expect(zoomTo(800, 600, initialCrop(800, 600), 10).zoom).toBe(MAX_ZOOM);
	});
});

describe('sourceRect', () => {
	it('is the centred square of the shorter side at the start', () => {
		expect(sourceRect(800, 600, initialCrop(800, 600))).toEqual({ sx: 100, sy: 0, sw: 600, sh: 600 });
		expect(sourceRect(600, 800, initialCrop(600, 800))).toEqual({ sx: 0, sy: 100, sw: 600, sh: 600 });
	});

	it('follows the zoom and the centre', () => {
		expect(sourceRect(800, 600, { zoom: 2, cx: 500, cy: 200 })).toEqual({ sx: 350, sy: 50, sw: 300, sh: 300 });
	});

	it('never reaches outside the image, even for a crop that does', () => {
		const rect = sourceRect(800, 600, { zoom: 1.5, cx: -50, cy: 900 });
		expect(rect.sx).toBe(0);
		expect(rect.sy + rect.sh).toBe(600);
		expect(rect.sw).toBe(400);
	});
});
