import { fireEvent, screen, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWith } from '$lib/test-utils';
import PhotoEditor from './PhotoEditor.svelte';

const navigation = vi.hoisted(() => ({ invalidateAll: vi.fn(async () => {}) }));
vi.mock('$app/navigation', () => navigation);
// SvelteKit's deserialize also revives `data` through devalue; the actions return plain JSON.
vi.mock('$app/forms', () => ({ deserialize: (text) => JSON.parse(text) }));

const xavier = { first_name: 'Xavier', last_name: 'Baby' };
const photo = { large: '/media/avatars/34-9b8a7c6d5e4f.webp', small: '/media/avatars/34-9b8a7c6d5e4f-sm.webp' };

/** Every 2D context handed out, each recording its calls with the fill colour at the time. */
let contexts;
/** Every canvas toBlob was called on. */
let encoded;

const actionResult = (result) => new Response(JSON.stringify(result), { headers: { 'content-type': 'application/json' } });

beforeEach(() => {
	contexts = [];
	encoded = [];
	// jsdom has no canvas: a context that records what is drawn, and a toBlob that encodes nothing.
	vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function () {
		const ctx = {
			canvas: this,
			calls: [],
			fillStyle: '',
			imageSmoothingQuality: 'low',
			sources: [],
			fillRect: (...args) => ctx.calls.push(['fillRect', ctx.fillStyle, ...args]),
			drawImage: (source, ...args) => {
				ctx.sources.push(source);
				ctx.calls.push(['drawImage', ...args]);
			}
		};
		contexts.push(ctx);
		return ctx;
	});
	vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (callback, type, quality) {
		encoded.push({ canvas: this, type, quality });
		callback(new Blob(['jpeg bytes'], { type }));
	});
	vi.stubGlobal(
		'createImageBitmap',
		vi.fn(async () => ({ width: 800, height: 600, close: vi.fn() }))
	);
	vi.stubGlobal('fetch', vi.fn(async () => actionResult({ type: 'success', status: 200 })));
});

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.style.overflow = '';
});

const jpegFile = () => new File(['jpeg'], 'me.jpg', { type: 'image/jpeg' });

/** Choose `file` in the file input, and wait for the crop widget to show. */
async function choose(file = jpegFile()) {
	await fireEvent.change(screen.getByLabelText('Choose a photo'), { target: { files: [file] } });
	return waitFor(() => screen.getByRole('application', { name: 'Photo framing' }));
}

/** A pointer event: jsdom has no PointerEvent, so a MouseEvent carrying a pointerId. */
const pointer = (target, type, { pointerId = 1, clientX = 0, clientY = 0 } = {}) => {
	const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX, clientY });
	Object.defineProperty(event, 'pointerId', { value: pointerId });
	return fireEvent(target, event);
};

/** The preview canvas, inside the crop widget. */
const previewCanvas = () => screen.getByRole('application').querySelector('canvas');

/** The last source rectangle drawn on the preview canvas: [sx, sy, sw, sh]. */
const lastPreviewRect = () => {
	const canvas = previewCanvas();
	const draws = contexts
		.filter((c) => c.canvas === canvas)
		.flatMap((c) => c.calls)
		.filter(([name]) => name === 'drawImage');
	return draws[draws.length - 1].slice(1, 5);
};

/** A promise and its resolver, to settle decodes in any order. */
const deferred = () => {
	let resolve;
	const promise = new Promise((done) => (resolve = done));
	return { promise, resolve };
};

/** Let every pending promise callback run. */
const settle = () => new Promise((done) => setTimeout(done));

const pickFile = (file = jpegFile()) =>
	fireEvent.change(screen.getByLabelText('Choose a photo'), { target: { files: [file] } });

