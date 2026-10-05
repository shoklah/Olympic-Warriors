import { fireEvent, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import { builderPayload } from '$lib/fixtures/builder.js';
import PlayerSheet from './PlayerSheet.svelte';

const { players, skills } = builderPayload;
const byId = (id) => players.find((p) => p.id === id);
const props = (id, over = {}) => ({ open: true, player: byId(id), skills, teamIndex: -1, ...over });
const dialog = () => screen.getByRole('dialog', { name: /./ });

describe('PlayerSheet', () => {
	it('renders nothing while closed', () => {
		renderWith(PlayerSheet, props(1, { open: false }));

		expect(screen.queryByRole('dialog')).toBeNull();
	});

	it('shows the name, the summary and one bar per skill', () => {
		renderWith(PlayerSheet, props(1, { player: { ...byId(1), global_level: 6 } }));

		const sheet = within(screen.getByRole('dialog', { name: 'Léa Martin' }));
		expect(sheet.getByText('To place')).toBeInTheDocument();
		expect(sheet.getByText('Rating').parentElement).toHaveTextContent(/Rating\s*8/);
		expect(sheet.getByText('Overall level').parentElement).toHaveTextContent(/Overall level\s*6/);
		expect(sheet.getByText('At least four hours a week')).toBeInTheDocument();
		expect(sheet.getByText('Cardio').parentElement).toHaveTextContent('9');
		expect(sheet.getByText('Strength').parentElement).toHaveTextContent('7');
		expect(sheet.queryByText('estimated')).toBeNull();
		expect(sheet.queryByText('Incomplete profile')).toBeNull();
	});

	it('says which team the player is in', () => {
		renderWith(PlayerSheet, props(1, { teamIndex: 2 }));

		expect(within(dialog()).getByText('Team 3')).toBeInTheDocument();
	});

	it('marks estimated skills and the incomplete profile, and shows a dash for what is unknown', () => {
		renderWith(PlayerSheet, props(5, { player: { ...byId(5), global_level: null } }));

		const sheet = within(dialog());
		expect(sheet.getAllByText('estimated')).toHaveLength(2);
		expect(sheet.getByText('Incomplete profile')).toBeInTheDocument();
		expect(sheet.getByText('Overall level').parentElement).toHaveTextContent(/Overall level\s*—/);
		expect(sheet.getByText('Sport frequency').parentElement).toHaveTextContent(/Sport frequency\s*—/);
	});

	it('lists the sports with their level, or says there is none', () => {
		const { unmount } = renderWith(PlayerSheet, props(3));
		expect(within(dialog()).getByText('Judo · In a club, with competitions')).toBeInTheDocument();
		unmount();

		renderWith(PlayerSheet, props(1));
		expect(within(dialog()).getByText('No sport given')).toBeInTheDocument();
	});

	it('closes on Escape and on its button', async () => {
		const { component } = renderWith(PlayerSheet, props(1));
		let closed = 0;
		component.$on('close', () => closed++);

		await fireEvent.keyDown(window, { key: 'Escape' });
		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));

		expect(closed).toBe(2);
	});

	it('gives focus back to the opener on close', async () => {
		const opener = document.createElement('button');
		document.body.append(opener);
		renderWith(PlayerSheet, props(1, { opener }));
		await tick();

		await fireEvent.click(screen.getByRole('button', { name: 'Close' }));

		expect(document.activeElement).toBe(opener);
		opener.remove();
	});

	it('speaks French', () => {
		renderWith(PlayerSheet, props(3, { teamIndex: 0 }), 'fr');

		const sheet = within(screen.getByRole('dialog', { name: 'Paul Petit' }));
		expect(sheet.getByText('Équipe 1')).toBeInTheDocument();
		expect(sheet.getByText('Force')).toBeInTheDocument();
		expect(sheet.getByRole('button', { name: 'Fermer' })).toBeInTheDocument();
	});
});
