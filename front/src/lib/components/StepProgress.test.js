import { fireEvent, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import StepProgress from './StepProgress.svelte';

const steps = [
	{ n: 1, label: 'One' },
	{ n: 2, label: 'Two' },
	{ n: 3, label: 'Three' }
];
const props = (over = {}) => ({ steps, step: 2, label: 'Steps', ofText: (n, total) => `Step ${n} of ${total}`, ...over });

describe('StepProgress', () => {
	it('shows the step text and a progress bar', () => {
		renderWith(StepProgress, props());

		expect(screen.getByText('Step 2 of 3')).toBeInTheDocument();
		const bar = screen.getByRole('progressbar', { name: 'Steps' });
		expect(bar).toHaveAttribute('aria-valuemin', '1');
		expect(bar).toHaveAttribute('aria-valuemax', '3');
		expect(bar).toHaveAttribute('aria-valuenow', '2');
		expect(bar).toHaveAttribute('aria-valuetext', 'Step 2 of 3');
	});

	it('accepts a ready string for the text', () => {
		renderWith(StepProgress, props({ ofText: 'Étape 2 sur 3' }));
		expect(screen.getByText('Étape 2 sur 3')).toBeInTheDocument();
	});

	it('marks the current step and disables unreachable ones', () => {
		renderWith(StepProgress, props({ canGo: (n) => n <= 2 }));

		expect(screen.getByRole('button', { name: 'Two' })).toHaveAttribute('aria-current', 'step');
		expect(screen.getByRole('button', { name: 'One' })).not.toHaveAttribute('aria-current');
		expect(screen.getByRole('button', { name: 'Three' })).toBeDisabled();
		expect(screen.getByRole('button', { name: 'One' })).toBeEnabled();
	});

	it('emits go with the step number', async () => {
		const { component } = renderWith(StepProgress, props());
		const seen = [];
		component.$on('go', (e) => seen.push(e.detail));

		await fireEvent.click(screen.getByRole('button', { name: 'Three' }));

		expect(seen).toEqual([3]);
	});

	it('can be hidden', () => {
		const { container } = renderWith(StepProgress, props({ hidden: true }));
		expect(container.querySelector('nav')).toHaveAttribute('hidden');
	});
});
