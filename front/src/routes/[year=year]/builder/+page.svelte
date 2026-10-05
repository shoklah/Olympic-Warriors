<script>
	import { onDestroy, onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { emptyDraft, reconcile } from '$lib/builder/plan.js';
	import { BuilderError, generate, placeNewcomers } from '$lib/builder/generate.js';
	import { newSeed } from '$lib/builder/random.js';
	import { features, makeScorer } from '$lib/builder/score.js';
	import { createSaver } from '$lib/builder/saver.js';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import BuilderRequests from '$lib/components/builder/BuilderRequests.svelte';
	import BuilderTeams from '$lib/components/builder/BuilderTeams.svelte';
	import BuilderApply from '$lib/components/builder/BuilderApply.svelte';

	export let data;
	const t = useT();

	$: builder = data.builder;
	$: players = builder.players;
	$: year = builder.edition.year;
	$: byId = new Map(players.map((p) => [p.id, p]));

	let step = 1;
	let draft = emptyDraft();
	let unplaced = [];
	let banner = { joined: 0, left: 0 };
	let saveState = 'idle';
	let stale = undefined; // undefined: not stale; null: stale and the draft was cleared; object: theirs
	let tooFew = false;
	let busy = false;
	let applyError = '';
	let done = null;
	let saver;
	let showRequests = true;

	const NOTES_KEY = 'builder.showRequests';
	onMount(() => {
		try {
			showRequests = localStorage.getItem(NOTES_KEY) !== 'off';
		} catch {
			// private mode or blocked storage: the default stands
		}
	});
	function setShowRequests({ detail }) {
		showRequests = detail;
		try {
			localStorage.setItem(NOTES_KEY, detail ? 'on' : 'off');
		} catch {
			// not remembered, still applied
		}
	}

	function load(saved) {
		saver?.flush(); // a pending edit of the draft being replaced is not lost, nor sent twice
		const out = reconcile(saved ? saved.document : emptyDraft(), players);
		draft = out.draft;
		unplaced = out.unplaced;
		banner = { joined: out.joined, left: out.left };
		stale = undefined;
		saveState = 'idle';
		// A replaced saver may still answer for its last request; only the current one speaks.
		const mine = createSaver({
			url: `/${year}/builder/draft`,
			based_on: saved ? saved.updated_at : null,
			onSaved: () => {
				if (saver === mine && !mine.pending()) saveState = 'saved';
			},
			onStale: (theirs) => {
				if (saver !== mine) return;
				stale = theirs;
				saveState = 'stale';
			},
			onError: () => {
				if (saver === mine) saveState = 'error';
			}
		});
		saver = mine;
		loadedRoster = players.map((p) => p.id).join();
	}

	// Loaded again only for a different payload (a new load), never because a bound child
	// input marked `data` dirty.
	// A payload carrying the draft this page already holds (our own save, seen again after an
	// invalidation) with the same roster changes nothing.
	let loadedFrom = null;
	let loadedRoster = '';
	$: if (builder !== loadedFrom) {
		const known = loadedFrom !== null && builder.draft && builder.draft.updated_at === saver?.version() && builder.players.map((p) => p.id).join() === loadedRoster;
		loadedFrom = builder;
		if (!known) load(builder.draft);
	}

	$: teamIds = draft.teams.map((tm) => tm.players);
	$: scorer = makeScorer(players, draft.links, builder.skills);
	$: result = teamIds.length > 0 ? scorer(teamIds) : null;
	$: incomplete = new Set(players.filter((p) => features(p, builder.skills).incomplete).map((p) => p.id));
	$: placedCount = players.length - unplaced.length;

	/** What the cards show of a player's requests: the texts no confirmed link explains stay as notes. */
	$: notesFor = (player) =>
		[player.team_with && `+ ${player.team_with}`, player.team_avoid && `− ${player.team_avoid}`].filter(Boolean);

	function commit(next) {
		draft = next;
		const placed = new Set(draft.teams.flatMap((tm) => tm.players));
		unplaced = players.map((p) => p.id).filter((id) => !placed.has(id));
		saveState = 'saving';
		saver.save(draft);
	}

	function toggleLink({ detail: { player, kind, target } }) {
		const same = (l) => l.player === player && l.kind === kind && l.target === target;
		const links = draft.links.some(same) ? draft.links.filter((l) => !same(l)) : [...draft.links, { player, kind, target }];
		commit({ ...draft, links });
	}
	function setPerTeam({ detail }) {
		if (draft.teams.length === 0 && Number.isInteger(detail) && detail >= 2 && detail <= 20) {
			tooFew = false;
			commit({ ...draft, players_per_team: detail });
		}
	}
	function run(seed, variety = false) {
		try {
			const { teams } = generate(players, draft.links, builder.skills, {
				perTeam: draft.players_per_team,
				seed,
				current: teamIds,
				locked: draft.locked,
				variety
			});
			tooFew = false;
			commit({ ...draft, seed, teams: teams.map((ids) => ({ players: ids })) });
		} catch (err) {
			if (err instanceof BuilderError) tooFew = true;
			else throw err;
		}
	}
	const propose = () => run(draft.seed);
	const reroll = () => run(newSeed(), true);
	function placeNew() {
		const teams = placeNewcomers(players, draft.links, builder.skills, teamIds, unplaced);
		commit({ ...draft, teams: teams.map((ids) => ({ players: ids })) });
	}
	function reset() {
		const n = draft.teams.length + draft.locked.length;
		if (!window.confirm(t('builder.resetConfirm', { n }))) return;
		commit({ ...draft, teams: [], locked: [] });
	}
	function move({ detail: { id, to } }) {
		const teams = draft.teams.map((tm) => ({ players: tm.players.filter((p) => p !== id) }));
		if (to !== null && teams[to]) teams[to].players.push(id);
		commit({ ...draft, teams, locked: draft.locked.filter((p) => p !== id) });
	}
	function toggleLock({ detail: { id } }) {
		const locked = draft.locked.includes(id) ? draft.locked.filter((p) => p !== id) : [...draft.locked, id];
		commit({ ...draft, locked });
	}
	$: saveBlocked = saveState === 'stale' || saveState === 'error';
	async function apply() {
		if (saveBlocked) return;
		busy = true;
		applyError = '';
		try {
			await saver.flush();
			if (saveBlocked) return;
			const response = await fetch(`/${year}/builder/apply`, {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ based_on: saver.version() })
			});
			const body = await response.json().catch(() => ({}));
			if (response.ok) {
				done = body;
				await invalidateAll(); // the layout's summary now has the teams
			} else {
				applyError = `builder.error.${['no_draft', 'teams_exist', 'incomplete', 'bad_size', 'stale_draft'].includes(body.error) ? body.error : 'failed'}`;
				if (body.error === 'stale_draft') {
					stale = body.draft ?? null;
					saveState = 'stale';
				}
			}
		} catch {
			applyError = 'builder.error.failed';
		} finally {
			busy = false;
		}
	}
	async function loadTheirs() {
		if (stale) return load(stale);
		// No draft came with the refusal: read the server's data again, then its draft.
		await invalidateAll();
		if (builder === loadedFrom) load(builder.draft);
	}

	onDestroy(() => saver?.flush());
	const nameOf = (id) => (byId.has(id) ? fullName(byId.get(id)) : '');
	const STEPS = [1, 2, 3];
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('builder.title') }]} />
	<h1>{t('builder.title')}</h1>

	{#if done}
		<h2>{t('builder.step.3')}</h2>
		<BuilderApply {done} teamCount={done.teams.length} placedCount={0} unplacedCount={0} registrationOpen={false} nameOf={() => ''} />
	{:else if builder.teams_exist}
		<p class="notice">{t('builder.exists')}</p>
	{:else if players.length === 0}
		<p class="notice">{t('builder.noPlayers')}</p>
	{:else}
		{#if banner.joined > 0}<p class="notice">{t('builder.banner', { joined: banner.joined, n: banner.joined })}</p>{/if}
		{#if banner.left > 0}<p class="notice">{t('builder.bannerLeft', { left: banner.left, n: banner.left })}</p>{/if}
		{#if saveState === 'stale'}
			<p class="error" role="alert">
				{t('builder.stale')}
				<button type="button" class="pill" on:click={loadTheirs}>{t('builder.stale.load')}</button>
			</p>
		{:else if saveState === 'error'}
			<p class="error" role="alert">{t('builder.save.error')}</p>
		{:else if saveState === 'saved'}
			<p class="hint" role="status">{t('builder.save.saved')}</p>
		{/if}

		<nav class="progress" aria-label={t('builder.steps.label')}>
			<ol>
				{#each STEPS as n}
					<li>
						<button type="button" class="step-name" aria-current={n === step ? 'step' : undefined} on:click={() => (step = n)}>
							<span class="num" aria-hidden="true">{n}</span>
							{t(`builder.step.${n}`)}
						</button>
					</li>
				{/each}
			</ol>
		</nav>

		{#if step === 1}
			<h2>{t('builder.step.1')}</h2>
			<BuilderRequests {players} links={draft.links} on:toggle={toggleLink} />
		{:else if step === 2}
			<h2>{t('builder.step.2')}</h2>
			<BuilderTeams
				{players}
				teams={draft.teams}
				{unplaced}
				{result}
				skills={builder.skills}
				perTeam={draft.players_per_team}
				locked={draft.locked}
				{incomplete}
				{notesFor}
				{tooFew}
				on:perTeam={setPerTeam}
				on:propose={propose}
				on:reroll={reroll}
				on:placeNew={placeNew}
				on:reset={reset}
				on:move={move}
				{showRequests}
				on:showRequests={setShowRequests}
				on:lock={toggleLock}
			/>
		{:else}
			<h2>{t('builder.step.3')}</h2>
			<BuilderApply
				teamCount={draft.teams.length}
				{placedCount}
				unplacedCount={unplaced.length}
				registrationOpen={builder.registration_open}
				unmet={result?.unmet ?? []}
				{nameOf}
				{busy}
				error={applyError}
				{done}
				{saveBlocked}
				on:apply={apply}
			/>
		{/if}
	{/if}
</div>

<style>
	.page {
		padding-bottom: 3rem;
	}
	h1 {
		margin: 0.2rem 0 1rem;
		overflow-wrap: anywhere;
	}
	h2 {
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
		margin: 0 0 0.75rem;
	}
	.notice {
		margin: 0 0 1rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		background: var(--bg-raised);
	}
	.error {
		margin: 0 0 1rem;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
		color: var(--loss);
		border: 1px solid var(--loss);
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
	}
	.hint {
		margin: 0 0 1rem;
		color: var(--muted);
		font-size: 0.875rem;
	}
	.pill {
		padding: 0.375rem 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.progress {
		margin: 0 0 1.25rem;
	}
	.progress ol {
		display: flex;
		gap: 0.5rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.progress li {
		flex: 1;
		display: flex;
	}
	.step-name {
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.125rem;
		text-align: center;
		padding: 0.5rem;
		background: transparent;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--muted);
		font: inherit;
		cursor: pointer;
	}
	@media (min-width: 600px) {
		.step-name {
			flex-direction: row;
			gap: 0.5rem;
		}
	}
	.step-name[aria-current='step'] {
		color: var(--ink);
		border-color: var(--accent);
	}
</style>
