<script>
	import { createEventDispatcher, onDestroy, tick } from 'svelte';
	import { deserialize } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import Avatar from './Avatar.svelte';
	import {
		EXPORT_BACKGROUND,
		MAX_ZOOM,
		MIN_ZOOM,
		OUTPUT_QUALITY,
		OUTPUT_SIZE,
		OUTPUT_TYPE,
		initialCrop,
		panBy,
		sourceRect,
		zoomTo
	} from '$lib/crop';
	import { useLocale, useT } from '$lib/i18n';

	/** Whether the dialog is shown; the page closes it on the `close` event. */
	export let open = false;
	/** The current photo, `{ large, small }`, or null: « Supprimer ma photo » needs one. */
	export let photo = null;
	/** An organiser turned uploads off (`me.photo_locked`): only the delete button is left. */
	export let locked = false;
	/** The person's name, `{ first_name, last_name }`, for the initials without a photo. */
	export let name = null;
	/** The element given focus back when the dialog closes (the camera button). */
	export let opener = null;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();

	/** What the file input offers; iOS hands a HEIC photo over as JPEG. */
	const ACCEPT = ['image/jpeg', 'image/png', 'image/webp'];
	const FAILED = 'photo.error.failed';
	/** The preview's side in CSS pixels, drawn at up to twice that for a sharp retina preview. */
	const PREVIEW = 280;
	const pixels =
		typeof window === 'undefined' ? PREVIEW : Math.round(PREVIEW * Math.min(2, window.devicePixelRatio || 1));
	/** An arrow press moves the image this many CSS pixels (five times that with Shift). */
	const KEY_STEP = 10;
	const ZOOM_STEP = 0.1;
	const MOVES = new Map([
		['ArrowLeft', [-1, 0]],
		['ArrowRight', [1, 0]],
		['ArrowUp', [0, -1]],
		['ArrowDown', [0, 1]]
	]);
	/** A save or delete that never answers gives the buttons back after this long. */
	const TIMEOUT_MS = 30000;

	let sheetEl = null;
	let canvasEl = null;
	/** The decoded image (an ImageBitmap, or an <img> from the fallback), and its size. */
	let source = null;
	let width = 0;
	let height = 0;
	/** `{ zoom, cx, cy }` from $lib/crop, or null before a file is chosen. */
	let crop = null;
	/** A dictionary key for the alert line, or null. */
	let error = null;
	/** The action on its way ('photo' or 'removePhoto'), or null. */
	let busy = null;
	/** The pointer dragging the image: its id and last position. */
	let drag = null;

	const percent = new Intl.NumberFormat(locale === 'en' ? 'en' : 'fr', { style: 'percent' });

	// The dialog itself takes focus when it opens, like BadgeSheet.
	$: if (open && sheetEl) tick().then(() => sheetEl?.focus());

	/** Close and give focus back to the opener. */
	function close() {
		dispatch('close');
		opener?.focus();
	}

	/** Cancel, Escape and the backdrop: not while a save is on its way, whose answer decides. */
	function dismiss() {
		if (!busy) close();
	}

	/** Forget the chosen file: a reopened dialog starts from the current photo. */
	function reset() {
		source?.close?.();
		source = null;
		crop = null;
		error = null;
		drag = null;
	}
	$: if (!open) reset();

	/** Every element the dialog lets Tab reach, in DOM order. */
	function focusables() {
		if (!sheetEl) return [];
		return [
			...sheetEl.querySelectorAll(
				'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
			)
		];
	}

	/** Escape closes; Tab and Shift+Tab wrap inside the dialog, as in BadgeSheet. */
	const onKey = (event) => {
		if (!open) return;
		if (event.key === 'Escape') {
			dismiss();
			return;
		}
		if (event.key !== 'Tab') return;
		const items = focusables();
		if (items.length === 0) {
			event.preventDefault();
			return;
		}
		const first = items[0];
		const last = items[items.length - 1];
		const active = document.activeElement;
		if (!sheetEl.contains(active)) {
			event.preventDefault();
			(event.shiftKey ? last : first).focus();
			return;
		}
		if (event.shiftKey) {
			if (active === first || active === sheetEl) {
				event.preventDefault();
				last.focus();
			}
		} else if (active === last) {
			event.preventDefault();
			first.focus();
		}
	};

	// The page must not scroll behind the open dialog (BadgeSheet's lock).
	let previousOverflow = null;
	function lockScroll() {
		if (typeof document === 'undefined' || previousOverflow !== null) return;
		previousOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
	}
	function unlockScroll() {
		if (typeof document === 'undefined' || previousOverflow === null) return;
		document.body.style.overflow = previousOverflow;
		previousOverflow = null;
	}
	$: if (open) lockScroll();
	else unlockScroll();
	onDestroy(() => {
		unlockScroll();
		source?.close?.();
	});

	/** Decode through an <img>, for engines whose createImageBitmap refuses the file or the option. */
	function decodeWithImage(file) {
		return new Promise((resolve, reject) => {
			const url = URL.createObjectURL(file);
			const img = new Image();
			img.onload = () => {
				URL.revokeObjectURL(url);
				resolve(img);
			};
			img.onerror = () => {
				URL.revokeObjectURL(url);
				reject(new Error('unreadable'));
			};
			img.src = url;
		});
	}

	/**
	 * The chosen file as something to draw, turned upright from its EXIF orientation, so a
	 * phone photo is not drawn on its side (an <img> applies the orientation by default).
	 */
	async function decode(file) {
		if (typeof createImageBitmap === 'function') {
			try {
				return await createImageBitmap(file, { imageOrientation: 'from-image' });
			} catch {
				// An older engine refuses the option, or the format: the <img> gets a try.
			}
		}
		return decodeWithImage(file);
	}

	async function choose(event) {
		const input = event.currentTarget;
		const file = input.files?.[0];
		// Emptied, so choosing the same file again still fires `change`.
		input.value = '';
		if (!file) return;
		error = null;
		if (file.type && !ACCEPT.includes(file.type)) {
			error = 'photo.error.bad_format';
			return;
		}
		let decoded;
		try {
			decoded = await decode(file);
		} catch {
			error = 'photo.error.unreadable';
			return;
		}
		source?.close?.();
		source = decoded;
		width = decoded.naturalWidth || decoded.width;
		height = decoded.naturalHeight || decoded.height;
		crop = initialCrop(width, height);
	}

	/** Draw the crop into a square `side` pixels wide, on the grey the server flattens onto. */
	function paint(ctx, side, current) {
		ctx.fillStyle = EXPORT_BACKGROUND;
		ctx.fillRect(0, 0, side, side);
		const { sx, sy, sw, sh } = sourceRect(width, height, current);
		ctx.imageSmoothingQuality = 'high';
		ctx.drawImage(source, sx, sy, sw, sh, 0, 0, side, side);
	}

	$: if (canvasEl && source && crop) {
		const ctx = canvasEl.getContext('2d');
		if (ctx) paint(ctx, canvasEl.width, crop);
	}

	/** The preview's drawn width in CSS pixels, which a drag and an arrow press are measured in. */
	const previewSize = () => canvasEl?.getBoundingClientRect().width || PREVIEW;

	/** One pointer drags at a time; the same pointer pressing again takes over its stale drag. */
	function pointerDown(event) {
		if (!crop || (drag && drag.id !== event.pointerId)) return;
		drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
		try {
			event.currentTarget.setPointerCapture?.(event.pointerId);
		} catch {
			// No capture (the pointer is already gone): the drag still follows while over the canvas.
		}
	}

	function pointerMove(event) {
		if (!drag || event.pointerId !== drag.id) return;
		crop = panBy(width, height, crop, event.clientX - drag.x, event.clientY - drag.y, previewSize());
		drag = { ...drag, x: event.clientX, y: event.clientY };
	}

	function pointerUp(event) {
		if (drag && event.pointerId === drag.id) drag = null;
	}

	/** The arrows move the image like a drag, + and - zoom; the page does not scroll meanwhile. */
	function cropKey(event) {
		if (!crop) return;
		const move = MOVES.get(event.key);
		if (move) {
			const step = event.shiftKey ? KEY_STEP * 5 : KEY_STEP;
			crop = panBy(width, height, crop, move[0] * step, move[1] * step, previewSize());
		} else if (event.key === '+' || event.key === '=') {
			crop = zoomTo(width, height, crop, crop.zoom + ZOOM_STEP);
		} else if (event.key === '-' || event.key === '_') {
			crop = zoomTo(width, height, crop, crop.zoom - ZOOM_STEP);
		} else {
			return;
		}
		event.preventDefault();
	}

	const zoomInput = (event) => {
		crop = zoomTo(width, height, crop, Number(event.currentTarget.value));
	};

	/** The crop as a 512px square JPEG, or null when the browser cannot encode it. */
	function exportPhoto() {
		const canvas = document.createElement('canvas');
		canvas.width = OUTPUT_SIZE;
		canvas.height = OUTPUT_SIZE;
		const ctx = canvas.getContext('2d');
		if (!ctx) return Promise.resolve(null);
		paint(ctx, OUTPUT_SIZE, crop);
		return new Promise((resolve) => canvas.toBlob(resolve, OUTPUT_TYPE, OUTPUT_QUALITY));
	}

	/** The key of a fail() from the page's own action, or the generic one. */
	const failureKey = (data) =>
		typeof data?.error === 'string' && data.error.startsWith('photo.error.') ? data.error : FAILED;

	/**
	 * Post `body` to the page's `action` the way use:enhance does (SvelteKit answers an
	 * ActionResult to `x-sveltekit-action`), since the file is a Blob made here, not a form
	 * field. On success the loads re-run, so the header avatar and the account pill change,
	 * then the dialog closes; a failure stays open with its line.
	 */
	async function send(action, body) {
		busy = action;
		error = null;
		try {
			const response = await fetch(`?/${action}`, {
				method: 'POST',
				body,
				headers: { 'x-sveltekit-action': 'true' },
				...(typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
					? { signal: AbortSignal.timeout(TIMEOUT_MS) }
					: {})
			});
			let result = null;
			try {
				result = deserialize(await response.text());
			} catch {
				// Not an ActionResult: a proxy's refusal, such as a 413 for too big a body.
			}
			if (result?.type === 'success') {
				try {
					await invalidateAll();
				} catch {
					// The photo is saved; a load failing now shows its own error page.
				}
				busy = null;
				close();
				return;
			}
			error =
				result?.type === 'failure'
					? failureKey(result.data)
					: response.status === 413
						? 'photo.error.too_large'
						: FAILED;
		} catch {
			error = FAILED;
		}
		busy = null;
	}

	async function save() {
		if (!source || busy) return;
		busy = 'photo';
		error = null;
		let blob = null;
		try {
			blob = await exportPhoto();
		} catch {
			blob = null;
		}
		if (!blob) {
			busy = null;
			error = FAILED;
			return;
		}
		const body = new FormData();
		body.append('photo', blob, 'photo.jpg');
		await send('photo', body);
	}

	function remove() {
		if (!busy) send('removePhoto', new FormData());
	}
