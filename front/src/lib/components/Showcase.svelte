<script>
	import Badge from './Badge.svelte';
	import BadgeSheet from './BadgeSheet.svelte';
	import { isKnownBadge, slotLabel } from '$lib/badges';
	import { useT } from '$lib/i18n';

	/**
	 * The showcase, `[{ code, tier, discipline }]` in display order: a /profiles/ row's
	 * `showcase`, or the `showcase.badges` of /profile/<id>/. Each medallion is drawn from its
	 * entry, which the server picks the way a collection slot picks its medal (the highest
	 * tier, else the first entry), so the metal, the pips and a specialist's discipline icon
	 * match the collection.
	 */
	export let badges = [];
	/**
	 * 'row': a leaderboard row, which is one link and cannot hold buttons, so the medallions
	 * are aria-hidden at 20px and the row's hidden sentence names them (`showcaseLabel`).
	 * 'interactive': the profile header, each medallion a button opening its BadgeSheet.
	 */
	export let mode = 'row';
	/** interactive: the page's `badgeCollection(profile.badges)`, holding each medallion's slot. */
	export let collection = null;
	/** interactive: the profile's `badge_stats`, for the sheet's rarity line, or null. */
	export let badgeStats = null;

	const t = useT();

	$: slots = new Map((collection?.families ?? []).flatMap((family) => family.slots).map((slot) => [slot.code, slot]));
	// A code the front does not know (a newer server) is left out. So is, in the header, a
	// code without an earned slot to open: the showcase and the badges come from the same
	// rows, so only a payload at odds with itself would have one.
	$: shown = (badges ?? []).filter(
		(badge) => isKnownBadge(badge) && (mode !== 'interactive' || slots.get(badge.code)?.earned)
	);

	// The sheet opens and gives focus back the way BadgeCollection's does.
	/** The code of the medallion whose sheet is open, or null. */
	let openCode = null;
	/** The button that opened the sheet, refocused when it closes. */
	let openButton = null;

	$: activeSlot = openCode ? (slots.get(openCode) ?? null) : null;

	function openSheet(code, event) {
		openCode = code;
		openButton = event.currentTarget;
	}

	function closeSheet() {
		openCode = null;
		openButton?.focus();
		openButton = null;
	}
</script>

<!-- Nothing at all without a badge to show: no empty line under the name. -->
{#if shown.length > 0}
	{#if mode === 'interactive'}
		<ul class="showcase interactive" role="list" aria-label={t('showcase.label')} data-testid="showcase">
			{#each shown as badge}
				<li>
					<button
						type="button"
						aria-label={slotLabel(slots.get(badge.code), t)}
						on:click={(event) => openSheet(badge.code, event)}
					>
						<Badge {badge} />
					</button>
				</li>
			{/each}
		</ul>
		<BadgeSheet slot={activeSlot} open={activeSlot !== null} {badgeStats} on:close={closeSheet} />
	{:else}
		<span class="showcase row" style:--badge-size="20px" aria-hidden="true" data-testid="showcase">
			{#each shown as badge}
				<Badge {badge} />
			{/each}
		</span>
	{/if}
{/if}

<style>
	.showcase {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
	}

	.row {
		gap: 4px;
	}

	.interactive {
		gap: 6px;
		--badge-size: 40px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.interactive button {
		display: grid;
		place-items: center;
		padding: 3px;
		background: none;
		border: none;
		border-radius: var(--radius);
		color: inherit;
		font: inherit;
		cursor: pointer;
		transition: transform 0.2s ease;
	}

	.interactive button:hover {
		transform: translateY(-2px);
	}

	.interactive button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	@media (min-width: 600px) {
		.interactive {
			gap: 8px;
			--badge-size: 48px;
		}
	}
</style>
