import { describe, expect, it } from 'vitest';
import {
	bodyFromValues,
	choiceLabel,
	durationParts,
	emptySport,
	errorKeys,
	initialValues,
	listNames,
	monthsOf,
	parisToday,
	registrationLink,
	valuesFromForm,
	visitorCta
} from './registration.js';
import { registrationPayload, savedAnswers } from './fixtures/registration.js';

const formOf = (entries) => {
	const form = new FormData();
	for (const [name, value] of entries) form.append(name, value);
	return form;
};

describe('durations', () => {
	it('splits months into years and months', () => {
		expect(durationParts(30)).toEqual({ years: '2', months: '6' });
		expect(durationParts(0)).toEqual({ years: '0', months: '0' });
		expect(durationParts(null)).toEqual({ years: '', months: '' });
	});

	it('joins years and months, null when both are blank', () => {
		expect(monthsOf('2', '6')).toBe(30);
		expect(monthsOf('', '8')).toBe(8);
		expect(monthsOf('3', '')).toBe(36);
		expect(monthsOf('', '')).toBeNull();
	});

	it('hands the API a value it refuses rather than hiding a bad one', () => {
		expect(monthsOf('-1', '')).toBeLessThan(0);
		expect(monthsOf('1.5', '')).toBeLessThan(0);
		expect(monthsOf('abc', '')).toBeLessThan(0);
	});
});

describe('initialValues', () => {
	it('starts blank, with one empty sports row', () => {
		const values = initialValues(registrationPayload);

		expect(values.ratings).toEqual({ CARD: '', STR: '' });
		expect(values.global_level).toBe('');
		expect(values.sports).toEqual([emptySport()]);
		expect(values.attendance_confirmed).toBe(false);
		expect(values.email).toBe('');
	});

	it('fills from the saved answers', () => {
		const values = initialValues({ ...registrationPayload, registration: savedAnswers });

		expect(values.ratings).toEqual({ CARD: '6', STR: '7' });
		expect(values.global_level).toBe('8');
		expect(values.sport_frequency).toBe('two_hours');
		expect(values.sports).toEqual([
			{ sport: 'Judo', level: 'amateur', practice: 'no_longer', years: '2', months: '6', notes: 'Ceinture orange' }
		]);
		expect(values.team_wishes).toBe('Avec Bob');
		expect(values.attendance_confirmed).toBe(true);
	});

	it('offers only the stable suggested answers to someone who has not registered', () => {
		const payload = {
			...registrationPayload,
			suggested: {
				year: 2026,
				sport_frequency: 'hour',
				dietary_restrictions: 'Sans gluten',
				sports: [{ sport: 'Tennis', level: '', practice: '', duration_months: null, notes: '30/1' }]
			}
		};

		const values = initialValues(payload);

		expect(values.sport_frequency).toBe('hour');
		expect(values.dietary_restrictions).toBe('Sans gluten');
		expect(values.sports[0]).toMatchObject({ sport: 'Tennis', notes: '30/1', years: '', months: '' });
		expect(values.ratings).toEqual({ CARD: '', STR: '' });
		expect(values.team_wishes).toBe('');
		expect(values.attendance_confirmed).toBe(false);
	});

	it('keeps one blank sports row after a refusal that posted none', () => {
		const posted = { ...initialValues(registrationPayload), sports: [] };

		expect(initialValues(registrationPayload, posted).sports).toEqual([emptySport()]);
	});

	it('prefers what was posted (a refused save) over everything', () => {
		const posted = { ...initialValues(registrationPayload), global_level: '99', team_wishes: 'typed' };

		const values = initialValues({ ...registrationPayload, registration: savedAnswers }, posted);

		expect(values.global_level).toBe('99');
		expect(values.team_wishes).toBe('typed');
	});
});

describe('valuesFromForm and bodyFromValues', () => {
	const entries = [
		['skill', 'CARD'],
		['skill', 'STR'],
		['rating.CARD', '6'],
		['rating.STR', '7'],
		['global_level', '8'],
		['sport_frequency', 'two_hours'],
		['sport.0.sport', ' Judo '],
		['sport.0.level', 'amateur'],
		['sport.0.practice', 'no_longer'],
		['sport.0.years', '2'],
		['sport.0.months', '6'],
		['sport.0.notes', 'Ceinture orange'],
		['sport.1.sport', ''],
		['sport.1.level', ''],
		['sport.1.practice', ''],
		['sport.1.years', ''],
		['sport.1.months', ''],
		['sport.1.notes', ''],
		['team_wishes', 'Avec Bob'],
		['dietary_restrictions', ''],
		['attendance_confirmed', 'on']
	];

	it('reads the posted form back into the form model, dropping blank sports rows', () => {
		const values = valuesFromForm(formOf(entries));

		expect(values.ratings).toEqual({ CARD: '6', STR: '7' });
		expect(values.sports).toEqual([
			{ sport: ' Judo ', level: 'amateur', practice: 'no_longer', years: '2', months: '6', notes: 'Ceinture orange' }
		]);
		expect(values.attendance_confirmed).toBe(true);
		expect(values.email).toBe('');
	});

	it('orders sports rows by their index, whatever the order they were posted in', () => {
		const values = valuesFromForm(
			formOf([['sport.10.sport', 'B'], ['sport.2.sport', 'A'], ['skill', 'CARD']])
		);

		expect(values.sports.map((s) => s.sport)).toEqual(['A', 'B']);
	});

	it('builds the API body', () => {
		const body = bodyFromValues(valuesFromForm(formOf(entries)), false);

		expect(body).toEqual({
			ratings: { CARD: 6, STR: 7 },
			global_level: 8,
			sport_frequency: 'two_hours',
			sports: [
				{ sport: 'Judo', level: 'amateur', practice: 'no_longer', duration_months: 30, notes: 'Ceinture orange' }
			],
			team_wishes: 'Avec Bob',
			dietary_restrictions: '',
			attendance_confirmed: true
		});
	});

	it('sends the email only when the form asked for one', () => {
		const values = { ...valuesFromForm(formOf(entries)), email: ' New@Example.com ' };

		expect(bodyFromValues(values, false)).not.toHaveProperty('email');
		expect(bodyFromValues(values, true).email).toBe('New@Example.com');
	});

	it('leaves a blank rating out and passes a bad one on for the API to refuse', () => {
		const values = valuesFromForm(formOf([['skill', 'CARD'], ['skill', 'STR'], ['rating.CARD', ''], ['rating.STR', 'x'], ['global_level', '']]));

		const body = bodyFromValues(values, false);

		expect(body.ratings).toEqual({ STR: 'x' });
		expect(body.global_level).toBeNull();
	});
});

