<script>
	import { onDestroy, onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { useT } from '$lib/i18n';
	import { fullName } from '$lib/players';
	import { emptyDraft, reconcile, swapBlock, swapPlayers } from '$lib/builder/plan.js';
	import { BuilderError, generate, placeNewcomers } from '$lib/builder/generate.js';
	import { newSeed } from '$lib/builder/random.js';
	import { requestRows, summarise } from '$lib/builder/requests.js';
	import { features, makeScorer } from '$lib/builder/score.js';
	import { swapPreview } from '$lib/builder/compare.js';
	import { emptyHistory, record, redo as redoStep, undo as undoStep } from '$lib/builder/history.js';
	import { createSaver } from '$lib/builder/saver.js';
	import StepProgress from '$lib/components/StepProgress.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import BuilderRequests from '$lib/components/builder/BuilderRequests.svelte';
	import BuilderTeams from '$lib/components/builder/BuilderTeams.svelte';
	import PlayerSheet from '$lib/components/builder/PlayerSheet.svelte';
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

	let history = emptyHistory();
	function load(saved) {
		saver?.flush(); // a pending edit of the draft being replaced is not lost, nor sent twice
		const out = reconcile(saved ? saved.document : emptyDraft(), players);
		draft = out.draft;
		history = emptyHistory(); // a snapshot of another draft or roster must never come back
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

	// `key` makes consecutive edits of one field a single undo step.
	function commit(next, key = null) {
		history = record(history, draft, key);
		show(next);
	}
	function show(next) {
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
	const linkKey = (l) => `${l.player}:${l.kind}:${l.target}`;
	// The clear matches confirmed in one click: one change of the draft, so one save.
	function confirmClear({ detail }) {
		const seen = new Set(draft.links.map(linkKey));
		const added = [];
		for (const link of detail) {
			if (seen.has(linkKey(link))) continue;
			seen.add(linkKey(link));
			added.push(link);
		}
		if (added.length > 0) commit({ ...draft, links: [...draft.links, ...added] });
	}
	// The matches depend on the roster only: a drag or a lock changes the draft, never them.
	$: rows = requestRows(players);
	$: requestSummary = summarise(rows, draft.links);
	function setPerTeam({ detail }) {
		if (draft.teams.length === 0 && Number.isInteger(detail) && detail >= 2 && detail <= 20) {
			tooFew = false;
			commit({ ...draft, players_per_team: detail }, 'perTeam');
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
	let preview = null; // { id, opener } while a player's sheet is open
	function openPreview({ detail }) {
		preview = detail;
	}
	$: previewed = preview ? byId.get(preview.id) ?? null : null;
	// A player who left the roster (a reloaded draft) closes the sheet.
	$: if (preview && !byId.has(preview.id)) preview = null;
	$: previewTeam = previewed ? draft.teams.findIndex((tm) => tm.players.includes(previewed.id)) : -1;
	$: saveBlocked = saveState === 'stale' || saveState === 'error';

	$: canUndo = history.past.length > 0 && !saveBlocked;
	$: canRedo = history.future.length > 0 && !saveBlocked;
	function undo() {
		const out = canUndo && undoStep(history, draft);
		if (!out) return;
		history = out.history;
		show(out.draft);
	}
	function redo() {
		const out = canRedo && redoStep(history, draft);
		if (!out) return;
		history = out.history;
		show(out.draft);
	}
	const typing = (el) => el instanceof HTMLElement && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
	// Cmd/Ctrl+Z and Shift+Z (or Ctrl+Y); left alone in a text field, which has its own, and behind the sheet.
	function onKeydown(event) {
		if (!(event.metaKey || event.ctrlKey) || event.altKey || typing(event.target) || preview) return;
		const key = event.key.toLowerCase();
		if (key === 'z' && !event.shiftKey) undo();
		else if ((key === 'z' && event.shiftKey) || (key === 'y' && event.ctrlKey)) redo();
		else return;
		event.preventDefault();
	}

	// The player compared with in the open sheet; it never outlives the sheet, a change of
	// previewed player, or its own place on the roster.
	let compareId = null;
	$: if (!preview || compareId === preview.id || (compareId !== null && !byId.has(compareId))) compareId = null;
	$: other = compareId !== null ? byId.get(compareId) ?? null : null;
	const teamOfId = (id) => draft.teams.findIndex((tm) => tm.players.includes(id));
	$: otherTeam = other ? teamOfId(other.id) : -1;
	$: swapReason = previewed && other ? (saveBlocked ? 'blocked' : swapBlock(draft, previewed.id, other.id)) : null;
	$: swapView = previewed && other && !swapReason ? swapPreview(draft, previewed.id, other.id, scorer) : null;
	$: candidates = previewed
		? players
				.filter((p) => p.id !== previewed.id)
				.map((p) => ({ id: p.id, name: fullName(p), teamIndex: teamOfId(p.id), rating: p.rating }))
				.sort((x, y) => x.name.localeCompare(y.name))
		: [];
	// One update of the draft, so one save: the sheet stays on the pair, and a second swap undoes it.
	function swap({ detail: { a, b } }) {
		if (saveBlocked) return;
		const next = swapPlayers(draft, a, b);
		if (next) commit(next);
	}
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

<svelte:window on:keydown={onKeydown} />

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('builder.title') }]} />
	<h1>{t('builder.title')}</h1>

	{#if done}
		<h2>{t('builder.step.3')}</h2>
		<BuilderApply {done} {year} teamCount={done.teams.length} placedCount={0} unplacedCount={0} registrationOpen={false} nameOf={() => ''} />
	{:else if builder.teams_exist}
		<p class="notice">{t('builder.exists')}</p>
	{:else if players.length === 0}
		<p class="notice">{t('builder.noPlayers')}</p>
	{:else}
		{#if banner.joined > 0}<p class="notice">{t('builder.banner', { joined: banner.joined, n: banner.joined })}</p>{/if}
		{#if banner.left > 0}<p class="notice">{t('builder.bannerLeft', { left: banner.left, n: banner.left })}</p>{/if}
		<!-- One slot for the save state, always there: the text switches in place, so the page below
		     never jumps when a change is saved. -->
		<div class="save-status">
			{#if saveState === 'stale'}
				<p class="error" role="alert">
					{t('builder.stale')}
					<button type="button" class="pill" on:click={loadTheirs}>{t('builder.stale.load')}</button>
				</p>
			{:else if saveState === 'error'}
				<p class="error" role="alert">{t('builder.save.error')}</p>
			{:else}
				<p class="hint" role="status">
					{saveState === 'saving' ? t('builder.save.saving') : saveState === 'saved' ? t('builder.save.saved') : ''}
				</p>
			{/if}
		</div>

		<StepProgress
			steps={STEPS.map((n) => ({ n, label: t(`builder.step.${n}`) }))}
			{step}
			label={t('builder.steps.label')}
			ofText={t('builder.step.of', { n: step, total: STEPS.length })}
			on:go={({ detail }) => (step = detail)}
		/>

		{#if step === 1}
			<h2>{t('builder.step.1')}</h2>
			<BuilderRequests {players} links={draft.links} {canUndo} {canRedo} on:undo={undo} on:redo={redo} on:toggle={toggleLink} on:confirmClear={confirmClear} />
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
				on:preview={openPreview}
				{showRequests}
				on:showRequests={setShowRequests}
				on:lock={toggleLock}
				{canUndo}
				{canRedo}
				on:undo={undo}
				on:redo={redo}
			/>
			<PlayerSheet
				open={previewed !== null}
				player={previewed}
				skills={builder.skills}
				teamIndex={previewTeam}
				{candidates}
				{other}
				otherTeamIndex={otherTeam}
				{swapReason}
				{swapView}
				on:compare={({ detail }) => (compareId = detail.id)}
				on:uncompare={() => (compareId = null)}
				on:swap={swap}
				opener={preview?.opener ?? null}
				on:close={() => (preview = null)}
			/>
		{:else}
			<h2>{t('builder.step.3')}</h2>
			<BuilderApply
				{year}
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

		<div aria-live="polite">
			{#if step === 1 && requestSummary.review > 0}
				<p class="notice">{t('builder.requests.warning', { n: requestSummary.review })}</p>
			{/if}
		</div>

		<div class="nav-buttons">
			{#if step > 1}
				<button type="button" class="pill" on:click={() => (step -= 1)}>{t('builder.step.previous')}</button>
			{/if}
			{#if step < STEPS.length}
				<button type="button" class="submit" on:click={() => (step += 1)}>{t('builder.step.next')}</button>
			{/if}
		</div>
	{/if}
</div>

<style>
	.page {
		/* The board wants room: use the width the screen has instead of the reading column. */
		--page: min(100% - 2rem, 110rem);
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
	.save-status {
		/* The height of the one-line states, so saving and saved never move what is below. */
		min-height: 2.25rem;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 1rem;
		margin-bottom: 1rem;
	}
	.save-status :global(.hint) {
		margin: 0;
	}
	.hint {
		margin: 0 0 1rem;
		color: var(--muted);
		font-size: 0.875rem;
		line-height: 1.25rem;
		min-height: 1.25rem;
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
	.submit {
		padding: 0.375rem 1rem;
		border-radius: 999px;
		border: 1px solid var(--accent);
		background: var(--accent);
		color: var(--bg);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.nav-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin-top: 1.25rem;
	}
</style>
