<script>
	import { createEventDispatcher } from 'svelte';
	import { useT } from '$lib/i18n';
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

	const t = useT();
	const dispatch = createEventDispatcher();
	$: byId = new Map(players.map((p) => [p.id, p]));
	$: proposed = teams.length > 0;
	$: count = proposed ? teams.length : Math.ceil(players.length / perTeam);
	$: unmet = result?.unmet ?? [];
	$: skillName = (s) => s.name_fr;

	function drop(event, to) {
		event.preventDefault();
		const id = Number(event.dataTransfer?.getData('text/plain'));
		if (byId.has(id)) dispatch('move', { id, to });
	}
	const nameOf = (id) => (byId.has(id) ? fullName(byId.get(id)) : '');
</script>

<div class="controls">
	<div class="field">
		<label for="per-team">{t('builder.perTeam')}</label>
		<input
			id="per-team"
			type="number"
			min="2"
			max="20"
			step="1"
			value={perTeam}
			disabled={proposed}
			aria-describedby={proposed ? 'per-team-hint' : undefined}
			on:change={(event) => dispatch('perTeam', Number(event.currentTarget.value))}
		/>
		{#if proposed}<p class="hint" id="per-team-hint">{t('builder.perTeamLocked')}</p>{/if}
	</div>
	<p class="count num">{t('builder.counts', { n: count })}</p>
	<label class="check">
		<input type="checkbox" checked={showRequests} on:change={(e) => dispatch('showRequests', e.currentTarget.checked)} />
		{t('builder.showRequests')}
	</label>
	<div class="buttons">
		{#if !proposed}
			<button type="button" class="submit" disabled={players.length === 0} on:click={() => dispatch('propose')}>{t('builder.propose')}</button>
		{:else}
			<button type="button" class="submit" on:click={() => dispatch('reroll')}>{t('builder.reroll')}</button>
			{#if unplaced.length > 0}
				<button type="button" class="pill" on:click={() => dispatch('placeNew')}>{t('builder.placeNew')}</button>
			{/if}
			<button type="button" class="pill" on:click={() => dispatch('reset')}>{t('builder.reset')}</button>
		{/if}
	</div>
</div>
{#if tooFew}<p class="error" role="alert">{t('builder.tooFew')}</p>{/if}

{#if proposed}
	<section class="unmet" aria-labelledby="unmet-title">
		<h3 id="unmet-title">{t('builder.unmet')}</h3>
		{#if unmet.length === 0}
			<p class="hint">{t('builder.unmetNone')}</p>
		{:else}
			<ul>
				{#each unmet as u}
					<li>
						{t(`builder.unmet.${u.kind}`, { player: nameOf(u.player), target: nameOf(u.target) })}{u.mutual ? t('builder.unmet.mutual') : ''}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<div class="board">
	{#if unplaced.length > 0}
		<section class="column tray" aria-label={t('builder.tray')} on:dragover|preventDefault on:drop={(e) => drop(e, null)}>
			<h3>{t('builder.tray')}</h3>
			<ul>
				{#each unplaced as id (id)}
					<PlayerCard player={byId.get(id)} teamCount={teams.length || count} incomplete={incomplete.has(id)} notes={showRequests ? notesFor(byId.get(id)) : []} on:move />
				{/each}
			</ul>
		</section>
	{/if}
	{#each teams as team, i}
		<section class="column" aria-label={t('builder.team', { n: i + 1 })} on:dragover|preventDefault on:drop={(e) => drop(e, i)}>
			<h3>{t('builder.team', { n: i + 1 })}</h3>
			<p class="stats">
				<span>{t('builder.size', { n: team.players.length })}</span>
				{#if result?.teams[i]}<span class="num">{t('builder.average', { rating: result.teams[i].rating.toFixed(1) })}</span>{/if}
			</p>
			{#if result?.teams[i]}
				<ul class="bars" aria-hidden="true">
					{#each skills as s}
						<li title="{skillName(s)} {result.teams[i].skills[s.identifier].toFixed(1)}">
							<span class="fill" style="width: {result.teams[i].skills[s.identifier] * 10}%"></span>
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
					/>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.5rem;
		align-items: end;
		margin-bottom: 1rem;
	}
	.field {
		display: grid;
		gap: 0.25rem;
	}
	.field label {
		font-weight: 600;
	}
	input[type='number'] {
		width: 6rem;
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
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.submit,
	.pill {
		padding: 0.625rem 1.25rem;
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
	.hint {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0;
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
	.board {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
		gap: 1rem;
		align-items: start;
	}
	.column {
		display: grid;
		gap: 0.5rem;
		padding: 0.75rem;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		border-radius: var(--radius);
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
		height: 0.375rem;
		list-style: none;
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
</style>
