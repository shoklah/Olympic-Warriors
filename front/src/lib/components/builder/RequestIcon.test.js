import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import RequestIcon from './RequestIcon.svelte';

const paths = (name) => [...render(RequestIcon, { name }).container.querySelectorAll('svg path')].map((p) => p.getAttribute('d'));

describe('RequestIcon', () => {
	it('is hidden from assistive technology: the state is always said in words beside it', () => {
		const { container } = render(RequestIcon, { name: 'check' });

		expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
	});

	it('draws a circle with a different mark for each state', () => {
		const marks = ['question', 'check', 'minus'].map((name) => paths(name).join('|'));

		expect(new Set(marks).size).toBe(3);
		expect(paths('check')).toEqual(['M8 12.5l3 3 5-6']);
		expect(paths('minus')).toEqual(['M8 12h8']);
	});
});
