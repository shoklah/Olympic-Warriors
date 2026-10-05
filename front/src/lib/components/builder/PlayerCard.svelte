<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';

	export let player;
	export let teamCount;
	export let index = -1;
	export let locked = false;
	export let incomplete = false;
	export let notes = [];

	const t = useT();
	const dispatch = createEventDispatcher();
	$: name = fullName(player);
	$: targets = Array.from({ length: teamCount }, (_, i) => i).filter((i) => i !== index);

	function dragStart(event) {
		event.dataTransfer?.setData('text/plain', String(player.id));
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
	}
	function change(event) {
		const value = event.currentTarget.value;
		event.currentTarget.value = '';
		if (value === '') return;
		dispatch('move', { id: player.id, to: value === 'tray' ? null : Number(value) });
	}
</script>

<li class="card" class:locked draggable="true" on:dragstart={dragStart}>
	<span class="top">
		<span class="name">{name}</span>
		<span class="rating num">{player.rating}</span>
	</span>
	{#if incomplete}<span class="badge">{t('builder.incomplete')}</span>{/if}
	{#each notes as note}<span class="note">{note}</span>{/each}
	<span class="actions">
		{#if targets.length > 0 || index !== -1}
		<select aria-label={t('builder.move', { name })} on:change={change}>
			<option value="">{t('builder.moveTo')}</option>
			{#each targets as i}<option value={i}>{t('builder.team', { n: i + 1 })}</option>{/each}
			{#if index !== -1}<option value="tray">{t('builder.moveToTray')}</option>{/if}
		</select>
		{/if}
		{#if index !== -1}
			<button
				type="button"
				class="icon-button"
				aria-pressed={locked}
				aria-label={t(locked ? 'builder.unlock' : 'builder.lock', { name })}
				on:click={() => dispatch('lock', { id: player.id })}
			>
				<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z" /></svg>
			</button>
		{/if}
	</span>
</li>

<style>
	.card {
		display: grid;
		gap: 0.375rem;
		padding: 0.625rem 0.75rem;
		list-style: none;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		cursor: grab;
	}
	.card.locked {
		border-color: var(--accent);
	}
	.top {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.name {
		font-weight: 600;
		color: var(--ink);
	}
	.rating {
		color: var(--muted);
	}
	.badge,
	.note {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.badge {
		color: var(--loss);
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	select {
		flex: 1;
		min-width: 0;
		padding: 0.375rem 0.5rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	.icon-button {
		display: inline-grid;
		place-items: center;
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		border-radius: 999px;
		border: 1px solid var(--line-strong);
		background: transparent;
		color: var(--muted);
		cursor: pointer;
	}
	.icon-button[aria-pressed='true'] {
		color: var(--accent);
		border-color: var(--accent);
	}
	.icon-button svg {
		width: 1.125rem;
		height: 1.125rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
