<script>
	import { onMount, tick } from 'svelte';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import { MAX_SPORTS, choiceLabel, durationParts, emptySport, initialValues, listNames, stepOfForm } from '$lib/registration';

	/** The `GET /registration/` payload. */
	export let registration;
	/** The result of the last post to this page, or null. */
	export let form = null;

	const t = useT();
	const locale = useLocale();

	$: edition = registration.edition;
	$: open = registration.state.is_open;
	$: saved = registration.registration;
	$: registered = Boolean(saved?.registered);
	// An organiser removed this person's row; a late pass is how they let them back (the API
	// accepts the save then), so the form shows again while the pass is valid.
	$: removedRow = Boolean(saved?.removed_by_organiser);
	$: late = registration.state.reason === 'late_pass';
	$: removed = removedRow && !late;
	$: formShown = open && !removed;

	// The model the inputs read: what was typed before a refusal, else saved, else suggested.
	// It is loaded again only when `registration` or `form` is a different object (a new load
	// or a new post result). Svelte also marks them changed whenever an input bound inside an
	// `{#each registration.skills}` block is edited, so a plain `$: values = initialValues(...)`
	// ran on every keystroke and put the saved answers back under the player's hands.
	//
	// The wizard rides on the same identity check: a new post result puts it on the step of the
	// first refusal, and after a refusal every step is reachable (the player must be able to go
	// and fix what the server refused, wherever it is).
	const STEPS = [1, 2, 3];
	// The server renders every step, stacked and with no step controls, so a visitor without
	// JavaScript can still fill and submit the form; in the browser the wizard takes over.
	const js = typeof window !== 'undefined';
	const reachAfter = (result, at) => (result && !result.ok ? STEPS.length : at);

	let step = stepOfForm(form);
	let reached = reachAfter(form, step);
	let nextError = false;
	let formElement;
	let values = initialValues(registration, form?.values ?? null);
	let loadedFrom = [registration, form];
	$: if (registration !== loadedFrom[0] || form !== loadedFrom[1]) {
		loadedFrom = [registration, form];
		values = initialValues(registration, form?.values ?? null);
		step = stepOfForm(form);
		reached = Math.max(reached, reachAfter(form, step));
		nextError = false;
	}

	// A month in the wrong language would sit oddly in a sentence: none beats the French one.
	$: month = registration.skills_month[locale] || '';
	$: skillName = (skill) => (locale === 'fr' ? skill.name_fr : skill.name_en);
	$: programme = listNames(
		locale,
		registration.disciplines.map((name) => disciplineName(locale, name))
	);
	$: introText = registration.intro[locale] || registration.intro.fr || '';

	/** The date the registration opens, in words. */
	$: opensOn = registration.edition.opens
		? new Intl.DateTimeFormat(locale === 'fr' ? 'fr' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(
				new Date(`${registration.edition.opens}T12:00:00Z`)
			)
		: '';

	$: resultOf = (action) => (form?.action === action ? form : null);
	$: saveResult = resultOf('save');
	$: withdrawResult = resultOf('withdraw');
	$: errorKeys = saveResult?.errors ?? (saveResult?.error ? [saveResult.error] : []);

	/** Moves to a step and puts focus on its heading, so a screen reader announces it. */
	async function goTo(n) {
		step = n;
		reached = Math.max(reached, n);
		nextError = false;
		await tick();
		const heading = document.getElementById(`register-step-${n}`);
		heading?.focus();
		heading?.scrollIntoView?.({ block: 'start' });
	}

	/** The fields of a step, in the form. */
	const fieldsOf = (n) => [...(formElement?.querySelector(`[data-step="${n}"]`)?.querySelectorAll('input, select, textarea') ?? [])];

	/** Whether the step's required fields are filled; the browser shows its own message on the first that is not. */
	const stepIsValid = (n) => fieldsOf(n).every((field) => field.reportValidity());

	function next() {
		if (!stepIsValid(step)) {
			nextError = true;
			return;
		}
		goTo(step + 1);
	}

	/** A submit with a required field blank on another step (reachable after a refusal) opens that step first. */
	async function onSubmit(event) {
		const bad = STEPS.find((n) => fieldsOf(n).some((field) => !field.checkValidity()));
		if (bad === undefined) return;
		event.preventDefault();
		if (bad !== step) await goTo(bad);
		stepIsValid(bad);
	}

	/** The label of a stored choice for the summary, the dash for none. */
	function summaryChoice(kind, value) {
		const choice = registration.choices[kind]?.find((c) => c.value === value);
		return choice ? choiceLabel(t, kind, choice) : t('register.summary.none');
	}

	/** One sports row as a line: sport, level, practice, how long, details; blanks left out. */
	function sportLine(row) {
		const { years, months } = durationParts(row.duration_months);
		const duration = [
			Number(years) > 0 && t('register.summary.years', { n: Number(years) }),
			Number(months) > 0 && t('register.summary.months', { n: Number(months) })
		]
			.filter(Boolean)
			.join(' ');
		return [
			row.sport,
			row.level && summaryChoice('level', row.level),
			row.practice && summaryChoice('practice', row.practice),
			duration,
			row.notes
		]
			.filter(Boolean)
			.join(' · ');
	}

	function addSport() {
		if (values.sports.length < MAX_SPORTS) values.sports = [...values.sports, emptySport()];
	}
	function removeSport(index) {
		const rest = values.sports.filter((_, i) => i !== index);
		values.sports = rest.length > 0 ? rest : [emptySport()];
	}

	// A plain POST reloads the page with the message not announced: focus it.
	onMount(() => {
		const target = document.getElementById(form?.ok ? 'register-status' : 'register-errors');
		if (!target || !form) return;
		target.focus();
		target.scrollIntoView?.({ block: 'center' });
	});
</script>

{#if introText && !formShown}<p class="intro">{introText}</p>{/if}

{#if late}<p class="notice">{t('register.latePass')}</p>{/if}

{#if removed}
	<p class="notice" role="note">{t('register.removed')}</p>
{:else if !open}
	{#if registration.state.reason === 'not_yet_open' && opensOn}
		<p class="notice">{t('register.closed.not_yet_open', { date: opensOn })}</p>
	{:else}
		<p class="notice">{t(`register.closed.${registration.state.reason === 'closed' ? 'closed' : 'not_configured'}`)}</p>
	{/if}
	{#if registered && saved}
		<p class="notice">{t('register.registeredClosed')}</p>
		<!-- Closed: what they submitted stays readable (the form is gone). -->
		<section class="summary" aria-labelledby="register-summary">
			<h2 id="register-summary">{t('register.summary.title')}</h2>
			<dl>
				{#each registration.skills as skill}
					<dt>{skillName(skill)}</dt>
					<dd>{saved.ratings?.[skill.identifier] ?? t('register.summary.none')}</dd>
				{/each}
				<dt>{t('register.globalLevel')}</dt>
				<dd>{saved.global_level ?? t('register.summary.none')}</dd>
				<dt>{t('register.frequency.legend')}</dt>
				<dd>{summaryChoice('frequency', saved.sport_frequency)}</dd>
				<dt>{t('register.sports.legend')}</dt>
				<dd>
					{#if saved.sports.length === 0}
						{t('register.summary.none')}
					{:else}
						<ul>
							{#each saved.sports as row}
								<li>{sportLine(row)}</li>
							{/each}
						</ul>
					{/if}
				</dd>
				<dt>{t('register.summary.with')}</dt>
				<dd>{saved.team_with || t('register.summary.none')}</dd>
				<dt>{t('register.summary.avoid')}</dt>
				<dd>{saved.team_avoid || t('register.summary.none')}</dd>
				<dt>{t('register.dietary')}</dt>
				<dd>{saved.dietary_restrictions || t('register.summary.none')}</dd>
			</dl>
			{#if saved.attendance_confirmed}<p class="notes">{t('register.summary.attendance')}</p>{/if}
		</section>
	{/if}
{:else}
	{#if form?.ok && form.action === 'save'}
		<p class="saved" id="register-status" tabindex="-1" role="status">{t('register.saved')}</p>
	{:else if form?.ok && form.action === 'withdraw'}
		<p class="saved" id="register-status" tabindex="-1" role="status">{t('register.withdrawn')}</p>
	{/if}
	{#if registered}
		<p class="notice">{t('register.registered')}</p>
	{:else if saved && !removedRow && !(form?.ok && form.action === 'withdraw')}
		<!-- Not right after a withdrawal: the status line above already says it. -->
		<p class="notice">{t('register.withdrawn')}</p>
	{:else if registration.suggested}
		<p class="notice">{t('register.suggested', { year: registration.suggested.year })}</p>
	{/if}

	{#if errorKeys.length > 0}
		<div class="error" id="register-errors" tabindex="-1" role="alert">
			{#each errorKeys as key}<p>{t(key)}</p>{/each}
		</div>
	{/if}

	<nav class="progress" hidden={!js} aria-label={t('register.steps.label')}>
		<p class="progress-text num">{t('register.step.of', { n: step, total: STEPS.length })}</p>
		<div
			class="bar"
			role="progressbar"
			aria-label={t('register.steps.label')}
			aria-valuemin="1"
			aria-valuemax={STEPS.length}
			aria-valuenow={step}
			aria-valuetext={t('register.step.of', { n: step, total: STEPS.length })}
		>
			<div class="fill" style="width: {(step / STEPS.length) * 100}%"></div>
		</div>
		<ol>
			{#each STEPS as n}
				<li>
					<button
						type="button"
						class="step-name"
						aria-current={n === step ? 'step' : undefined}
						disabled={!(registered || n <= reached)}
						on:click={() => goTo(n)}
					>
						<span class="num" aria-hidden="true">{n}</span>
						{t(`register.step.${n}`)}
					</button>
				</li>
			{/each}
		</ol>
	</nav>

	<form method="POST" action="?/save" class="registration" bind:this={formElement} on:submit={onSubmit}>
		{#each registration.skills as skill}
			<input type="hidden" name="skill" value={skill.identifier} />
		{/each}

		<div class="step" data-step="1" hidden={js && step !== 1}>
			<h2 id="register-step-1" tabindex="-1">{t('register.step.1')}</h2>
			{#if introText}<p class="intro">{introText}</p>{/if}
			<fieldset>
				<legend>{t('register.frequency.legend')}</legend>
				{#each registration.choices.frequency as choice}
					<label class="radio">
						<input type="radio" name="sport_frequency" value={choice.value} required bind:group={values.sport_frequency} />
						{choiceLabel(t, 'frequency', choice)}
					</label>
				{/each}
			</fieldset>

			<fieldset class="sports">
				<legend>{t('register.sports.legend')}</legend>
				{#each values.sports as row, i}
					<div class="sport" role="group" aria-label="{t('register.sports.sport')} {i + 1}">
						<div class="fields">
						<div class="field">
							<label for="sport-{i}-sport">{t('register.sports.sport')}</label>
							<input id="sport-{i}-sport" type="text" name="sport.{i}.sport" maxlength="80" bind:value={row.sport} />
						</div>
						<div class="field">
							<label for="sport-{i}-level">{t('register.sports.level')}</label>
							<select id="sport-{i}-level" name="sport.{i}.level" bind:value={row.level}>
								<option value="">{t('register.sports.none')}</option>
								{#each registration.choices.level as choice}
									<option value={choice.value}>{choiceLabel(t, 'level', choice)}</option>
								{/each}
							</select>
						</div>
						<div class="field">
							<label for="sport-{i}-practice">{t('register.sports.practice')}</label>
							<select id="sport-{i}-practice" name="sport.{i}.practice" bind:value={row.practice}>
								<option value="">{t('register.sports.none')}</option>
								{#each registration.choices.practice as choice}
									<option value={choice.value}>{choiceLabel(t, 'practice', choice)}</option>
								{/each}
							</select>
						</div>
						<div class="duration">
							<div class="field short">
								<label for="sport-{i}-years">{t('register.sports.years')}</label>
								<input id="sport-{i}-years" type="number" name="sport.{i}.years" min="0" step="1" bind:value={row.years} />
							</div>
							<div class="field short">
								<label for="sport-{i}-months">{t('register.sports.months')}</label>
								<input id="sport-{i}-months" type="number" name="sport.{i}.months" min="0" max="11" step="1" bind:value={row.months} />
							</div>
						</div>
						<div class="field wide">
							<label for="sport-{i}-notes">{t('register.sports.notes')}</label>
							<input id="sport-{i}-notes" type="text" name="sport.{i}.notes" maxlength="200" bind:value={row.notes} />
						</div>
						</div>
						<button
							type="button"
							class="icon-button remove"
							title={t('register.sports.remove', { n: i + 1 })}
							aria-label={t('register.sports.remove', { n: i + 1 })}
							on:click={() => removeSport(i)}
						>
							<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
								<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12M9 7V4h6v3" />
							</svg>
						</button>
					</div>
				{/each}
				<button
					type="button"
					class="icon-button add"
					disabled={values.sports.length >= MAX_SPORTS}
					title={t('register.sports.add')}
					aria-label={t('register.sports.add')}
					on:click={addSport}
				>
					<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 5v14M5 12h14" /></svg>
				</button>
			</fieldset>
		</div>

		<div class="step" data-step="2" hidden={js && step !== 2}>
			<h2 id="register-step-2" tabindex="-1">{t('register.step.2')}</h2>
			<p class="lead" id="register-skills">
				{month ? t('register.skillsIntro', { month }) : t('register.skillsIntroNoMonth')}
			</p>
			{#each registration.skills as skill}
				<div class="field slider">
					<label for="rating-{skill.identifier}">{skillName(skill)}</label>
					<div class="range">
						<span class="end" aria-hidden="true" title={t('register.scaleLow')}>1</span>
						<input
							id="rating-{skill.identifier}"
							type="range"
							name="rating.{skill.identifier}"
							min="1"
							max="10"
							step="1"
							aria-describedby="rating-{skill.identifier}-value"
							bind:value={values.ratings[skill.identifier]}
						/>
						<span class="end" aria-hidden="true" title={t('register.scaleHigh')}>10</span>
						<output id="rating-{skill.identifier}-value" for="rating-{skill.identifier}" class="value num">{values.ratings[skill.identifier]}</output>
					</div>
				</div>
			{/each}
			<div class="field slider">
				<label for="global-level">{t('register.globalLevel')}</label>
				<p class="hint" id="global-level-hint">
					{programme
						? t('register.globalQuestion', { year: edition.year, disciplines: programme })
						: t('register.globalQuestionShort', { year: edition.year })}
				</p>
				<div class="range">
					<span class="end" aria-hidden="true" title={t('register.scaleLow')}>1</span>
					<input
						id="global-level"
						type="range"
						name="global_level"
						min="1"
						max="10"
						step="1"
						aria-describedby="global-level-hint global-level-value"
						bind:value={values.global_level}
					/>
					<span class="end" aria-hidden="true" title={t('register.scaleHigh')}>10</span>
					<output id="global-level-value" for="global-level" class="value num">{values.global_level}</output>
				</div>
			</div>
		</div>

		<div class="step" data-step="3" hidden={js && step !== 3}>
			<h2 id="register-step-3" tabindex="-1">{t('register.step.3')}</h2>
			<div class="field">
				<label for="team-with">{t('register.teamWith')}</label>
				<p class="hint" id="team-with-hint">{t('register.teamWithHint')}</p>
				<textarea id="team-with" aria-describedby="team-with-hint" name="team_with" rows="3" maxlength="500" bind:value={values.team_with}></textarea>
			</div>
			<div class="field">
				<label for="team-avoid">{t('register.teamAvoid')}</label>
				<p class="hint" id="team-avoid-hint">{t('register.teamAvoidHint')}</p>
				<textarea id="team-avoid" aria-describedby="team-avoid-hint" name="team_avoid" rows="3" maxlength="500" bind:value={values.team_avoid}></textarea>
			</div>

			<div class="field">
				<label for="dietary">{t('register.dietary')} <span class="optional">({t('register.optional')})</span></label>
				<textarea id="dietary" name="dietary_restrictions" rows="2" maxlength="500" bind:value={values.dietary_restrictions}></textarea>
			</div>

			{#if registration.email.editable}
				<div class="field">
					<label for="register-email">{t('register.email')}</label>
					<p class="hint" id="register-email-hint">{t('register.emailNeeded')}</p>
					<input id="register-email" aria-describedby="register-email-hint" type="email" name="email" autocomplete="email" required bind:value={values.email} />
				</div>
			{:else}
				<p class="email">
					<span class="label">{t('register.email')}</span>
					<span>{registration.email.value}</span>
					<a class="quiet-link" href="/account">{t('register.emailChange')}</a>
				</p>
			{/if}

			<label class="check">
				<input type="checkbox" name="attendance_confirmed" required bind:checked={values.attendance_confirmed} />
				{t('register.attendance')}
			</label>

			<p class="notes">{t('register.visibility')}</p>
			<p class="notes">{t('register.retention')}</p>
		</div>

		<div class="nav-buttons">
			{#if nextError}<p class="error" role="alert">{t('register.step.incomplete')}</p>{/if}
			{#if js && step > 1}
				<button type="button" class="pill" on:click={() => goTo(step - 1)}>{t('register.step.previous')}</button>
			{/if}
			{#if js && step < STEPS.length}
				<button type="button" class="submit" on:click={next}>{t('register.step.next')}</button>
			{/if}
			<button class="submit final" hidden={js && step !== STEPS.length}>{registered ? t('register.submitEdit') : t('register.submit')}</button>
		</div>
	</form>

	{#if registered}
		<form method="POST" action="?/withdraw" class="withdraw" hidden={js && step !== STEPS.length}>
			<p class="notes">{t('register.withdrawNote')}</p>
			{#if withdrawResult?.error}
				<p class="error" id="register-errors" tabindex="-1" role="alert">{t(withdrawResult.error)}</p>
			{/if}
			<button class="pill">{t('register.withdraw')}</button>
		</form>
	{/if}
{/if}

<style>
	.registration {
		display: grid;
		gap: 1.25rem;
	}
	.intro,
	.notice {
		margin: 0 0 1rem;
	}
	.notice {
		padding: 0.75rem 1rem;
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		background: var(--bg-raised);
	}
	h2 {
		font-size: 1rem;
		font-family: var(--font-body);
		text-transform: none;
		letter-spacing: 0;
		margin: 0 0 0.75rem;
	}
	.step[hidden],
	.final[hidden],
	.withdraw[hidden],
	.progress[hidden] {
		display: none;
	}
	.progress {
		margin: 0 0 1.25rem;
	}
	.progress-text {
		margin: 0 0 0.5rem;
		color: var(--muted);
	}
	.bar {
		height: 0.375rem;
		border-radius: 999px;
		background: var(--bg-sunken);
		border: 1px solid var(--line);
		overflow: hidden;
	}
	.fill {
		height: 100%;
		background: var(--accent);
	}
	.progress ol {
		display: flex;
		gap: 0.5rem;
		list-style: none;
		margin: 0.75rem 0 0;
		padding: 0;
	}
	.progress li {
		flex: 1;
	}
	.step-name {
		width: 100%;
		padding: 0.5rem;
		background: transparent;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--muted);
		font: inherit;
		cursor: pointer;
	}
	.step-name[aria-current='step'] {
		color: var(--ink);
		border-color: var(--accent);
	}
	.step-name:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.range {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		max-width: 28rem;
	}
	.range input[type='range'] {
		flex: 1;
		accent-color: var(--accent);
		min-height: 2rem;
	}
	.end {
		color: var(--muted);
		font-size: 0.875rem;
	}
	.value {
		min-width: 2ch;
		font-size: 1.75rem;
		text-align: right;
		color: var(--ink);
	}
	.lead {
		margin: 0 0 1rem;
	}
	.nav-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
	}
	.nav-buttons .error {
		flex-basis: 100%;
	}
	.field {
		display: grid;
		gap: 0.25rem;
		margin-bottom: 0.75rem;
	}
	.field label,
	legend {
		font-weight: 600;
	}
	.hint,
	.notes,
	.optional {
		color: var(--muted);
		font-size: 0.875rem;
		margin: 0;
	}
	input[type='number'],
	input[type='text'],
	input[type='email'],
	select,
	textarea {
		width: 100%;
		max-width: 28rem;
		padding: 0.5rem 0.625rem;
		background: var(--bg-sunken);
		color: var(--ink);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		font: inherit;
	}
	input[type='number'] {
		max-width: 6rem;
	}
	fieldset {
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin: 0;
	}
	.radio,
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		padding: 0.25rem 0;
	}
	fieldset + fieldset {
		margin-top: 1.5rem;
	}
	.sport {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.75rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--line);
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
		gap: 0.5rem 0.75rem;
		align-items: end;
	}
	.icon-button {
		display: inline-grid;
		place-items: center;
		width: 2.5rem;
		height: 2.5rem;
		padding: 0;
		border-radius: 999px;
		border: 1px solid var(--line-strong);
		background: transparent;
		color: var(--muted);
		cursor: pointer;
	}
	.icon-button:hover:not(:disabled),
	.icon-button:focus-visible {
		color: var(--accent);
		border-color: var(--accent);
	}
	.icon-button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.icon-button svg {
		width: 1.25rem;
		height: 1.25rem;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	/* Level with the first row of inputs: skip the first label (its line and the field's gap). */
	.remove {
		align-self: start;
		margin-top: calc(1lh + 0.25rem);
	}
	.add {
		margin-top: 0.75rem;
	}
	.field.wide {
		grid-column: 1 / -1;
	}
	.duration {
		display: flex;
		gap: 0.5rem;
		align-items: end;
	}
	.duration .field {
		margin-bottom: 0;
	}
	.field.short input {
		max-width: 5rem;
	}
	.error,
	.saved {
		margin: 0;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
	}
	.error {
		color: var(--loss);
		border: 1px solid var(--loss);
	}
	.saved {
		color: var(--win);
		border: 1px solid var(--win);
		margin-bottom: 1rem;
	}
	.submit,
	.pill {
		justify-self: start;
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
	.pill:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.summary dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.25rem 1rem;
		margin: 0;
	}
	.summary dt {
		color: var(--muted);
	}
	.summary dd {
		margin: 0;
	}
	.summary ul {
		margin: 0;
		padding-left: 1rem;
	}
	.withdraw {
		display: grid;
		gap: 0.5rem;
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--line);
	}
	.email {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: baseline;
		margin: 0;
	}
</style>
