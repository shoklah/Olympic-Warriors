<script>
	import { createEventDispatcher, tick } from 'svelte';
	import { enhance } from '$app/forms';
	import { useT } from '$lib/i18n';
	import { modal } from '$lib/modal';

	/** A game as `disciplineSchedule` shapes it (ids, names, scores, isPlayed, refereeName). */
	export let game;
	/** 1-based round number for the label. */
	export let roundNumber;
	export let open = false;
	/** A dictionary key for the line under the form, or null. */
	export let error = null;

	const t = useT();
	const dispatch = createEventDispatcher();

	/** True from 1000px: on a phone the number field's keyboard would cover the sheet. */
	const desktop = () =>
		typeof window !== 'undefined' &&
		typeof window.matchMedia === 'function' &&
		window.matchMedia('(min-width: 1000px)').matches;

	/** The first score field, focused when the sheet opens on desktop; the sheet itself on
	    a phone, so opening it does not pop the keyboard. The page refocuses the row on close. */
	let firstField = null;
	let sheetEl = null;
	$: if (open && (firstField || sheetEl)) tick().then(() => (desktop() ? firstField : sheetEl)?.focus());

	// Local copies: the steppers edit these, the loaded game stays as it is until the
	// action succeeds and the page reloads its data.
	let score1 = 0;
	let score2 = 0;
	let played = true;
	// The switch starts on whenever the sheet opens: saving a score means the game was played.
	$: if (open) {
		score1 = game.score1 ?? 0;
		score2 = game.score2 ?? 0;
		played = true;
	}

	const clamp = (n) => Math.max(0, Number.isFinite(n) ? n : 0);
	const close = () => dispatch('close');
	// After a successful save the page's data reloads; the sheet closes on that success.
	// reset: false, so SvelteKit does not blank the fields and the switch before the
	// reloaded summary brings the saved values back.
	const afterSubmit = () => async ({ result, update }) => {
		await update({ reset: false });
		if (result.type === 'success') close();
	};
	$: title = `${t('discipline.round', { n: roundNumber })} · ${t('game.referee', { name: game.refereeName ?? t('team.unknown') })}`;
</script>

{#if open}
	<div class="backdrop" data-testid="backdrop" on:click={close} aria-hidden="true"></div>
	<div
		class="sheet"
		role="dialog"
		aria-modal="true"
		aria-label={title}
		tabindex="-1"
		bind:this={sheetEl}
		use:modal={{ onClose: close }}
	>
		<form method="POST" action="?/score" use:enhance={afterSubmit}>
			<input type="hidden" name="game" value={game.id} />
			<p class="label">{title}</p>

			<div class="line">
				<label class="name" for="score1-{game.id}">{game.team1Name ?? t('team.unknown')}</label>
				<span class="stepper">
					<button type="button" aria-label={t('orga.minus', { team: game.team1Name ?? t('team.unknown') })} on:click={() => (score1 = clamp(score1 - 1))}>−</button>
					<input id="score1-{game.id}" name="score1" type="number" inputmode="numeric" min="0" required bind:value={score1} bind:this={firstField} />
					<button type="button" aria-label={t('orga.plus', { team: game.team1Name ?? t('team.unknown') })} on:click={() => (score1 = clamp(score1 + 1))}>+</button>
				</span>
			</div>

			<div class="line">
				<label class="name" for="score2-{game.id}">{game.team2Name ?? t('team.unknown')}</label>
				<span class="stepper">
					<button type="button" aria-label={t('orga.minus', { team: game.team2Name ?? t('team.unknown') })} on:click={() => (score2 = clamp(score2 - 1))}>−</button>
					<input id="score2-{game.id}" name="score2" type="number" inputmode="numeric" min="0" required bind:value={score2} />
					<button type="button" aria-label={t('orga.plus', { team: game.team2Name ?? t('team.unknown') })} on:click={() => (score2 = clamp(score2 + 1))}>+</button>
				</span>
			</div>

			<label class="switch">
				<input type="checkbox" name="is_played" bind:checked={played} />
				<span class="track" aria-hidden="true"></span>
				{t('orga.played')}
			</label>

			{#if error}
				<p class="error" role="alert">{t(error)}</p>
			{/if}

			<div class="actions">
				<button type="button" class="ghost" on:click={close}>{t('orga.cancel')}</button>
				<button type="submit">{t('orga.save')}</button>
			</div>
		</form>
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

	.line {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin: 0.8rem 0;
	}

	.name {
		font-weight: 600;
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.stepper {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: none;
	}

	.stepper button {
		width: 44px;
		height: 44px;
		border-radius: var(--radius);
		background: var(--bg-sunken);
		border: 1px solid var(--line-strong);
		color: var(--accent);
		font-size: 1.4rem;
		cursor: pointer;
	}

	.stepper input {
		width: 3.2rem;
		height: 44px;
		text-align: center;
		background: var(--bg-sunken);
		border: 1px solid var(--line-strong);
		border-radius: var(--radius);
		color: var(--ink);
		font-family: var(--font-display);
		font-size: 1.5rem;
		-moz-appearance: textfield;
	}

	.stepper input::-webkit-outer-spin-button,
	.stepper input::-webkit-inner-spin-button {
		appearance: none;
		margin: 0;
	}

	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		margin: 0.4rem 0 0.8rem;
		cursor: pointer;
		color: var(--text);
	}

	.switch input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}

	.track {
		width: 36px;
		height: 20px;
		border-radius: var(--radius-pill);
		background: var(--line-strong);
		position: relative;
		transition: background 0.2s ease;
	}

	.track::after {
		content: '';
		position: absolute;
		top: 2px;
		left: 2px;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--ink);
		transition: transform 0.2s ease;
	}

	.switch input:checked + .track {
		background: var(--accent);
	}

	.switch input:checked + .track::after {
		transform: translateX(16px);
		background: var(--bg);
	}

	.switch input:focus-visible + .track {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.error {
		margin: 0 0 0.6rem;
		color: var(--loss);
		font-size: 0.85rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
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

	.actions .ghost {
		background: transparent;
		color: var(--accent);
	}

	button:focus-visible {
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
