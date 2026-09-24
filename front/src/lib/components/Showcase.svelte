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
	/** interactive: the owner looks at an automatic showcase, so a quiet line says how it is picked. */
	export let autoHint = false;

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
						aria-describedby="showcase-rule-{badge.code}"
						on:click={(event) => openSheet(badge.code, event)}
					>
						<Badge {badge} />
						<!-- The rule as the description, as on the collection's slots (without their
						     hover tooltip: the sheet this opens states the rule too). -->
						<span id="showcase-rule-{badge.code}" class="visually-hidden">{t(`badge.${badge.code}.rule`)}</span>
					</button>
				</li>
			{/each}
		</ul>
		{#if autoHint}
			<p class="hint">{t('showcase.autoHint')}</p>
		{/if}
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
		align-items: center;
	}

	/* Badge draws a pip row under each ring: its gap (8% of the size) then its pips (7%, at
	   least 5px). A page setting `--showcase-hang: 1`, where the medallions sit inline after
	   a name, lets that row hang below the line: the rings then centre on the name and a row
	   with a showcase is no taller than one without. */
	.row {
		flex: none;
		gap: 4px;
		margin-bottom: calc(
			var(--showcase-hang, 0) * -1 * (var(--badge-size) * 0.08 + max(5px, var(--badge-size) * 0.07))
		);
	}

	/* Pulled back by the buttons' padding, so the rings line up with the name above. */
	.interactive {
		flex-wrap: wrap;
		gap: 6px;
		--badge-size: 40px;
		margin: 0;
		margin-inline-start: -3px;
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

	.hint {
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
	}

	@media (min-width: 600px) {
		.interactive {
			gap: 8px;
			--badge-size: 48px;
		}
	}
</style>
