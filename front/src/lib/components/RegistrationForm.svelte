<script>
	import { onMount } from 'svelte';
	import { disciplineName, useLocale, useT } from '$lib/i18n';
	import { MAX_SPORTS, choiceLabel, durationParts, emptySport, initialValues, listNames } from '$lib/registration';

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

	// The model the inputs read: what was typed before a refusal, else saved, else suggested.
	// It is loaded again only when `registration` or `form` is a different object (a new load
	// or a new post result). Svelte also marks them changed whenever an input bound inside an
	// `{#each registration.skills}` block is edited, so a plain `$: values = initialValues(...)`
	// ran on every keystroke and put the saved answers back under the player's hands.
	let values = initialValues(registration, form?.values ?? null);
	let loadedFrom = [registration, form];
	$: if (registration !== loadedFrom[0] || form !== loadedFrom[1]) {
		loadedFrom = [registration, form];
		values = initialValues(registration, form?.values ?? null);
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

{#if introText}<p class="intro">{introText}</p>{/if}

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
		<p class="notice">{t('register.registered')}</p>
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
				<dt>{t('register.teamWishes')}</dt>
				<dd>{saved.team_wishes || t('register.summary.none')}</dd>
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
	{:else if saved && !removedRow}
		<p class="notice">{t('register.withdrawn')}</p>
	{:else if registration.suggested}
		<p class="notice">{t('register.suggested', { year: registration.suggested.year })}</p>
	{/if}

	<form method="POST" action="?/save" class="registration">
		{#each registration.skills as skill}
			<input type="hidden" name="skill" value={skill.identifier} />
		{/each}

		<section aria-labelledby="register-skills">
			<h2 id="register-skills">
				{month ? t('register.skillsIntro', { month }) : t('register.skillsIntroNoMonth')}
			</h2>
			{#each registration.skills as skill}
				<div class="field">
					<label for="rating-{skill.identifier}">{skillName(skill)}</label>
					<input
						id="rating-{skill.identifier}"
						type="number"
						name="rating.{skill.identifier}"
						min="1"
						max="10"
						step="1"
						inputmode="numeric"
						required
						bind:value={values.ratings[skill.identifier]}
					/>
				</div>
			{/each}
			<div class="field">
				<label for="global-level">{t('register.globalLevel')}</label>
				<p class="hint" id="global-level-hint">
					{programme
						? t('register.globalQuestion', { year: edition.year, disciplines: programme })
						: t('register.globalQuestionShort', { year: edition.year })}
				</p>
				<input
					id="global-level"
					aria-describedby="global-level-hint"
					type="number"
					name="global_level"
					min="1"
					max="10"
					step="1"
					inputmode="numeric"
					required
					bind:value={values.global_level}
				/>
			</div>
		</section>

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
					<div class="field short">
						<label for="sport-{i}-years">{t('register.sports.years')}</label>
						<input id="sport-{i}-years" type="number" name="sport.{i}.years" min="0" step="1" bind:value={row.years} />
					</div>
					<div class="field short">
						<label for="sport-{i}-months">{t('register.sports.months')}</label>
						<input id="sport-{i}-months" type="number" name="sport.{i}.months" min="0" max="11" step="1" bind:value={row.months} />
					</div>
					<div class="field wide">
						<label for="sport-{i}-notes">{t('register.sports.notes')}</label>
						<input id="sport-{i}-notes" type="text" name="sport.{i}.notes" maxlength="200" bind:value={row.notes} />
					</div>
					<button type="button" class="pill remove" on:click={() => removeSport(i)}>
						{t('register.sports.remove', { n: i + 1 })}
					</button>
				</div>
			{/each}
			<button type="button" class="pill" disabled={values.sports.length >= MAX_SPORTS} on:click={addSport}>
				{t('register.sports.add')}
			</button>
		</fieldset>

		<div class="field">
			<label for="team-wishes">{t('register.teamWishes')}</label>
			<p class="hint" id="team-wishes-hint">{t('register.teamWishesHint')}</p>
			<textarea id="team-wishes" aria-describedby="team-wishes-hint" name="team_wishes" rows="3" maxlength="1000" bind:value={values.team_wishes}></textarea>
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

		{#if errorKeys.length > 0}
			<div class="error" id="register-errors" tabindex="-1" role="alert">
				{#each errorKeys as key}<p>{t(key)}</p>{/each}
			</div>
		{/if}

		<button class="submit">{registered ? t('register.submitEdit') : t('register.submit')}</button>
	</form>

	{#if registered}
		<form method="POST" action="?/withdraw" class="withdraw">
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
	.sport {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
		gap: 0.5rem 0.75rem;
		align-items: end;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--line);
	}
	.field.wide {
		grid-column: 1 / -1;
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
