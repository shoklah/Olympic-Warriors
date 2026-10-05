import { tick } from 'svelte';
import { fireEvent, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { renderWith } from '$lib/test-utils';
import RegistrationForm from './RegistrationForm.svelte';
import { registrationPayload, savedAnswers } from '$lib/fixtures/registration.js';
import { initialValues } from '$lib/registration';

const open = registrationPayload;
const registered = { ...registrationPayload, registration: savedAnswers };
/** Opens a step the way a player does: a new one picks a frequency and goes forward. */
async function toStep(n) {
	for (let step = 1; step < n; step += 1) {
		const radios = screen.queryAllByRole('radio');
		if (radios.length > 0 && !radios.some((radio) => radio.checked)) await fireEvent.click(radios[0]);
		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await tick();
	}
}

const closed = (reason) => ({ ...registrationPayload, state: { is_open: false, reason } });

describe('RegistrationForm', () => {
	it('shows the intro, one rating field per skill and the global question with the programme', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(screen.getByText('Welcome to registration')).toBeInTheDocument();
		expect(screen.getByText(/the level you will have in August/)).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toHaveAttribute('name', 'rating.CARD');
		expect(screen.getByLabelText('Strength')).toHaveAttribute('name', 'rating.STR');
		expect(screen.getByLabelText('Cardio')).toHaveAttribute('min', '1');
		expect(screen.getByLabelText('Cardio')).toHaveAttribute('max', '10');
		expect(
			screen.getByText('On a scale from 1 to 10, how would you rate your overall level for Olympic Warriors 2027: Relay and Darts?')
		).toBeInTheDocument();
		// The skills travel with the form, so the server knows which ratings to read.
		expect(document.querySelectorAll('input[type="hidden"][name="skill"]')).toHaveLength(2);
	});

	it('leaves the month out when the edition names none, and the programme when it has none', () => {
		renderWith(RegistrationForm, {
			registration: { ...open, skills_month: { fr: '', en: '' }, disciplines: [] }
		});

		expect(screen.getByText(/how would you rate your level on the following criteria/)).toBeInTheDocument();
		expect(screen.getByText(/overall level for Olympic Warriors 2027\?/)).toBeInTheDocument();
	});

	it('offers the five frequencies as radios, with the dictionary wording', () => {
		renderWith(RegistrationForm, { registration: open });

		const group = screen.getByRole('group', { name: 'How often do you play sport?' });
		expect(within(group).getAllByRole('radio')).toHaveLength(5);
		expect(within(group).getByLabelText('At least two hours a week')).toHaveAttribute('value', 'two_hours');
	});

	it('shows the email read-only, with a way to change it, when the account has a usable one', async () => {
		renderWith(RegistrationForm, { registration: open });
		await toStep(3);

		expect(screen.getByText('lea@example.com')).toBeInTheDocument();
		expect(screen.queryByRole('textbox', { name: 'Email address' })).toBeNull();
		expect(screen.getByRole('link', { name: 'Change my address' })).toHaveAttribute('href', '/account');
	});

	it('asks for an email when the account has none', async () => {
		renderWith(RegistrationForm, { registration: { ...open, email: { value: '', editable: true } } });
		await toStep(3);

		const field = screen.getByRole('textbox', { name: 'Email address' });
		expect(field).toHaveAttribute('name', 'email');
		expect(field).toBeRequired();
		expect(screen.getByText(/also lets you recover your password/)).toBeInTheDocument();
	});

	it('requires the confirmation tick and shows the visibility and retention notices', async () => {
		renderWith(RegistrationForm, { registration: open });
		await toStep(3);

		expect(screen.getByRole('checkbox', { name: /I have paid my registration/ })).toBeRequired();
		expect(screen.getByText('Your name will appear in the players list.')).toBeInTheDocument();
		expect(screen.getByText(/kept as long as your account exists/)).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
	});

	it('adds and removes sports rows, indexed in order', async () => {
		renderWith(RegistrationForm, { registration: open });

		expect(screen.getAllByRole('textbox', { name: 'Sport' })).toHaveLength(1);
		await fireEvent.click(screen.getByRole('button', { name: 'Add a sport' }));
		const rows = screen.getAllByRole('textbox', { name: 'Sport' });
		expect(rows.map((r) => r.getAttribute('name'))).toEqual(['sport.0.sport', 'sport.1.sport']);

		await fireEvent.click(screen.getByRole('button', { name: 'Remove sport 1' }));
		expect(screen.getAllByRole('textbox', { name: 'Sport' })).toHaveLength(1);
		expect(screen.getByRole('textbox', { name: 'Sport' })).toHaveAttribute('name', 'sport.0.sport');
	});

	it('keeps the rows and what is typed in them while the player types', async () => {
		renderWith(RegistrationForm, { registration: registered });
		await fireEvent.click(screen.getByRole('button', { name: 'Add a sport' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Add a sport' }));

		const rows = screen.getAllByRole('textbox', { name: 'Sport' });
		await fireEvent.input(rows[2], { target: { value: 'Tennis' } });
		await fireEvent.input(screen.getByLabelText('Cardio'), { target: { value: '9' } });

		const after = screen.getAllByRole('textbox', { name: 'Sport' });
		expect(after).toHaveLength(3);
		expect(after.map((r) => r.value)).toEqual(['Judo', '', 'Tennis']);
		expect(screen.getByLabelText('Cardio')).toHaveValue('9');
	});

	it('loads the posted values again when a new post result arrives', async () => {
		const { component } = renderWith(RegistrationForm, { registration: open });
		await fireEvent.input(screen.getByLabelText('Cardio'), { target: { value: '3' } });
		expect(screen.getByLabelText('Cardio')).toHaveValue('3');

		const posted = { ...initialValues(open), ratings: { CARD: '9', STR: '' }, team_with: 'posted wish' };
		await component.$set({ form: { action: 'save', errors: ['register.error.missing_rating'], values: posted } });

		expect(screen.getByLabelText('Cardio')).toHaveValue('9');
		expect(screen.getByLabelText('Who would you like to be with?')).toHaveValue('posted wish');
	});

	it('stops adding at fifteen sports', async () => {
		renderWith(RegistrationForm, { registration: open });
		for (let i = 0; i < 14; i++) await fireEvent.click(screen.getByRole('button', { name: 'Add a sport' }));

		expect(screen.getAllByRole('textbox', { name: 'Sport' })).toHaveLength(15);
		expect(screen.getByRole('button', { name: 'Add a sport' })).toBeDisabled();
	});

	it('fills the saved answers and offers to withdraw', async () => {
		renderWith(RegistrationForm, { registration: registered });

		expect(screen.getByLabelText('Cardio')).toHaveValue('6');
		expect(screen.getByLabelText('Overall level')).toHaveValue('8');
		expect(screen.getByRole('radio', { name: 'At least two hours a week' })).toBeChecked();
		expect(screen.getByRole('textbox', { name: 'Sport' })).toHaveValue('Judo');
		expect(screen.getByRole('spinbutton', { name: 'Years' })).toHaveValue(2);
		expect(screen.getByRole('spinbutton', { name: 'Months' })).toHaveValue(6);
		expect(screen.getByText(/You are registered/)).toBeInTheDocument();
		await toStep(3);
		expect(screen.getByRole('button', { name: 'Save my answers' })).toBeInTheDocument();
		const withdraw = screen.getByRole('button', { name: 'Withdraw my registration' });
		expect(withdraw.closest('form')).toHaveAttribute('action', '?/withdraw');
	});

	it('tells someone suggested answers were taken from last time', () => {
		const suggested = {
			year: 2026, sport_frequency: 'hour', dietary_restrictions: 'Sans gluten',
			sports: [{ sport: 'Tennis', level: '', practice: '', duration_months: null, notes: '' }]
		};
		renderWith(RegistrationForm, { registration: { ...open, suggested } });

		expect(screen.getByText('Taken from your 2026 registration: check that everything is up to date.')).toBeInTheDocument();
		expect(screen.getByRole('textbox', { name: 'Sport' })).toHaveValue('Tennis');
		expect(screen.getByRole('radio', { name: 'About one hour a week' })).toBeChecked();
	});

	it('keeps what was typed after a refusal and lists every error', () => {
		const values = {
			ratings: { CARD: '9', STR: '' }, global_level: '', sport_frequency: '', sports: [],
			team_with: 'typed wish', team_avoid: '', dietary_restrictions: '', attendance_confirmed: false, email: ''
		};
		renderWith(RegistrationForm, {
			registration: open,
			form: { action: 'save', errors: ['register.error.missing_rating', 'register.error.attendance_required'], values }
		});

		const alert = screen.getByRole('alert');
		expect(within(alert).getByText('Rate every criterion')).toBeInTheDocument();
		expect(within(alert).getByText('Tick the confirmation box')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toHaveValue('9');
		expect(screen.getByLabelText('Who would you like to be with?')).toHaveValue('typed wish');
	});

	it('words a single refusal and confirms a save', () => {
		const { unmount } = renderWith(RegistrationForm, {
			registration: open, form: { action: 'save', error: 'register.error.closed', values: undefined }
		});
		expect(screen.getByRole('alert')).toHaveTextContent('Registration is closed.');
		unmount();

		renderWith(RegistrationForm, { registration: registered, form: { ok: true, action: 'save' } });
		expect(screen.getByRole('status')).toHaveTextContent('Registration saved');
	});

	it('shows the has_team refusal of a withdrawal', () => {
		renderWith(RegistrationForm, {
			registration: registered, form: { action: 'withdraw', error: 'register.error.has_team' }
		});

		expect(screen.getByRole('alert')).toHaveTextContent('You are already in a team');
	});

	it.each([
		['not_configured', 'Registration is not open yet.'],
		['not_yet_open', 'Registration opens on 1 January 2027.'],
		['closed', 'Registration is closed. Contact the organisers for any request.']
	])('shows a %s registration as a notice, with no form', (reason, text) => {
		renderWith(RegistrationForm, { registration: closed(reason) });

		expect(screen.getByText(text)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Register' })).toBeNull();
		expect(screen.queryByLabelText('Cardio')).toBeNull();
	});

	it('shows a registered player their answers, read-only, once registration is closed', () => {
		renderWith(RegistrationForm, { registration: { ...closed('closed'), registration: savedAnswers } });

		const summary = screen.getByRole('region', { name: 'Your answers' });
		expect(within(summary).getByText('Cardio')).toBeInTheDocument();
		expect(within(summary).getByText('6')).toBeInTheDocument();
		expect(within(summary).getByText('At least two hours a week')).toBeInTheDocument();
		expect(within(summary).getByText(/Judo/)).toHaveTextContent('Amateur');
		expect(within(summary).getByText(/Judo/)).toHaveTextContent('2 years 6 months');
		expect(within(summary).getByText(/Judo/)).toHaveTextContent('Ceinture orange');
		expect(within(summary).getByText('Avec Bob')).toBeInTheDocument();
		expect(within(summary).getByText('Végane')).toBeInTheDocument();
		expect(within(summary).getByText('Attendance confirmed')).toBeInTheDocument();
		expect(screen.queryByRole('spinbutton')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
		// Closed: it must not promise an edit.
		expect(screen.getByText('You are registered.')).toBeInTheDocument();
		expect(screen.queryByText(/edit your answers/)).toBeNull();
	});

	it('says a withdrawal once, not as a status and again as a notice', () => {
		renderWith(RegistrationForm, {
			registration: { ...registered, registration: { ...savedAnswers, registered: false } },
			form: { ok: true, action: 'withdraw' }
		});

		expect(screen.getAllByText('You are withdrawn. Your answers are kept.')).toHaveLength(1);
		expect(screen.getByRole('status')).toHaveTextContent('You are withdrawn');
	});

	it('shows no summary to someone who is not registered, withdrew, or was removed', () => {
		const none = renderWith(RegistrationForm, { registration: closed('closed') });
		expect(screen.queryByRole('region', { name: 'Your answers' })).toBeNull();
		none.unmount();

		const withdrew = renderWith(RegistrationForm, {
			registration: { ...closed('closed'), registration: { ...savedAnswers, registered: false } }
		});
		expect(screen.queryByRole('region', { name: 'Your answers' })).toBeNull();
		withdrew.unmount();

		renderWith(RegistrationForm, {
			registration: { ...closed('closed'), registration: { ...savedAnswers, registered: false, removed_by_organiser: true } }
		});
		expect(screen.queryByRole('region', { name: 'Your answers' })).toBeNull();
	});

	it('speaks French in the summary', () => {
		renderWith(RegistrationForm, { registration: { ...closed('closed'), registration: savedAnswers } }, 'fr');

		expect(screen.getByRole('region', { name: 'Vos réponses' })).toBeInTheDocument();
		expect(screen.getByText(/Judo/)).toHaveTextContent('2 ans 6 mois');
	});

	it('mentions a late pass and shows the form', () => {
		renderWith(RegistrationForm, { registration: { ...open, state: { is_open: true, reason: 'late_pass' } } });

		expect(screen.getByText('The organisers have allowed your late registration.')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toBeInTheDocument();
	});

	it('explains an organiser removal and shows no form', () => {
		renderWith(RegistrationForm, {
			registration: { ...registered, registration: { ...savedAnswers, registered: false, removed_by_organiser: true } }
		});

		expect(screen.getByText(/An organiser removed your registration/)).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Save my answers' })).toBeNull();
	});

	it('shows the form again to an organiser-removed player who holds a late pass', async () => {
		renderWith(RegistrationForm, {
			registration: {
				...registered,
				state: { is_open: true, reason: 'late_pass' },
				registration: { ...savedAnswers, registered: false, removed_by_organiser: true }
			}
		});

		expect(screen.getByText('The organisers have allowed your late registration.')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toHaveValue('6');
		await toStep(3);
		expect(screen.queryByText(/An organiser removed your registration/)).toBeNull();
		expect(screen.queryByText('You are withdrawn. Your answers are kept.')).toBeNull();
		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
	});

	it('ties the question and the hints to their fields', () => {
		renderWith(RegistrationForm, { registration: { ...open, email: { value: '', editable: true } } });

		expect(screen.getByLabelText('Overall level')).toHaveAccessibleDescription(/overall level for Olympic Warriors 2027/);
		expect(screen.getByLabelText('Who would you like to be with?')).toHaveAccessibleDescription(/stay confidential/);
		expect(screen.getByLabelText('Email address')).toHaveAccessibleDescription(/recover your password/);
	});

	it('shows a withdrawn registration as withdrawn, with the form to register again', async () => {
		renderWith(RegistrationForm, {
			registration: { ...registered, registration: { ...savedAnswers, registered: false } }
		});
		expect(screen.getByLabelText('Cardio')).toHaveValue('6');
		await toStep(3);

		expect(screen.getByText('You are withdrawn. Your answers are kept.')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
	});

	it('speaks French', () => {
		renderWith(RegistrationForm, { registration: open }, 'fr');

		expect(screen.getByText('Bienvenue aux inscriptions')).toBeInTheDocument();
		expect(screen.getByLabelText('Cardio')).toBeInTheDocument();
		expect(screen.getByLabelText('Force')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Suivant' })).toBeInTheDocument();
		expect(document.querySelector('.final')).toHaveTextContent("M'inscrire");
		expect(screen.getByText('Votre nom apparaîtra dans la liste des joueurs.')).toBeInTheDocument();
		expect(screen.getByText(/pour les Olympic Warriors de 2027 : Relais et Fléchettes/)).toBeInTheDocument();
	});
});

describe('RegistrationForm wizard', () => {
	const step = (n) => document.querySelector(`[data-step="${n}"]`);
	const stepsNav = () => screen.getByRole('navigation', { name: 'Registration steps' });

	it('shows step 1 only, with the progress, and no previous button', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(step(1)).not.toHaveAttribute('hidden');
		expect(step(2)).toHaveAttribute('hidden');
		expect(step(3)).toHaveAttribute('hidden');
		expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
		expect(within(stepsNav()).getByRole('button', { name: 'Your sports background' })).toHaveAttribute('aria-current', 'step');
		expect(screen.queryByRole('button', { name: 'Previous' })).toBeNull();
		expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
		expect(screen.queryByRole('button', { name: 'Register' })).toBeNull();
	});

	it('refuses to leave step 1 without a frequency, then goes forward once it is chosen', async () => {
		renderWith(RegistrationForm, { registration: open });

		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));

		expect(step(1)).not.toHaveAttribute('hidden');
		expect(screen.getByRole('alert')).toHaveTextContent('Fill in the required fields to continue.');

		await fireEvent.click(screen.getByLabelText('About one hour a week'));
		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));

		expect(step(2)).not.toHaveAttribute('hidden');
		expect(step(1)).toHaveAttribute('hidden');
		expect(screen.getByText('Step 2 of 3')).toBeInTheDocument();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('moves focus to the new step heading', async () => {
		renderWith(RegistrationForm, { registration: open });
		await fireEvent.click(screen.getByLabelText('About one hour a week'));

		await fireEvent.click(screen.getByRole('button', { name: 'Next' }));
		await tick();

		expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Your level' }));
	});

	it('goes back freely and a new player cannot jump ahead', async () => {
		renderWith(RegistrationForm, { registration: open });

		expect(within(stepsNav()).getByRole('button', { name: 'Your level' })).toBeDisabled();
		expect(within(stepsNav()).getByRole('button', { name: 'Additional requests' })).toBeDisabled();

		await toStep(2);
		await fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
		expect(step(1)).not.toHaveAttribute('hidden');

		await fireEvent.click(within(stepsNav()).getByRole('button', { name: 'Your level' }));
		expect(step(2)).not.toHaveAttribute('hidden');
	});

	it('lets a registered player jump to any step', async () => {
		renderWith(RegistrationForm, { registration: registered });

		await fireEvent.click(within(stepsNav()).getByRole('button', { name: 'Additional requests' }));

		expect(step(3)).not.toHaveAttribute('hidden');
		expect(screen.getByRole('button', { name: 'Save my answers' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Withdraw my registration' })).toBeInTheDocument();
	});

	it('gates step 3 on the tick, and on an email when one is asked', async () => {
		renderWith(RegistrationForm, { registration: { ...open, email: { value: '', editable: true } } });
		await toStep(3);

		expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: 'Next' })).toBeNull();
		expect(screen.getByRole('textbox', { name: 'Email address' })).toBeRequired();
		expect(screen.getByRole('checkbox')).toBeRequired();
	});

	it.each([
		[['register.error.missing_frequency'], 1],
		[['register.error.invalid_rating'], 2],
		[['register.error.too_long'], 3]
	])('opens on the step of the first error %j, keeping the whole list above', (errors, n) => {
		renderWith(RegistrationForm, {
			registration: open,
			form: { action: 'save', errors, values: initialValues(open) }
		});

		expect(step(n)).not.toHaveAttribute('hidden');
		expect(screen.getByText(`Step ${n} of 3`)).toBeInTheDocument();
		expect(screen.getByRole('alert')).toBeInTheDocument();
		// after a refusal every step is reachable again
		expect(within(stepsNav()).getByRole('button', { name: 'Additional requests' })).toBeEnabled();
	});

	it('shows the notices above the progress, on every step', async () => {
		renderWith(RegistrationForm, { registration: registered, form: { action: 'save', ok: true } });
		const status = screen.getByRole('status');

		expect(status.compareDocumentPosition(stepsNav()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		await fireEvent.click(within(stepsNav()).getByRole('button', { name: 'Additional requests' }));
		expect(screen.getByRole('status')).toBeInTheDocument();
	});

	it('keeps the intro on step 1 only', () => {
		renderWith(RegistrationForm, { registration: open });

		expect(step(1)).toContainElement(screen.getByText('Welcome to registration'));
	});
});

describe('RegistrationForm sliders', () => {
	it('starts every slider at 5, shows its value and submits it', () => {
		renderWith(RegistrationForm, { registration: { ...open, registration: null, suggested: null } });

		const cardio = screen.getByLabelText('Cardio');
		expect(cardio).toHaveAttribute('type', 'range');
		expect(cardio).toHaveAttribute('min', '1');
		expect(cardio).toHaveAttribute('max', '10');
		expect(cardio).toHaveAttribute('step', '1');
		expect(cardio).toHaveValue('5');
		expect(document.getElementById('rating-CARD-value')).toHaveTextContent('5');
		expect(cardio).toHaveAttribute('aria-describedby', 'rating-CARD-value');
		const global = screen.getByLabelText('Overall level');
		expect(global).toHaveAttribute('type', 'range');
		expect(global).toHaveValue('5');
	});

	it('shows the value the player moves it to', async () => {
		renderWith(RegistrationForm, { registration: open });

		await fireEvent.input(screen.getByLabelText('Cardio'), { target: { value: '8' } });

		expect(document.getElementById('rating-CARD-value')).toHaveTextContent('8');
		expect(screen.getByLabelText('Cardio')).toHaveValue('8');
	});

	it('shows the saved ratings, not the default', () => {
		renderWith(RegistrationForm, { registration: registered });

		expect(screen.getByLabelText('Cardio')).toHaveValue(String(savedAnswers.ratings.CARD));
	});
});

describe('RegistrationForm team preferences', () => {
	it('has two fields, tied to their hints, and no legacy field', () => {
		renderWith(RegistrationForm, { registration: open });

		const withField = screen.getByLabelText('Who would you like to be with?');
		const avoidField = screen.getByLabelText('Who would you rather not be with?');
		expect(withField).toHaveAttribute('name', 'team_with');
		expect(avoidField).toHaveAttribute('name', 'team_avoid');
		expect(withField).toHaveAttribute('aria-describedby', 'team-with-hint');
		expect(avoidField).toHaveAttribute('aria-describedby', 'team-avoid-hint');
		expect(document.querySelector('[name="team_wishes"]')).toBeNull();
	});

	it('fills them from the saved answers', () => {
		renderWith(RegistrationForm, { registration: registered });
		expect(screen.getByLabelText('Who would you like to be with?')).toHaveValue('Avec Bob');
		expect(screen.getByLabelText('Who would you rather not be with?')).toHaveValue('Pas Carl');
	});

	it('shows both in the read-only summary once registration is closed', () => {
		renderWith(RegistrationForm, { registration: { ...registered, state: { is_open: false, reason: 'closed' } } });

		expect(screen.getByText('With')).toBeInTheDocument();
		expect(screen.getByText('Avec Bob')).toBeInTheDocument();
		expect(screen.getByText('To avoid')).toBeInTheDocument();
		expect(screen.getByText('Pas Carl')).toBeInTheDocument();
	});

	it('speaks French', () => {
		renderWith(RegistrationForm, { registration: open }, 'fr');

		expect(screen.getByText('Étape 1 sur 3')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Votre pratique sportive' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Suivant' })).toBeInTheDocument();
	});
});
