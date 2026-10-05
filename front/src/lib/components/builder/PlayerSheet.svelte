<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { useLocale, useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { modal } from '$lib/modal';
	import { playerProfile } from '$lib/builder/profile.js';

	export let open = false;
	export let player = null;
	export let skills;
	/** The team's index, -1 for a player still in the tray. */
	export let teamIndex = -1;
	/** What had focus before the sheet opened: it gets it back on close. */
	export let opener = null;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();

	let sheetEl = null;
	$: if (open && sheetEl) tick().then(() => sheetEl?.focus());

	function close() {
		dispatch('close');
		opener?.focus();
	}

	$: profile = player ? playerProfile(player, skills, locale) : null;
	$: name = player ? fullName(player) : '';
	const shown = (value) => Math.round(value * 10) / 10;
</script>

{#if open && player}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-labelledby="player-sheet-title"
		tabindex="-1"
		bind:this={sheetEl}
		use:modal={{ onClose: close }}
	>
		<h2 id="player-sheet-title">{name}</h2>
		<p class="where">{teamIndex >= 0 ? t('builder.team', { n: teamIndex + 1 }) : t('builder.preview.tray')}</p>

		<dl class="summary">
			<div>
				<dt>{t('builder.preview.rating')}</dt>
				<dd class="num">{profile.rating}</dd>
			</div>
			{#if profile.globalLevel !== null}
				<div>
					<dt>{t('builder.preview.globalLevel')}</dt>
					<dd class="num">{profile.globalLevel}</dd>
				</div>
			{/if}
			<div>
				<dt>{t('builder.preview.frequency')}</dt>
				<dd>{profile.frequency ? t(`register.frequency.${profile.frequency}`) : '—'}</dd>
			</div>
		</dl>

		<h3>{t('builder.preview.skills')}</h3>
		<ul class="bars">
			{#each profile.bars as bar (bar.identifier)}
				<li class:estimated={bar.estimated}>
					<span class="skill">{bar.name}</span>
					<span class="track" aria-hidden="true"><span class="fill" style="width: {bar.value * 10}%"></span></span>
					<span class="value num">{shown(bar.value)}</span>
					{#if bar.estimated}<span class="note">{t('builder.preview.estimated')}</span>{/if}
				</li>
			{/each}
		</ul>
		{#if profile.incomplete}<p class="incomplete">{t('builder.incomplete')}</p>{/if}

		<h3>{t('builder.preview.sports')}</h3>
		{#if profile.sports.length === 0}
			<p class="none">{t('builder.preview.noSports')}</p>
		{:else}
			<ul class="sports">
				{#each profile.sports as s}
					<li>{s.sport} · {t(`register.level.${s.level}`)}</li>
				{/each}
			</ul>
		{/if}

		<div class="actions">
			<button type="button" on:click={close}>{t('builder.preview.close')}</button>
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
	h2 {
		margin: 0;
		text-align: center;
	}
	h3 {
		margin: 1rem 0 0.5rem;
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
	}
	.where {
		margin: 0.2rem 0 1rem;
		text-align: center;
		color: var(--muted);
	}
	.summary {
		display: grid;
		gap: 0.5rem;
		margin: 0;
	}
	.summary div {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}
	dt {
		color: var(--muted);
	}
	dd {
		margin: 0;
		text-align: right;
		color: var(--ink);
	}
	.bars,
	.sports {
		display: grid;
		gap: 0.375rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	/* The name on its own line, whole (skill names run long), then the bar and its value. */
	.bars li {
		display: grid;
		grid-template-columns: 1fr 2rem;
		gap: 0.125rem 0.5rem;
		align-items: center;
	}
	.skill {
		grid-column: 1 / -1;
	}
	.track {
		display: block;
		height: 0.5rem;
		background: var(--bg);
		border: 1px solid var(--line);
		border-radius: 999px;
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.estimated .fill {
		opacity: 0.35;
	}
	.value {
		text-align: right;
	}
	.note {
		grid-column: 1 / -1;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.incomplete {
		margin: 0.5rem 0 0;
		font-size: 0.8125rem;
		color: var(--loss);
	}
	.none {
		margin: 0;
		color: var(--muted);
	}
	.actions {
		display: flex;
		justify-content: center;
		margin-top: 1rem;
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
