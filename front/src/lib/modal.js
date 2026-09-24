/**
 * The keyboard and scroll handling shared by the two sheets (BadgeSheet, ScoreSheet), as a
 * Svelte action on the dialog element: `use:modal={{ onClose }}`. Each sheet renders its
 * dialog only while open, so the action lives exactly as long as the sheet is open. The
 * initial focus stays with each sheet (ScoreSheet focuses its first field on desktop).
 */

const FOCUSABLE = [
	'a[href]',
	'button:not([disabled])',
	'input:not([disabled]):not([type="hidden"])',
	'select:not([disabled])',
	'textarea:not([disabled])',
	'[tabindex]:not([tabindex="-1"])'
].join(', ');

/** Every element Tab reaches inside `node`, in DOM order. A hidden input is no Tab stop:
    counting ScoreSheet's hidden game id as the first one would let Shift+Tab escape. */
export function focusables(node) {
	return node ? [...node.querySelectorAll(FOCUSABLE)] : [];
}

/** Tab/Shift+Tab wraps inside `node`, since aria-modal alone doesn't stop the browser
    sending focus to the page behind it (no jsdom support for native <dialog>.showModal()). */
function trapTab(event, node) {
	const items = focusables(node);
	if (items.length === 0) {
		event.preventDefault();
		return;
	}
	const first = items[0];
	const last = items[items.length - 1];
	const active = document.activeElement;
	// Focus landed outside the sheet altogether (e.g. a stray click on the page behind the
	// backdrop): pull it back in rather than letting Tab carry on from there.
	if (!node.contains(active)) {
		event.preventDefault();
		(event.shiftKey ? last : first).focus();
		return;
	}
	if (event.shiftKey) {
		if (active === first || active === node) {
			event.preventDefault();
			last.focus();
		}
	} else if (active === last) {
		event.preventDefault();
		first.focus();
	}
}

/** Escape calls `onClose`, Tab stays inside the node, and the page behind does not scroll. */
export function modal(node, { onClose } = {}) {
	let close = onClose;
	const onKey = (event) => {
		if (event.key === 'Escape') close?.();
		else if (event.key === 'Tab') trapTab(event, node);
	};
	window.addEventListener('keydown', onKey);

	const previousOverflow = document.body.style.overflow;
	document.body.style.overflow = 'hidden';

	return {
		update(params) {
			close = params?.onClose;
		},
		destroy() {
			window.removeEventListener('keydown', onKey);
			document.body.style.overflow = previousOverflow;
		}
	};
}
