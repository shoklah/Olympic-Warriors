<script>
	import { createEventDispatcher, onDestroy, tick } from 'svelte';
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

	/** Every element the sheet lets Tab reach, in DOM order (links then the close button). */
	function focusables() {
		if (!sheetEl) return [];
		return [
			...sheetEl.querySelectorAll(
				'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
			)
		];
	}

	/** Escape closes; Tab/Shift+Tab wraps inside the sheet, since aria-modal alone doesn't
	    stop the browser sending focus to the page behind it (no jsdom support for native
	    <dialog>.showModal(), see the badge collection review). */
	const onKey = (event) => {
		if (!open) return;
		if (event.key === 'Escape') {
			close();
			return;
		}
		if (event.key !== 'Tab') return;
		const items = focusables();
		if (items.length === 0) {
			event.preventDefault();
			return;
		}
		const first = items[0];
		const last = items[items.length - 1];
		const active = document.activeElement;
		if (event.shiftKey) {
			if (active === first || active === sheetEl) {
				event.preventDefault();
				last.focus();
			}
		} else if (active === last) {
			event.preventDefault();
			first.focus();
		}
	};

	// The background page must not scroll behind an open sheet. previousOverflow stays null
	// while unlocked, so a stray call (e.g. the initial `open: false`) is a no-op.
	let previousOverflow = null;
	function lockScroll() {
		if (typeof document === 'undefined' || previousOverflow !== null) return;
		previousOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
	}
	function unlockScroll() {
		if (typeof document === 'undefined' || previousOverflow === null) return;
		document.body.style.overflow = previousOverflow;
		previousOverflow = null;
	}
	$: if (open) lockScroll();
	else unlockScroll();
	onDestroy(unlockScroll);

	$: tiered = slot ? isTiered(slot.code) : false;
	$: titleId = slot ? `badge-sheet-title-${slot.code}` : null;
	/** The first tier's threshold for a locked tiered slot (slot.medal.tier is 0). */
	$: firstGoal = slot && tiered && !slot.earned ? nextThreshold(slot.code, 0) : null;

	/**
	 * badgeDetail's parts, minus the "×N" chip: the status line above already says the
	 * slot's count, so repeating it on every entry line would say it twice.
	 */
	function entryParts(entry) {
		return badgeDetail(entry, t, locale).filter((part) => !/^×\d+$/.test(part));
	}
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
					{@const parts = entryParts(entry)}
					{@const next = tiered ? nextThreshold(entry.code, badgeTier(entry)) : null}
					<li class="entry">
						{#if entry.partner || parts.length}
							<span class="detail" data-testid="badge-sheet-detail">
								{#if entry.partner}
									{t('badge.with')}
									<a href="/players/{entry.partner.id}">{fullName(entry.partner)}</a>
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
