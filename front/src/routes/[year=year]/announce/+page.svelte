<script>
	import { afterUpdate, onMount } from 'svelte';
	import { t as translate, useT } from '$lib/i18n';
	import { formatDateRange } from '$lib/edition';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import logo from '$lib/img/logo.svg';
	import title from '$lib/img/title.svg';
	import { cardLayout, posterLayout } from '$lib/announce/layout.js';
	import { drawLayout } from '$lib/announce/draw.js';
	import { fontsReady, loadImages } from '$lib/announce/images.js';
	import { cardFileName, download, downloadZip, posterFileName, toPng } from '$lib/announce/export.js';

	export let data;

	const t = useT();
	const PHOTOS_KEY = 'announce.photos';
	const LANG_KEY = 'announce.lang';

	$: edition = data.summary.edition;
	$: year = edition.year;
	$: teams = [...data.summary.teams].sort((a, b) => a.id - b.id);
	$: photoUrls = teams.flatMap((team) => team.players.map((p) => p.photo)).filter(Boolean);

	// Photos start off (players agreed to the site only) and the images start in French, whatever
	// the site's language: what an organiser chose is remembered, nothing else is.
	let photos = false;
	let lang = 'fr';
	let ready = false;
	let images = new Map();
	let failed = false;
	let posterCanvas;
	let cardCanvases = [];

	onMount(async () => {
		try {
			photos = localStorage.getItem(PHOTOS_KEY) === 'on';
			const saved = localStorage.getItem(LANG_KEY);
			if (saved === 'fr' || saved === 'en') lang = saved;
		} catch {
			// storage blocked: the defaults stand
		}
		await fontsReady();
		images = await loadImages([logo, title, ...photoUrls]);
		// `loadImages` keys the brand images by url; the painter looks them up by role.
		images.set('logo', images.get(logo));
		images.set('title', images.get(title));
		ready = true;
	});

	const measurer = () => {
		const ctx = document.createElement('canvas').getContext('2d');
		return (text, font) => {
			ctx.font = font;
			return ctx.measureText(text).width;
		};
	};

	function paint(canvas, layout) {
		if (!canvas) return;
		canvas.width = layout.width;
		canvas.height = layout.height;
		drawLayout(canvas.getContext('2d'), layout, { images });
	}

	// The text of the images, in the language chosen on the page (not the site's).
	$: labels = {
		title: translate(lang, 'announce.draw.title', { year }),
		subtitle: [edition.host, formatDateRange(edition.start_date, edition.end_date, lang)].filter(Boolean).join(' · '),
		event: translate(lang, 'announce.draw.event', { year })
	};
	// What the canvases should show: a new object whenever the teams, the switch, the language or
	// the images change, so `afterUpdate` repaints exactly then (and not on a failed-flag flip).
	$: wanted = ready && teams.length > 0 ? { teams, photos, labels, images } : null;
	let drawn = null;
	// After the DOM update, so the canvases of a changed team list are bound.
	afterUpdate(() => {
		if (!wanted || wanted === drawn) return;
		drawn = wanted;
		const measure = measurer();
		const { teams: list, photos: withPhotos, labels: text } = wanted;
		paint(posterCanvas, posterLayout(list, { photos: withPhotos, measure, labels: text }));
		list.forEach((team, i) => paint(cardCanvases[i], cardLayout(team, { photos: withPhotos, measure, labels: text })));
	});

	function setPhotos(event) {
		photos = event.currentTarget.checked;
		try {
			localStorage.setItem(PHOTOS_KEY, photos ? 'on' : 'off');
		} catch {
			// not remembered, still applied
		}
	}
	function setLang(event) {
		lang = event.currentTarget.value;
		try {
			localStorage.setItem(LANG_KEY, lang);
		} catch {
			// not remembered, still applied
		}
	}

	async function attempt(action) {
		failed = false;
		try {
			await action();
		} catch {
			failed = true;
		}
	}
	const downloadPoster = () => attempt(async () => download(await toPng(posterCanvas), posterFileName(year)));
	const downloadCard = (i) => attempt(async () => download(await toPng(cardCanvases[i]), cardFileName(i + 1, teams[i].name)));
	const downloadAll = () =>
		attempt(async () => {
			const entries = [{ name: posterFileName(year), blob: await toPng(posterCanvas) }];
			for (let i = 0; i < teams.length; i++) entries.push({ name: cardFileName(i + 1, teams[i].name), blob: await toPng(cardCanvases[i]) });
			await downloadZip(entries, `equipes-${year}.zip`);
		});
</script>

<div class="page">
	<Breadcrumb items={[{ label: String(year), href: `/${year}` }, { label: t('announce.title') }]} />
	<h1>{t('announce.title')}</h1>

	{#if teams.length === 0}
		<p class="notice">{t('announce.empty')}</p>
		<a class="pill-link" href="/{year}/builder">{t('builder.link')}</a>
	{:else}
		<div class="controls">
			<label class="check" for="announce-photos">
				<input id="announce-photos" type="checkbox" checked={photos} on:change={setPhotos} />
				{t('announce.photos')}
			</label>
			<label class="check">
				{t('announce.lang')}
				<select value={lang} on:change={setLang}>
					<option value="fr">Français</option>
					<option value="en">English</option>
				</select>
			</label>
			<button type="button" class="submit" disabled={!ready} on:click={downloadAll}>{t('announce.all')}</button>
		</div>
		{#if photos}<p class="hint" role="note">{t('announce.photos.notice')}</p>{/if}
		{#if failed}<p class="error" role="alert">{t('announce.failed')}</p>{/if}
		{#if !ready}<p class="hint" role="status">{t('announce.loading')}</p>{/if}

		<section aria-labelledby="poster-title">
			<h2 id="poster-title">{t('announce.poster.heading')}</h2>
			<!-- svelte-ignore a11y-no-interactive-element-to-noninteractive-role -->
			<canvas class="preview" bind:this={posterCanvas} role="img" aria-label={t('announce.poster.alt')}></canvas>
			<button type="button" class="pill" disabled={!ready} on:click={downloadPoster}>{t('announce.poster.download')}</button>
		</section>

		<section aria-labelledby="cards-title">
			<h2 id="cards-title">{t('announce.cards.heading')}</h2>
			<ul class="cards">
				{#each teams as team, i (team.id)}
					<li>
						<!-- svelte-ignore a11y-no-interactive-element-to-noninteractive-role -->
						<canvas class="preview" bind:this={cardCanvases[i]} role="img" aria-label={t('announce.card.alt', { name: team.name })}></canvas>
						<button type="button" class="pill" disabled={!ready} on:click={() => downloadCard(i)}>{t('announce.card.download', { name: team.name })}</button>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</div>

<style>
	.page {
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
		margin: 1.5rem 0 0.75rem;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	select {
		padding: 0.375rem 0.5rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	.preview {
		display: block;
		width: 100%;
		height: auto;
		margin-bottom: 0.75rem;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(18rem, 100%), 1fr));
		gap: 1.25rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.notice,
	.error {
		margin: 0 0 1rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		background: var(--bg-raised);
	}
	.error {
		color: var(--loss);
		border-color: var(--loss);
	}
	.hint {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0 0 1rem;
	}
	.submit,
	.pill,
	.pill-link {
		justify-self: start;
		display: inline-block;
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
	button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
