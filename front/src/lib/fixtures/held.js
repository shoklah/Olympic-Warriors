/**
 * Payload of /disciplines/all-time/, every discipline an active edition ever held, in the
 * server's database-name order: Blindtest (2024, 2025), Dodgeball (2025 only; Balle au
 * prisonnier in French, so first there), Hide and Seek (2026 only) and Relay (2023, 2024
 * and 2026, the last as id 10, the summary fixture's Relay).
 */
export const held = [
	{
		name: 'Blindtest',
		editions: [
			{ year: 2024, discipline: 21 },
			{ year: 2025, discipline: 31 }
		]
	},
	{ name: 'Dodgeball', editions: [{ year: 2025, discipline: 32 }] },
	{ name: 'Hide and Seek', editions: [{ year: 2026, discipline: 14 }] },
	{
		name: 'Relay',
		editions: [
			{ year: 2023, discipline: 3 },
			{ year: 2024, discipline: 7 },
			{ year: 2026, discipline: 10 }
		]
	}
];