</script>

<svelte:window on:keydown={onKey} />

{#if open}
	<div class="backdrop" data-testid="backdrop" on:click={dismiss} aria-hidden="true"></div>
	<div
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-labelledby="photo-editor-title"
		aria-busy={busy ? 'true' : undefined}
		tabindex="-1"
		bind:this={sheetEl}
	>
		<h2 id="photo-editor-title">{t('photo.title')}</h2>

		{#if locked}
			<p class="notice">{t('photo.locked')}</p>
		{:else}
			<div class="stage">
				{#if source}
					<!-- A focusable widget of its own: `application` has screen readers pass the
					     arrows and +/- through instead of reading on, and the canvas inside is only
					     the drawing. Svelte's lint counts `application` as non-interactive, hence: -->
					<!-- svelte-ignore a11y-no-noninteractive-tabindex a11y-no-noninteractive-element-interactions -->
					<div
						class="crop"
						class:dragging={drag !== null}
						tabindex="0"
						role="application"
						aria-label={t('photo.crop')}
						aria-describedby="photo-crop-help"
						on:pointerdown={pointerDown}
						on:pointermove={pointerMove}
						on:pointerup={pointerUp}
						on:pointercancel={pointerUp}
						on:lostpointercapture={pointerUp}
						on:keydown={cropKey}
					>
						<canvas bind:this={canvasEl} width={pixels} height={pixels}></canvas>
						<!-- The circle the avatar shows, the corners dimmed outside it. -->
						<span class="ring" aria-hidden="true"></span>
					</div>
				{:else}
					<Avatar photo={photo?.large ?? null} {name} size={160} />
				{/if}
			</div>

			{#if source}
				<p class="hint" id="photo-crop-help">{t('photo.cropHelp')}</p>
				<div class="zoom">
					<label for="photo-zoom">{t('photo.zoom')}</label>
					<input
						id="photo-zoom"
						type="range"
						min={MIN_ZOOM}
						max={MAX_ZOOM}
						step="0.01"
						value={crop.zoom}
						aria-valuetext={percent.format(crop.zoom)}
						disabled={busy !== null}
						on:input={zoomInput}
					/>
				</div>
			{/if}

		{/if}

		<!-- The two ways to change what shows: another photo, or none. -->
		{#if !locked || photo}
			<div class="choose">
				{#if !locked}
					<input
						class="file visually-hidden"
						id="photo-file"
						type="file"
						accept={ACCEPT.join(',')}
						disabled={busy !== null}
						on:change={choose}
					/>
					<label for="photo-file">{t('photo.choose')}</label>
				{/if}
				{#if photo}
					<button type="button" class="remove" disabled={busy !== null} on:click={remove}>{t('photo.remove')}</button>
				{/if}
			</div>
		{/if}
		{#if !locked}
			<p class="public">{t('photo.public')}</p>
		{/if}

		<!-- On one line, so an idle status is :empty and takes no room. -->
		<p class="progress" role="status">{busy === 'photo' ? t('photo.saving') : busy === 'removePhoto' ? t('photo.removing') : ''}</p>
		{#if error}
			<p class="error" role="alert">{t(error)}</p>
		{/if}

		<div class="actions">
			<button type="button" class="ghost" disabled={busy !== null} on:click={dismiss}
				>{t(locked ? 'photo.close' : 'photo.cancel')}</button
			>
			{#if !locked}
				<button type="button" disabled={!source || busy !== null} on:click={save}>{t('photo.save')}</button>
			{/if}
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		background: var(--scrim);
		z-index: 30;
	}

	/* BadgeSheet's sheet: a bottom sheet on phones, a centred dialog from 1000px. */
	.sheet {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 31;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg) var(--radius-lg) 0 0;
		padding: 1rem 1rem calc(1rem + env(safe-area-inset-bottom));
		max-height: 90vh;
		max-height: 90dvh;
		overflow-y: auto;
		overscroll-behavior: contain;
		text-align: center;
	}

	h2 {
		margin: 0 0 0.8rem;
	}

	.notice {
		margin: 0 0 1rem;
		color: var(--text);
	}

	.stage {
		display: flex;
		justify-content: center;
		margin-bottom: 0.8rem;
	}

	/* No touch-action: a finger drags the photo instead of scrolling the sheet. */
	.crop {
		position: relative;
		width: min(280px, 100%);
		aspect-ratio: 1;
		overflow: hidden;
		border-radius: var(--radius);
		cursor: grab;
		touch-action: none;
	}

	.crop.dragging {
		cursor: grabbing;
	}

	.crop:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	canvas {
		display: block;
		width: 100%;
		height: 100%;
	}

	.ring {
		position: absolute;
		inset: 0;
		border-radius: 50%;
		box-shadow: 0 0 0 100vmax var(--scrim);
		pointer-events: none;
	}

	.hint {
		margin: 0 0 0.6rem;
		font-size: 0.85rem;
		line-height: 1.4;
		color: var(--muted);
	}

	.zoom {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.8rem;
		margin-bottom: 0.8rem;
		color: var(--text);
	}

	.zoom input {
		width: min(200px, 60%);
		min-height: 44px;
		accent-color: var(--accent);
	}

	.choose {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.6rem;
		margin-bottom: 0.8rem;
	}

	/* The label is the button: the file input itself stays focusable but unseen. */
	.choose label,
	.choose button,
	.actions button {
		display: inline-flex;
		align-items: center;
		min-height: 44px;
		padding: 0 1.2rem;
		border: 1px solid var(--accent);
		border-radius: var(--radius);
		background: transparent;
		color: var(--accent);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		cursor: pointer;
	}

	.choose .remove {
		color: var(--loss);
		border-color: var(--loss);
	}

	.file:focus-visible + label,
	.choose button:focus-visible,
	.actions button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.file:disabled + label,
	.choose button:disabled,
	.actions button:disabled {
		opacity: 0.35;
		cursor: default;
	}

	.public {
		margin: 0 0 0.4rem;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.progress {
		margin: 0 0 0.6rem;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.progress:empty {
		margin: 0;
	}

	.error {
		margin: 0 0 0.6rem;
		color: var(--loss);
		font-size: 0.85rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
		margin-top: 0.8rem;
	}

	/* Save is the one filled button. */
	.actions button:not(.ghost) {
		background: var(--accent);
		color: var(--bg);
	}

	@media (min-width: 1000px) {
		.sheet {
			left: 50%;
			right: auto;
			bottom: auto;
			top: 50%;
			width: 420px;
			transform: translate(-50%, -50%);
			border-radius: var(--radius-lg);
		}
	}
</style>