describe('PhotoEditor', () => {
	it('opens as a dialog with the file input, the public line, no crop yet and Save disabled', () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		const dialog = screen.getByRole('dialog', { name: 'My photo' });
		expect(dialog).toHaveAttribute('aria-modal', 'true');
		expect(dialog).toHaveTextContent('Your photo will be publicly visible on the site.');
		expect(screen.getByLabelText('Choose a photo')).toHaveAttribute('accept', 'image/jpeg,image/png,image/webp');
		expect(screen.queryByRole('application')).toBeNull();
		expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
		// The current photo stands in for the crop until a file is chosen.
		expect(dialog.querySelector('img')).toHaveAttribute('src', photo.large);
	});

	it('renders nothing when closed', () => {
		renderWith(PhotoEditor, { open: false, photo, name: xavier });
		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('offers « Delete my photo » only when there is a photo', () => {
		const { unmount } = renderWith(PhotoEditor, { open: true, photo, name: xavier });
		expect(screen.getByRole('button', { name: 'Delete my photo' })).toBeInTheDocument();
		unmount();

		renderWith(PhotoEditor, { open: true, photo: null, name: xavier });
		expect(screen.queryByRole('button', { name: 'Delete my photo' })).toBeNull();
		expect(screen.getByRole('dialog')).toHaveTextContent('XB');
	});

	it('when locked, says so and leaves only the delete button (and Close)', () => {
		const { unmount } = renderWith(PhotoEditor, { open: true, photo, locked: true, name: xavier });

		const dialog = screen.getByRole('dialog', { name: 'My photo' });
		expect(dialog).toHaveTextContent('Photo uploads have been turned off by an organiser');
		expect(screen.queryByLabelText('Choose a photo')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
		expect(screen.getAllByRole('button').map((b) => b.textContent.trim())).toEqual(['Delete my photo', 'Close']);
		unmount();

		renderWith(PhotoEditor, { open: true, photo: null, locked: true, name: xavier });
		expect(screen.getAllByRole('button').map((b) => b.textContent.trim())).toEqual(['Close']);
	});

	it('decodes the chosen file upright and shows a focusable crop with its instructions and a zoom slider', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		const crop = await choose();
		expect(createImageBitmap).toHaveBeenCalledWith(expect.any(File), { imageOrientation: 'from-image' });
		expect(crop).toHaveAttribute('tabindex', '0');
		expect(crop).toHaveAccessibleDescription('Drag the photo to frame it, or use the arrow keys; + and − to zoom.');
		const canvas = crop.querySelector('canvas');
		expect(screen.getByRole('slider', { name: 'Zoom' })).toHaveValue('1');
		expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
		// The centred square of the shorter side, on the export grey.
		expect(lastPreviewRect()).toEqual([100, 0, 600, 600]);
		const preview = contexts.find((c) => c.canvas === canvas);
		expect(preview.calls[0]).toEqual(['fillRect', 'rgb(128, 128, 128)', 0, 0, canvas.width, canvas.height]);
	});

	it('falls back to an <img> when createImageBitmap refuses, revoking its object URL', async () => {
		createImageBitmap.mockRejectedValue(new TypeError('unsupported option'));
		const createObjectURL = vi.fn(() => 'blob:photo');
		const revokeObjectURL = vi.fn();
		vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }));
		class FakeImage {
			naturalWidth = 300;
			naturalHeight = 900;
			set src(url) {
				this.url = url;
				setTimeout(() => this.onload());
			}
		}
		vi.stubGlobal('Image', FakeImage);
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await choose();
		expect(createObjectURL).toHaveBeenCalledWith(expect.any(File));
		expect(revokeObjectURL).toHaveBeenCalledWith('blob:photo');
		expect(lastPreviewRect()).toEqual([0, 300, 300, 300]);
		delete URL.createObjectURL;
		delete URL.revokeObjectURL;
	});

	it('keeps the last pick when two decodes finish out of order, closing the stale bitmap', async () => {
		const first = deferred();
		const second = deferred();
		createImageBitmap.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await pickFile();
		await pickFile();
		const fresh = { width: 400, height: 300, close: vi.fn() };
		second.resolve(fresh);
		await waitFor(() => screen.getByRole('application'));
		expect(lastPreviewRect()).toEqual([50, 0, 300, 300]);

		const stale = { width: 800, height: 600, close: vi.fn() };
		first.resolve(stale);
		await settle();
		expect(stale.close).toHaveBeenCalled();
		expect(fresh.close).not.toHaveBeenCalled();
		expect(lastPreviewRect()).toEqual([50, 0, 300, 300]);
	});

	it('drops a decode that finishes after the dialog closed and reopened', async () => {
		const late = deferred();
		createImageBitmap.mockReturnValueOnce(late.promise);
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await pickFile();
		await component.$set({ open: false });
		await component.$set({ open: true });
		const bitmap = { width: 800, height: 600, close: vi.fn() };
		late.resolve(bitmap);
		await settle();
		expect(bitmap.close).toHaveBeenCalled();
		expect(screen.queryByRole('application')).toBeNull();
	});

	it('closes a bitmap decoded after the editor is gone', async () => {
		const late = deferred();
		createImageBitmap.mockReturnValueOnce(late.promise);
		const { unmount } = renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await pickFile();
		unmount();
		const bitmap = { width: 800, height: 600, close: vi.fn() };
		late.resolve(bitmap);
		await settle();
		expect(bitmap.close).toHaveBeenCalled();
	});

	it('shrinks a big photo to 2048px on its shorter side, closing the full-size bitmap', async () => {
		const full = { width: 8000, height: 6000, close: vi.fn() };
		const small = { width: 2731, height: 2048, close: vi.fn() };
		createImageBitmap.mockResolvedValueOnce(full).mockResolvedValueOnce(small);
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await choose();
		expect(createImageBitmap).toHaveBeenNthCalledWith(2, full, {
			resizeWidth: 2731,
			resizeHeight: 2048,
			resizeQuality: 'high'
		});
		expect(full.close).toHaveBeenCalled();
		expect(small.close).not.toHaveBeenCalled();
		expect(lastPreviewRect()).toEqual([341.5, 0, 2048, 2048]);

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(encoded).toHaveLength(1));
		const exported = contexts.find((c) => c.canvas === encoded[0].canvas);
		expect(exported.sources).toEqual([small]);
		expect(exported.calls[1]).toEqual(['drawImage', 341.5, 0, 2048, 2048, 0, 0, 512, 512]);
	});

	it('keeps the full size when the engine cannot resize a bitmap', async () => {
		const full = { width: 8000, height: 6000, close: vi.fn() };
		createImageBitmap.mockResolvedValueOnce(full).mockRejectedValueOnce(new TypeError('no resize'));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await choose();
		expect(full.close).not.toHaveBeenCalled();
		expect(lastPreviewRect()).toEqual([1000, 0, 6000, 6000]);
	});

	it('shrinks a big photo from the <img> fallback through a canvas', async () => {
		createImageBitmap.mockRejectedValue(new TypeError('unsupported option'));
		vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:big', revokeObjectURL: () => {} }));
		class BigImage {
			naturalWidth = 6000;
			naturalHeight = 9000;
			set src(_url) {
				setTimeout(() => this.onload());
			}
		}
		vi.stubGlobal('Image', BigImage);
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await choose();
		const shrink = contexts.find((c) => c.canvas.width === 2048 && c.canvas.height === 3072);
		expect(shrink.sources[0]).toBeInstanceOf(BigImage);
		expect(shrink.calls).toEqual([['drawImage', 0, 0, 2048, 3072]]);
		expect(lastPreviewRect()).toEqual([0, 512, 2048, 2048]);
		expect(contexts.find((c) => c.canvas === previewCanvas()).sources.at(-1)).toBe(shrink.canvas);
		delete URL.createObjectURL;
		delete URL.revokeObjectURL;
	});

	it('refuses a file of another type before decoding it', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await fireEvent.change(screen.getByLabelText('Choose a photo'), {
			target: { files: [new File(['gif'], 'a.gif', { type: 'image/gif' })] }
		});
		expect(screen.getByRole('alert')).toHaveTextContent('Unsupported format: JPEG, PNG or WebP');
		expect(createImageBitmap).not.toHaveBeenCalled();
	});

	it('says so when the image cannot be decoded at all', async () => {
		createImageBitmap.mockRejectedValue(new DOMException('bad', 'InvalidStateError'));
		vi.stubGlobal('Image', class {
			set src(_url) {
				setTimeout(() => this.onerror());
			}
		});
		vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} }));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });

		await fireEvent.change(screen.getByLabelText('Choose a photo'), { target: { files: [jpegFile()] } });
		await waitFor(() =>
			expect(screen.getByRole('alert')).toHaveTextContent('This image cannot be read: try another one')
		);
		expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
		delete URL.createObjectURL;
		delete URL.revokeObjectURL;
	});

	it('pans with the arrow keys and zooms with + and -, by the keyboard alone', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		const crop = await choose();

		crop.focus();
		await fireEvent.keyDown(crop, { key: 'ArrowRight' });
		const [sx] = lastPreviewRect();
		// The image follows the arrow, so the shown square moves left in the source.
		expect(sx).toBeLessThan(100);
		await fireEvent.keyDown(crop, { key: '+' });
		expect(screen.getByRole('slider', { name: 'Zoom' })).toHaveValue('1.1');
		expect(lastPreviewRect()[2]).toBeCloseTo(600 / 1.1);
		await fireEvent.keyDown(crop, { key: '-' });
		expect(screen.getByRole('slider', { name: 'Zoom' })).toHaveValue('1');
		// The edge stops it: the shown square never leaves the image.
		for (let i = 0; i < 20; i += 1) await fireEvent.keyDown(crop, { key: 'ArrowRight', shiftKey: true });
		expect(lastPreviewRect()[0]).toBe(0);
	});

	it('zooms with the slider, speaking the zoom as a percentage', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await choose();

		const slider = screen.getByRole('slider', { name: 'Zoom' });
		await fireEvent.input(slider, { target: { value: '2' } });
		expect(lastPreviewRect()).toEqual([250, 150, 300, 300]);
		expect(slider).toHaveAttribute('aria-valuetext', '200%');
	});

	it('pans by dragging', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		const crop = await choose();
		const canvas = crop.querySelector('canvas');
		await fireEvent.input(screen.getByRole('slider', { name: 'Zoom' }), { target: { value: '2' } });

		// Events on the canvas reach the widget around it.
		await pointer(canvas, 'pointerdown', { clientX: 100, clientY: 100 });
		// A second finger does not take the drag over.
		await pointer(canvas, 'pointermove', { pointerId: 2, clientX: 0, clientY: 0 });
		await pointer(canvas, 'pointermove', { clientX: 128, clientY: 86 });
		await pointer(canvas, 'pointerup');
		// 300 source px over the 280px preview (jsdom lays nothing out): 28px right, 14px up.
		const [sx, sy] = lastPreviewRect();
		expect(sx).toBeCloseTo(250 - (28 * 300) / 280);
		expect(sy).toBeCloseTo(150 + (14 * 300) / 280);
		// Released: moving on does nothing.
		await pointer(canvas, 'pointermove', { clientX: 300, clientY: 300 });
		expect(lastPreviewRect()[0]).toBeCloseTo(sx);
	});

	it('ends a drag whose pointer capture is lost, and lets the same pointer start again', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		const crop = await choose();
		await fireEvent.input(screen.getByRole('slider', { name: 'Zoom' }), { target: { value: '2' } });

		await pointer(crop, 'pointerdown', { clientX: 100, clientY: 100 });
		await pointer(crop, 'lostpointercapture');
		await pointer(crop, 'pointermove', { clientX: 150, clientY: 100 });
		expect(lastPreviewRect()[0]).toBe(250);

		await pointer(crop, 'pointerdown', { clientX: 100, clientY: 100 });
		await pointer(crop, 'pointermove', { clientX: 128, clientY: 100 });
		expect(lastPreviewRect()[0]).toBeCloseTo(250 - (28 * 300) / 280);
	});

	it('saves a 512px JPEG drawn on the export grey, posted as FormData to ?/photo, then reloads and closes', async () => {
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier });
		const closed = vi.fn();
		component.$on('close', closed);
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(closed).toHaveBeenCalledTimes(1));

		expect(encoded).toHaveLength(1);
		expect(encoded[0]).toMatchObject({ type: 'image/jpeg', quality: 0.9 });
		expect(encoded[0].canvas.width).toBe(512);
		expect(encoded[0].canvas.height).toBe(512);
		const exported = contexts.find((c) => c.canvas === encoded[0].canvas);
		expect(exported.calls).toEqual([
			['fillRect', 'rgb(128, 128, 128)', 0, 0, 512, 512],
			['drawImage', 100, 0, 600, 600, 0, 0, 512, 512]
		]);

		expect(fetch).toHaveBeenCalledTimes(1);
		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('?/photo');
		expect(options.method).toBe('POST');
		expect(options.headers).toEqual({ accept: 'application/json', 'x-sveltekit-action': 'true' });
		expect(options.cache).toBe('no-store');
		expect(options.body).toBeInstanceOf(FormData);
		const sent = options.body.get('photo');
		expect(typeof sent).not.toBe('string');
		expect(sent.type).toBe('image/jpeg');
		expect(sent.name).toBe('photo.jpg');
		expect(sent.size).toBeGreaterThan(0);
		expect(navigation.invalidateAll).toHaveBeenCalledTimes(1);
	});

	it('turns the buttons off and says so while saving, focus staying on Save', async () => {
		let answer;
		fetch.mockImplementation(() => new Promise((resolve) => (answer = resolve)));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await choose();

		const save = screen.getByRole('button', { name: 'Save' });
		save.focus();
		await fireEvent.click(save);
		await waitFor(() => expect(fetch).toHaveBeenCalled());
		expect(screen.getByRole('status')).toHaveTextContent('Saving…');
		expect(screen.getByRole('dialog')).not.toHaveAttribute('aria-busy');
		// aria-disabled, not disabled: a disabled button would drop focus to <body>.
		expect(save).toHaveAttribute('aria-disabled', 'true');
		expect(save).toHaveFocus();
		expect(screen.getByRole('button', { name: 'Delete my photo' })).toHaveAttribute('aria-disabled', 'true');
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
		expect(screen.getByLabelText('Choose a photo')).toBeDisabled();
		await fireEvent.click(save);
		await fireEvent.click(screen.getByRole('button', { name: 'Delete my photo' }));
		expect(fetch).toHaveBeenCalledTimes(1);

		answer(actionResult({ type: 'failure', status: 500, data: { action: 'photo', error: 'photo.error.failed' } }));
		await waitFor(() => expect(save).not.toHaveAttribute('aria-disabled'));
		expect(save).toHaveFocus();
		expect(screen.getByRole('status')).toHaveTextContent('');
	});

	it('keeps focus on Delete while deleting', async () => {
		fetch.mockImplementation(() => new Promise(() => {}));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		// Let the dialog's own opening focus land first.
		await tick();
		await tick();

		const remove = screen.getByRole('button', { name: 'Delete my photo' });
		remove.focus();
		await fireEvent.click(remove);
		await waitFor(() => expect(fetch).toHaveBeenCalled());
		expect(screen.getByRole('status')).toHaveTextContent('Deleting…');
		expect(remove).toHaveAttribute('aria-disabled', 'true');
		expect(remove).toHaveFocus();
	});

	it('freezes the crop while saving: no key, no drag moves it', async () => {
		fetch.mockImplementation(() => new Promise(() => {}));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		const crop = await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(fetch).toHaveBeenCalled());
		const before = lastPreviewRect();
		await fireEvent.keyDown(crop, { key: 'ArrowRight' });
		await fireEvent.keyDown(crop, { key: '+' });
		await pointer(crop, 'pointerdown', { clientX: 100, clientY: 100 });
		await pointer(crop, 'pointermove', { clientX: 160, clientY: 100 });
		expect(lastPreviewRect()).toEqual(before);
	});

	it("shows the action's refusal in an alert and stays open, without reloading", async () => {
		fetch.mockResolvedValue(
			actionResult({ type: 'failure', status: 429, data: { action: 'photo', error: 'photo.error.throttled' } })
		);
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier });
		const closed = vi.fn();
		component.$on('close', closed);
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() =>
			expect(screen.getByRole('alert')).toHaveTextContent('Too many photos sent: try again later')
		);
		expect(closed).not.toHaveBeenCalled();
		expect(navigation.invalidateAll).not.toHaveBeenCalled();
		expect(screen.getByRole('dialog')).toBeInTheDocument();
	});

	it('reads a proxy 413 that is not an action result as too large', async () => {
		fetch.mockResolvedValue(new Response('<html>413</html>', { status: 413, headers: { 'content-type': 'text/html' } }));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Photo too heavy: try another one'));
	});

	it('reads a network failure as a plain failure', async () => {
		fetch.mockRejectedValue(new TypeError('Failed to fetch'));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('The change failed: try again later'));
		expect(navigation.invalidateAll).not.toHaveBeenCalled();
	});

	it('reloads after a timeout, since the save may have gone through, and says it failed', async () => {
		fetch.mockRejectedValue(new DOMException('signal timed out', 'TimeoutError'));
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('The change failed: try again later'));
		expect(navigation.invalidateAll).toHaveBeenCalledTimes(1);
		expect(fetch.mock.calls[0][1].signal).toBeDefined();
		expect(screen.getByRole('dialog')).toBeInTheDocument();
	});

	it('switches to the locked view when an organiser locked uploads meanwhile, saying it once', async () => {
		fetch.mockResolvedValue(
			actionResult({ type: 'failure', status: 403, data: { action: 'photo', error: 'photo.error.photo_locked' } })
		);
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier });
		// The reload brings the layout's `me.photo_locked` down to the prop.
		navigation.invalidateAll.mockImplementationOnce(() => component.$set({ locked: true }));
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(navigation.invalidateAll).toHaveBeenCalledTimes(1));
		const notice = await waitFor(() => screen.getByText('Photo uploads have been turned off by an organiser'));
		await waitFor(() => expect(notice).toHaveFocus());
		expect(screen.getAllByText('Photo uploads have been turned off by an organiser')).toHaveLength(1);
		expect(screen.queryByRole('alert')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
		expect(screen.getByRole('button', { name: 'Delete my photo' })).not.toHaveAttribute('aria-disabled');
	});

	it('deletes the photo through ?/removePhoto, then reloads and closes, locked or not', async () => {
		const { component } = renderWith(PhotoEditor, { open: true, photo, locked: true, name: xavier });
		const closed = vi.fn();
		component.$on('close', closed);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete my photo' }));
		await waitFor(() => expect(closed).toHaveBeenCalledTimes(1));
		const [url, options] = fetch.mock.calls[0];
		expect(url).toBe('?/removePhoto');
		expect(options.method).toBe('POST');
		expect(options.body).toBeInstanceOf(FormData);
		expect(navigation.invalidateAll).toHaveBeenCalledTimes(1);
	});

	it('gives focus back to the opener on Cancel, and closes on Escape and the backdrop', async () => {
		const opener = document.createElement('button');
		document.body.append(opener);
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier, opener });
		const closed = vi.fn();
		component.$on('close', closed);
		await tick();
		await tick();

		expect(screen.getByRole('dialog')).toHaveFocus();
		await fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
		expect(closed).toHaveBeenCalledTimes(1);
		expect(opener).toHaveFocus();

		await fireEvent.keyDown(window, { key: 'Escape' });
		expect(closed).toHaveBeenCalledTimes(2);
		await fireEvent.click(screen.getByTestId('backdrop'));
		expect(closed).toHaveBeenCalledTimes(3);
		opener.remove();
	});

	it('gives focus back to the opener after a successful save', async () => {
		const opener = document.createElement('button');
		document.body.append(opener);
		renderWith(PhotoEditor, { open: true, photo, name: xavier, opener });
		await choose();

		await fireEvent.click(screen.getByRole('button', { name: 'Save' }));
		await waitFor(() => expect(opener).toHaveFocus());
		opener.remove();
	});

	it('traps Tab inside the dialog, wrapping both ways', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await tick();
		await tick();

		const input = screen.getByLabelText('Choose a photo');
		const cancel = screen.getByRole('button', { name: 'Cancel' });
		// Save is disabled until a file is chosen, so Cancel is the last stop.
		cancel.focus();
		await fireEvent.keyDown(window, { key: 'Tab' });
		expect(input).toHaveFocus();
		await fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
		expect(cancel).toHaveFocus();
	});

	it('locks the page scroll while open', async () => {
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier });
		expect(document.body.style.overflow).toBe('hidden');
		await component.$set({ open: false });
		expect(document.body.style.overflow).toBe('');
	});

	it('starts again from the current photo when reopened', async () => {
		const { component } = renderWith(PhotoEditor, { open: true, photo, name: xavier });
		await choose();
		await component.$set({ open: false });
		await component.$set({ open: true });

		expect(screen.queryByRole('application')).toBeNull();
		expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
	});

	it('speaks French', async () => {
		renderWith(PhotoEditor, { open: true, photo, name: xavier }, 'fr');

		const dialog = screen.getByRole('dialog', { name: 'Ma photo' });
		expect(dialog).toHaveTextContent('Votre photo sera visible publiquement sur le site.');
		expect(screen.getByRole('button', { name: 'Supprimer ma photo' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Annuler' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled();
		await fireEvent.change(screen.getByLabelText('Choisir une photo'), { target: { files: [jpegFile()] } });
		const crop = await waitFor(() => screen.getByRole('application', { name: 'Cadrage de la photo' }));
		expect(crop).toHaveAccessibleDescription(
			'Faites glisser la photo pour la cadrer, ou utilisez les flèches ; + et − pour zoomer.'
		);
		const slider = screen.getByRole('slider', { name: 'Zoom' });
		await fireEvent.input(slider, { target: { value: '1.5' } });
		expect(slider.getAttribute('aria-valuetext')).toMatch(/^150\s%$/);
	});

	it('speaks French when locked', () => {
		renderWith(PhotoEditor, { open: true, photo, locked: true, name: xavier }, 'fr');

		expect(screen.getByRole('dialog')).toHaveTextContent("L'ajout de photo a été désactivé par un organisateur");
		expect(screen.getByRole('button', { name: 'Fermer' })).toBeInTheDocument();
	});
});
