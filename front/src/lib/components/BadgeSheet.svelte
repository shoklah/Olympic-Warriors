<script>
	import { createEventDispatcher, tick } from 'svelte';
	import Badge from './Badge.svelte';
	import { badgeDetail, badgeTier, isTiered, nextThreshold } from '$lib/badges';
	import { fullName } from '$lib/players';
	import { useLocale, useT } from '$lib/i18n';

	/** A slot from badgeCollection: { code, entries, count, earned, medal }, or null. */
	export let slot = null;
	export let open = false;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();

	/** The sheet itself, focused when it opens, like ScoreSheet. */
	let sheetEl = null;
	$: if (open && sheetEl) tick().then(() => sheetEl?.focus());

	const close = () => dispatch('close');
	const onKey = (event) => {
		if (open && event.key === 'Escape') close();
	};

	$: tiered = slot ? isTiered(slot.code) : false;
	$: titleId = slot ? `badge-sheet-title-${slot.code}` : null;
	/** The first tier's threshold for a locked tiered slot (slot.medal.tier is 0). */
	$: firstGoal = slot && tiered && !slot.earned ? nextThreshold(slot.code, 0) : null;
</script>

<svelte:window on:keydown={onKey} />

{#if open && slot}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div class="sheet" role="dialog" aria-modal="true" aria-labelledby={titleId} tabindex="-1" bind:this={sheetEl}>
		<div class="medallion" style="--badge-size: 64px">
			<Badge badge={slot.medal} locked={!slot.earned} />
		</div>
		<h2 id={titleId}>{t(`badge.${slot.code}.name`)}</h2>
		<p class="status">
			{t(slot.earned ? 'badge.statusEarned' : 'badge.statusLocked')}
			{#if slot.earned && slot.count > 1}
				<span aria-hidden="true"> · </span>{t('badge.times', { n: slot.count })}
			{/if}
		</p>
		<p class="rule">{t(`badge.${slot.code}.rule`)}</p>

		{#if slot.earned}
			<ul class="entries" role="list">
				{#each slot.entries as entry}
					{@const parts = badgeDetail(entry, t, locale)}
					{@const next = tiered ? nextThreshold(entry.code, badgeTier(entry)) : null}
					<li class="entry">
						<span class="detail">
							{#if entry.partner}
								{t('badge.with')}
								<a href="/players/{entry.partner.id}">{fullName(entry.partner)}</a>
							{/if}
							{#each parts as part, i}{#if i > 0 || entry.partner}{' '}<span class="sep" aria-hidden="true"
										>·</span
									>{' '}{/if}<span>{part}</span>{/each}
						</span>
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
		color: var(--muted);
	}

	.entries {
		margin: 0 0 1rem;
		padding: 0;
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

	.sep {
		color: var(--ghost);
	}

	.goal {
		display: block;
		margin-top: 0.15rem;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
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
