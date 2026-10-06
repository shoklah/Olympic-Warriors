<script>
	import { createEventDispatcher } from 'svelte';
	import { useLocale, useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import PlayerCard from './PlayerCard.svelte';

	export let players;
	export let teams;
	export let unplaced;
	export let result;
	export let skills;
	export let perTeam;
	export let locked;
	export let incomplete;
	export let notesFor;
	export let tooFew = false;
	export let showRequests = true;
	export let canUndo = false;
	export let canRedo = false;

	const t = useT();
	const locale = useLocale();
	const dispatch = createEventDispatcher();
	$: byId = new Map(players.map((p) => [p.id, p]));
	$: proposed = teams.length > 0;
	$: count = proposed ? teams.length : Math.ceil(players.length / perTeam);
	$: unmet = result?.unmet ?? [];
	let unmetOpen = false;
	$: if (unmet.length === 0) unmetOpen = false;
	const skillName = (s) => (locale === 'en' ? s.name_en : s.name_fr);

	// The column a card is being dragged over: 'tray' or the team's index.
	let over = null;
	function dragOver(event, key) {
		event.preventDefault();
		over = key;
	}
	function dragLeave(event) {
		if (!event.currentTarget.contains(event.relatedTarget)) over = null;
	}
	function drop(event, to) {
		event.preventDefault();
		over = null;
		const id = Number(event.dataTransfer?.getData('text/plain'));
		if (byId.has(id)) dispatch('move', { id, to });
	}
	function setPerTeam(event) {
		const value = Number(event.currentTarget.value);
		if (Number.isInteger(value) && value >= 2 && value <= 20) dispatch('perTeam', value);
		else event.currentTarget.value = perTeam; // the field shows what the page holds
	}
	const nameOf = (id) => (byId.has(id) ? fullName(byId.get(id)) : '');
</script>

<div class="toolbar">
	<div class="field">
		<label for="per-team">{t('builder.perTeam')}</label>
		<div class="size">
			<input
				id="per-team"
				type="number"
				min="2"
				max="20"
				step="1"
				value={perTeam}
				disabled={proposed}
				title={proposed ? t('builder.perTeamLocked') : undefined}
				aria-describedby={proposed ? 'per-team-hint' : undefined}
				on:change={setPerTeam}
			/>
			<span class="count num">{t('builder.counts', { n: count })}</span>
		</div>
		{#if proposed}<p class="visually-hidden" id="per-team-hint">{t('builder.perTeamLocked')}</p>{/if}
	</div>
	<span class="sep" aria-hidden="true"></span>
	<div class="actions">
		<button type="button" class="icon" disabled={!canUndo} aria-label={t('builder.undo')} title={t('builder.undo.hint')} on:click={() => dispatch('undo')}>
			<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></svg>
		</button>
		<button type="button" class="icon" disabled={!canRedo} aria-label={t('builder.redo')} title={t('builder.redo.hint')} on:click={() => dispatch('redo')}>
			<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 14 5-5-5-5" /><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13" /></svg>
		</button>
		{#if !proposed}
			<button type="button" class="submit" disabled={players.length === 0} on:click={() => dispatch('propose')}>{t('builder.propose')}</button>
		{:else}
			<button type="button" class="submit" on:click={() => dispatch('reroll')}>{t('builder.reroll')}</button>
			{#if unplaced.length > 0}
				<button type="button" class="pill" on:click={() => dispatch('placeNew')}>{t('builder.placeNew')}</button>
			{/if}
			<button type="button" class="danger" on:click={() => dispatch('reset')}>{t('builder.reset')}</button>
		{/if}
	</div>
	<span class="sep" aria-hidden="true"></span>
	<label class="switch">
		<input type="checkbox" checked={showRequests} on:change={(e) => dispatch('showRequests', e.currentTarget.checked)} />
		<span class="knob" aria-hidden="true"></span>
		{t('builder.showRequests')}
	</label>
</div>
{#if tooFew}<p class="error" role="alert">{t('builder.tooFew')}</p>{/if}

{#if proposed}
	<section class="status" class:met={unmet.length === 0} aria-labelledby="unmet-title">
		<h3 id="unmet-title" class="visually-hidden">{t('builder.unmet')}</h3>
		{#if unmet.length === 0}
			<p class="chip good">
				<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 5 5L20 7" /></svg>
				{t('builder.unmetNone')}
			</p>
		{:else}
			<button type="button" class="head" aria-expanded={unmetOpen} aria-controls="unmet-list" on:click={() => (unmetOpen = !unmetOpen)}>
				<span class="chip warn">
					<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg>
					{t('builder.unmetCount', { n: unmet.length })}
				</span>
				<span class="toggle">{unmetOpen ? t('builder.unmetHide') : t('builder.unmetShow')}
					<svg class="chev" class:open={unmetOpen} viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
				</span>
			</button>
			<ul id="unmet-list" hidden={!unmetOpen}>
				{#each unmet as u}
					<li>
						{t(`builder.unmet.${u.kind}`, { player: nameOf(u.player), target: nameOf(u.target) })}{u.mutual ? t('builder.unmet.mutual') : ''}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

{#if unplaced.length > 0}
	<div class="trayrow">
		<section
			class="column tray"
			class:over={over === 'tray'}
			aria-label={t('builder.tray')}
			on:dragover={(e) => dragOver(e, 'tray')}
			on:dragleave={dragLeave}
			on:drop={(e) => drop(e, null)}
		>
			<h3>{t('builder.tray')}</h3>
			<ul>
				{#each unplaced as id (id)}
					<PlayerCard player={byId.get(id)} teamCount={teams.length} incomplete={incomplete.has(id)} notes={showRequests ? notesFor(byId.get(id)) : []} on:move on:preview />
				{/each}
			</ul>
		</section>
	</div>
{/if}
<div class="board">
	{#each teams as team, i}
		<section
			class="column"
			class:over={over === i}
			aria-label={t('builder.team', { n: i + 1 })}
			on:dragover={(e) => dragOver(e, i)}
			on:dragleave={dragLeave}
			on:drop={(e) => drop(e, i)}
		>
			<h3>{t('builder.team', { n: i + 1 })}</h3>
			<p class="stats">
				<span>{t('builder.size', { n: team.players.length })}</span>
				{#if result?.teams[i]}<span class="num">{t('builder.average', { rating: result.teams[i].rating.toFixed(1) })}</span>{/if}
			</p>
			{#if result?.teams[i]}
				<ul class="bars" aria-hidden="true">
					{#each skills as s}
						<li title="{skillName(s)} {result.teams[i].skills[s.identifier].toFixed(1)}">
							<span class="tag">{s.identifier}</span>
							<span class="track"><span class="fill" style="width: {result.teams[i].skills[s.identifier] * 10}%"></span></span>
						</li>
					{/each}
				</ul>
			{/if}
			<ul>
				{#each team.players as id (id)}
					<PlayerCard
						player={byId.get(id)}
						teamCount={teams.length}
						index={i}
						locked={locked.includes(id)}
						incomplete={incomplete.has(id)}
						notes={showRequests ? notesFor(byId.get(id)) : []}
						on:move
						on:lock
						on:preview
					/>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.25rem;
		margin-bottom: 0.5rem;
		padding: 0.75rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.sep {
		align-self: stretch;
		width: 1px;
		background: var(--line);
	}
	.field {
		display: grid;
		gap: 0.25rem;
	}
	.field label {
		font-weight: 600;
	}
	.size {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	input[type='number'] {
		width: 5rem;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	input:disabled {
		opacity: 0.5;
	}
	.count {
		margin: 0;
		color: var(--muted);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		cursor: pointer;
	}
	.icon:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.icon:focus-visible,
	.danger:focus-visible,
	.head:focus-visible,
	.switch:focus-within {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.submit,
	.pill {
		padding: 0.5rem 1.125rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.submit {
		background: var(--accent);
		color: var(--bg);
	}
	.submit:disabled,
	.pill:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	/* The risky one reads as such: no fill, the loss colour. */
	.danger {
		padding: 0.5rem 0.5rem;
		border: 0;
		background: none;
		color: var(--loss);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		border-radius: var(--radius);
	}
	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		border-radius: var(--radius);
	}
	.switch input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}
	.knob {
		position: relative;
		flex: none;
		width: 2rem;
		height: 1.125rem;
		border-radius: 999px;
		background: var(--line-strong);
		transition: background 0.15s;
	}
	.knob::after {
		content: '';
		position: absolute;
		top: 0.125rem;
		left: 0.125rem;
		width: 0.875rem;
		height: 0.875rem;
		border-radius: 50%;
		background: var(--bg);
		transition: transform 0.15s;
	}
	.switch input:checked + .knob {
		background: var(--accent);
	}
	.switch input:checked + .knob::after {
		transform: translateX(0.875rem);
	}
	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	.status {
		margin: 0 0 1rem;
		padding: 0.5rem 1rem;
		background: var(--bg-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.head {
		display: flex;
		width: 100%;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.25rem 0;
		background: none;
		border: 0;
		color: var(--muted);
		font: inherit;
		cursor: pointer;
		border-radius: var(--radius);
	}
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.875rem;
	}
	.chev {
		transition: transform 0.15s;
	}
	.chev.open {
		transform: rotate(180deg);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
	}
	.chip.good {
		color: var(--win);
	}
	.chip.warn {
		color: var(--todo);
	}
	.status ul {
		margin: 0.5rem 0 0.25rem;
		padding-left: 1.25rem;
		display: grid;
		gap: 0.25rem;
		font-size: 0.875rem;
	}
	.status ul[hidden] {
		display: none;
	}
	.error {
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
		color: var(--loss);
		border: 1px solid var(--loss);
	}
	.unmet {
		margin: 1rem 0;
	}
	.unmet h3 {
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
		margin: 0 0 0.5rem;
	}
	.unmet ul {
		margin: 0;
		padding-left: 1.25rem;
	}
	.trayrow {
		margin-bottom: 1rem;
	}
	.tray ul {
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		align-items: start;
	}
	.board {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: 1rem;
		align-items: stretch;
	}
	.column {
		display: grid;
		/* A stretched card keeps its rows where they are: the spare height ends up at the bottom,
		   so every card's title, stats and bars line up with its neighbours'. */
		align-content: start;
		gap: 0.5rem;
		padding: 0.75rem;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.column.over {
		border-color: var(--accent);
		background: var(--bg-raised);
	}
	.column h3 {
		margin: 0;
		font-size: 1.125rem;
	}
	.column ul {
		display: grid;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
	}
	.tray {
		border-style: dashed;
		border-color: var(--accent);
	}
	.stats {
		display: flex;
		justify-content: space-between;
		margin: 0;
		color: var(--muted);
		font-size: 0.875rem;
	}
	.column ul.bars {
		display: grid;
		gap: 0.25rem;
	}
	.bars li {
		display: grid;
		grid-template-columns: 2.75rem 1fr;
		gap: 0.5rem;
		align-items: center;
		list-style: none;
	}
	.tag {
		font-size: 0.6875rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track {
		display: block;
		height: 0.375rem;
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
	/* Side by side, every card the same size (the tallest row sets the height); one column on a
	   phone keeps each card as tall as its content. */
	@media (min-width: 600px) {
		.board {
			grid-auto-rows: 1fr;
		}
	}
</style>