describe('errorKeys', () => {
	it('words the API codes, once each, in order', () => {
		expect(errorKeys(['missing_rating', 'attendance_required', 'missing_rating'])).toEqual([
			'register.error.missing_rating',
			'register.error.attendance_required'
		]);
	});

	it('reads a code it does not know as one generic refusal', () => {
		expect(errorKeys(['brand_new'])).toEqual(['register.error.invalid']);
		expect(errorKeys([])).toEqual(['register.error.invalid']);
	});
});

describe('choiceLabel', () => {
	const t = (key) => ({ 'register.level.club': 'Club (club)' })[key] ?? key;

	it('uses the dictionary, then the API label for a value the front does not know', () => {
		expect(choiceLabel(t, 'level', { value: 'club', label: 'Club' })).toBe('Club (club)');
		expect(choiceLabel(t, 'level', { value: 'olympic', label: 'Olympique' })).toBe('Olympique');
	});
});

describe('listNames', () => {
	it('joins names with the locale conjunction', () => {
		expect(listNames('en', ['Relay', 'Darts', 'Hide and Seek'])).toBe('Relay, Darts, and Hide and Seek');
		expect(listNames('fr', ['Relais', 'Fléchettes'])).toBe('Relais et Fléchettes');
		expect(listNames('en', [])).toBe('');
	});
});

describe('the registration link', () => {
	const editions = [
		{ year: 2027, start_date: '2027-09-18', registration_opens: '2027-05-01', registration_closes: null },
		{ year: 2026, start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null }
	];

	it('sends a visitor through the login while the public window is open', () => {
		expect(registrationLink({ me: null, editions, today: '2027-06-01' })).toEqual({
			href: '/login?next=/register', year: 2027, visitor: true
		});
	});

	it('links someone who can register straight to the form', () => {
		const me = { id: 1, can_register: true };

		expect(registrationLink({ me, editions, today: '2027-06-01' })).toEqual({
			href: '/register', year: 2027, visitor: false
		});
	});

	it('is nothing for someone who cannot register, outside the window, or with no edition', () => {
		expect(registrationLink({ me: { id: 1, can_register: false }, editions, today: '2027-06-01' })).toBeNull();
		expect(registrationLink({ me: null, editions, today: '2027-04-01' })).toBeNull();
		expect(registrationLink({ me: null, editions: [], today: '2027-06-01' })).toBeNull();
		expect(registrationLink({ me: null, editions: undefined, today: '2027-06-01' })).toBeNull();
	});

	it('only ever concerns the latest edition', () => {
		const old = [{ year: 2026, start_date: '2026-09-19', registration_opens: '2026-01-01', registration_closes: null }];

		expect(registrationLink({ me: null, editions: old, today: '2026-06-01' }).year).toBe(2026);
		expect(registrationLink({ me: null, editions: [...editions].reverse(), today: '2027-06-01' })).toBeNull();
	});
});

describe('visitorCta', () => {
	it('is the public window: opening day reached, closing day (or the day before the start) not passed', () => {
		const edition = { start_date: '2027-09-18', registration_opens: '2027-05-01', registration_closes: null };

		expect(visitorCta(edition, '2027-04-30')).toBe(false);
		expect(visitorCta(edition, '2027-05-01')).toBe(true);
		expect(visitorCta(edition, '2027-09-17')).toBe(true); // the day before the start
		expect(visitorCta(edition, '2027-09-18')).toBe(false);
		expect(visitorCta({ ...edition, registration_closes: '2027-06-30' }, '2027-06-30')).toBe(true);
		expect(visitorCta({ ...edition, registration_closes: '2027-06-30' }, '2027-07-01')).toBe(false);
		expect(visitorCta({ ...edition, registration_opens: null }, '2027-06-01')).toBe(false);
		expect(visitorCta(undefined, '2027-06-01')).toBe(false);
	});
});

describe('parisToday', () => {
	it('reads today in Paris', () => {
		expect(parisToday(new Date('2027-06-01T22:30:00Z'))).toBe('2027-06-02'); // already tomorrow there
		expect(parisToday(new Date('2027-01-15T10:00:00Z'))).toBe('2027-01-15');
	});
});
