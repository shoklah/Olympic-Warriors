import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { focusables, modal } from './modal';

/** A sheet holding a hidden input, then a link, a text field and a button, like the two sheets. */
function sheet() {
	const node = document.createElement('div');
	node.tabIndex = -1;
	node.innerHTML = `
		<input type="hidden" name="game" value="1" />
		<a href="/players/1">Léa</a>
		<input name="score" />
		<button type="button" disabled>Off</button>
		<button type="button">Save</button>`;
	document.body.appendChild(node);
	return node;
}

const tab = (shiftKey = false) => {
	const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, bubbles: true, cancelable: true });
	window.dispatchEvent(event);
	return event;
};

let node;
let action;

beforeEach(() => {
	document.body.style.overflow = '';
	node = sheet();
});

afterEach(() => {
	action?.destroy();
	action = null;
	document.body.innerHTML = '';
	document.body.style.overflow = '';
});

describe('focusables', () => {
	it('lists what Tab reaches, in DOM order, skipping hidden inputs and disabled controls', () => {
		expect(focusables(node).map((el) => el.textContent || el.name)).toEqual(['Léa', 'score', 'Save']);
	});

	it('is empty without a node', () => {
		expect(focusables(null)).toEqual([]);
	});
});

describe('modal', () => {
	it('wraps Tab from the last focusable to the first, and Shift+Tab back', () => {
		action = modal(node);
		const [link, , save] = focusables(node);

		save.focus();
		expect(tab().defaultPrevented).toBe(true);
		expect(link).toHaveFocus();

		expect(tab(true).defaultPrevented).toBe(true);
		expect(save).toHaveFocus();
	});

	it('lets Tab move normally between the ends', () => {
		action = modal(node);
		const [link] = focusables(node);
		link.focus();
		expect(tab().defaultPrevented).toBe(false);
	});

	it('sends Shift+Tab from the sheet itself to the last focusable', () => {
		action = modal(node);
		node.focus();
		tab(true);
		expect(focusables(node).at(-1)).toHaveFocus();
	});

	it('pulls focus back inside when it has landed outside the sheet', () => {
		const outside = document.createElement('button');
		document.body.appendChild(outside);
		action = modal(node);
		const [link, , save] = focusables(node);

		outside.focus();
		tab();
		expect(link).toHaveFocus();

		outside.focus();
		tab(true);
		expect(save).toHaveFocus();
	});

	it('keeps Tab from leaving a sheet with nothing to focus', () => {
		node.innerHTML = '<p>Nothing here</p>';
		action = modal(node);
		expect(tab().defaultPrevented).toBe(true);
	});

	it('calls onClose on Escape, the latest one after an update', () => {
		const first = vi.fn();
		const second = vi.fn();
		action = modal(node, { onClose: first });
		window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
		expect(first).toHaveBeenCalledTimes(1);

		action.update({ onClose: second });
		window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
		expect(first).toHaveBeenCalledTimes(1);
		expect(second).toHaveBeenCalledTimes(1);
	});

	it('locks the page scroll while mounted and restores the previous value', () => {
		document.body.style.overflow = 'auto';
		action = modal(node);
		expect(document.body.style.overflow).toBe('hidden');
		action.destroy();
		action = null;
		expect(document.body.style.overflow).toBe('auto');
	});

	it('stops listening once destroyed', () => {
		const onClose = vi.fn();
		action = modal(node, { onClose });
		action.destroy();
		action = null;
		window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
		expect(onClose).not.toHaveBeenCalled();
		expect(tab().defaultPrevented).toBe(false);
	});
});
