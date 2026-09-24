<script>
	import { createEventDispatcher, tick } from 'svelte';
	import Avatar from './Avatar.svelte';
	import Badge from './Badge.svelte';
	import { badgeDetail, badgeRarity, badgeTier, isTiered, nextThreshold } from '$lib/badges';
	import { fullName } from '$lib/players';
	import { modal } from '$lib/modal';
	import { useLocale, useT } from '$lib/i18n';

	/** A slot from badgeCollection: { code, entries, count, earned, medal }, or null. */
	export let slot = null;
	export let open = false;
	/** The profile's `badge_stats` ({ players, holders, tiers }), or null (an older API). */
	export let badgeStats = null;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();

	/** The sheet itself, focused when it opens, like ScoreSheet. */
	let sheetEl = null;
	$: if (open && sheetEl) tick().then(() => sheetEl?.focus());

	const close = () => dispatch('close');

	$: tiered = slot ? isTiered(slot.code) : false;
	$: titleId = slot ? `badge-sheet-title-${slot.code}` : null;
	/** The first tier's threshold for a locked tiered slot (slot.medal.tier is 0). */
	$: firstGoal = slot && tiered && !slot.earned ? nextThreshold(slot.code, 0) : null;

	/** The badge's overall share of players, or null without badge_stats. */
	$: rarity = slot ? badgeRarity(badgeStats, slot.code) : null;
	/** A second share at the profile owner's own tier, only for an earned tiered badge. */
	$: tierRarity = slot && tiered && slot.earned ? badgeRarity(badgeStats, slot.code, badgeTier(slot.medal)) : null;
</script>

{#if open && slot}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-labelledby={titleId}
		tabindex="-1"
		bind:this={sheetEl}
		use:modal={{ onClose: close }}
	>
		<div class="medallion" style="--badge-size: 64px">
			<Badge badge={slot.medal} locked={!slot.earned} />
		</div>
		<h2 id={titleId}>{t(`badge.${slot.code}.name`)}</h2>
		<p class="status">
			{t(slot.earned ? 'badge.statusEarned' : 'badge.statusLocked')}
			{#if slot.earned && slot.count > 1}
				<span aria-hidden="true"> · {t('badge.times', { n: slot.count })}</span>
				<span class="visually-hidden"> {t('badge.timesSpoken', { n: slot.count })}</span>
			{/if}
		</p>
		<p class="rule">{t(`badge.${slot.code}.rule`)}</p>

		{#if rarity}
			<p class="rarity">
				{#if rarity.holders === 0}
					{t('badge.rarityNone')}
				{:else if rarity.percent === 0}
					{t('badge.rarityUnder1', { holders: rarity.holders, players: rarity.players })}
				{:else}
					{t('badge.rarity', { percent: rarity.percent, holders: rarity.holders, players: rarity.players })}
				{/if}
			</p>
			{#if tierRarity && tierRarity.holders > 0}
				<p class="rarity">
					{#if tierRarity.percent === 0}
						{t('badge.rarityTierUnder1', {
							tier: badgeTier(slot.medal),
							holders: tierRarity.holders,
							players: tierRarity.players
						})}
					{:else}
						{t('badge.rarityTier', {
							percent: tierRarity.percent,
							tier: badgeTier(slot.medal),
							holders: tierRarity.holders,
							players: tierRarity.players
						})}
					{/if}
				</p>
			{/if}
		{/if}

		{#if slot.earned}
			<ul class="entries" role="list">
				{#each slot.entries as entry}
					{@const parts = badgeDetail(entry, t, locale)}
					{@const next = tiered ? nextThreshold(entry.code, badgeTier(entry)) : null}
					<li class="entry">
						{#if entry.partner || parts.length}
							<span class="detail" data-testid="badge-sheet-detail">
								{#if entry.partner}
									{t('badge.with')}
									<!-- Beside the link, not in it: the link keeps its underline on the name alone. -->
									<span class="partner-avatar"
										><Avatar photo={entry.partner.photo ?? null} name={entry.partner} size={24} /></span
									>
									<a class="quiet-link" href="/players/{entry.partner.id}">{fullName(entry.partner)}</a>
								{/if}
								{#each parts as part, i}{#if i > 0 || entry.partner}{' '}<span class="sep" aria-hidden="true"
											>·</span
										>{' '}{/if}<span>{part}</span>{/each}
							</span>
						{/if}
						{#if tiered}
							<span class="goal">{next !== null ? t(`badge.next.${entry.code}`, { n: next }) : t('badge.topTier')}</span>
						{/if}
					</li>
				{/each}
			</ul>
		{:else if tiered}
			<p class="goal">{t(`badge.first.${slot.code}`, { n: firstGoal })}</p>
		{/if}

		<div class="actions">
			<button type="button" on:click={close}>{t('badge.close')}</button>
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
	}

	.medallion {
		display: flex;
		justify-content: center;
		margin-bottom: 0.6rem;
	}

	h2 {
		margin: 0 0 0.2rem;
		text-align: center;
	}

	.status {
		margin: 0 0 0.8rem;
		text-align: center;
		color: var(--muted);
	}

	.rule {
		margin: 0 0 1rem;
		font-size: 0.9rem;
		line-height: 1.4;
		text-align: center;
		color: var(--muted);
	}

	.rarity {
		margin: -0.4rem 0 0.8rem;
		font-size: 0.85rem;
		text-align: center;
		color: var(--muted);
	}

	.rarity + .rarity {
		margin-top: -0.6rem;
	}

	.entries {
		margin: 0 0 1rem;
		padding: 0;
		text-align: center;
		list-style: none;
	}

	.entry {
		padding: 0.5rem 0;
		border-top: 1px solid var(--line);
	}

	.entry:first-child {
		border-top: none;
	}

	.detail {
		font-size: 0.9rem;
		color: var(--text);
		overflow-wrap: anywhere;
	}

	.detail a {
		color: var(--accent);
	}

	.detail a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	/* Centred on the line of text rather than sitting on its baseline. */
	.partner-avatar {
		display: inline-flex;
		vertical-align: middle;
	}

	.sep {
		color: var(--ghost);
	}

	.goal {
		display: block;
		margin-top: 0.15rem;
		font-size: 0.85rem;
		text-align: center;
		color: var(--muted);
	}

	.actions {
		display: flex;
		justify-content: center;
	}

	.actions button {
		min-height: 44px;
		padding: 0 1.2rem;
		border-radius: var(--radius);
		font-family: var(--font-display);
		font-size: 1.1rem;
		letter-spacing: 0.1em;
		background: var(--accent);
		color: var(--bg);
		border: 1px solid var(--accent);
		cursor: pointer;
	}

	.actions button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
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
