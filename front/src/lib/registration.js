/**
 * The registration form's model and rules, with no Svelte and no network (spec
 * 2026-10-04). The form model keeps every value as the string the browser posts, so a refused
 * save can hand exactly what was typed back to the page; `bodyFromValues` turns it into the
 * API's JSON.
 */

/** Sports the API accepts (enrolment.MAX_SPORTS). */
export const MAX_SPORTS = 15;

/** The slider's start, submitted as is when it is not touched. */
export const RATING_DEFAULT = 5;

/** An empty row of the sports table. */
export const emptySport = () => ({ sport: '', level: '', practice: '', years: '', months: '', notes: '' });

/** Months as the two fields a person fills: years and months, blank when unknown. */
export function durationParts(total) {
	if (total === null || total === undefined) return { years: '', months: '' };
	return { years: String(Math.floor(total / 12)), months: String(total % 12) };
}

/**
 * Years and months back to a number of months: null when both are blank. A value that is
 * not a whole non-negative number comes back negative, which the API refuses
 * (`invalid_sport`): a bad entry is reported, never silently dropped.
 */
export function monthsOf(years, months) {
	const y = String(years ?? '').trim();
	const m = String(months ?? '').trim();
	if (y === '' && m === '') return null;
	const whole = (s) => (s === '' ? 0 : /^\d+$/.test(s) ? Number(s) : NaN);
	const total = whole(y) * 12 + whole(m);
	return Number.isFinite(total) ? total : -1;
}

const text = (value) => (value === null || value === undefined ? '' : String(value));

const sportFrom = (row) => ({
	sport: text(row.sport),
	level: text(row.level),
	practice: text(row.practice),
	...durationParts(row.duration_months),
	notes: text(row.notes)
});

/**
 * The form model of a `GET /registration/` payload: what was posted last (`posted`, the
 * model a refused save returned), else the caller's saved answers, else the stable answers
 * suggested from their last registration (sports, frequency, dietary restrictions: never
 * the ratings, team preferences or the tick), else blanks. Always at least one sports row.
 */
export function initialValues(payload, posted = null) {
	if (posted) {
		const fallback = String(RATING_DEFAULT);
		return {
			...posted,
			ratings: Object.fromEntries(
				Object.entries(posted.ratings ?? {}).map(([id, value]) => [id, text(value).trim() === '' ? fallback : value])
			),
			global_level: text(posted.global_level).trim() === '' ? fallback : posted.global_level,
			sports: posted.sports?.length > 0 ? posted.sports : [emptySport()]
		};
	}
	const values = {
		ratings: Object.fromEntries(payload.skills.map((s) => [s.identifier, String(RATING_DEFAULT)])),
		global_level: String(RATING_DEFAULT),
		sport_frequency: '',
		sports: [],
		team_with: '',
		team_avoid: '',
		dietary_restrictions: '',
		attendance_confirmed: false,
		email: ''
	};
	const saved = payload.registration;
	const suggested = payload.suggested;
	if (saved) {
		for (const skill of payload.skills) {
			if (saved.ratings?.[skill.identifier] !== undefined) {
				values.ratings[skill.identifier] = String(saved.ratings[skill.identifier]);
			}
		}
		values.global_level = text(saved.global_level);
		values.sport_frequency = text(saved.sport_frequency);
		values.sports = (saved.sports ?? []).map(sportFrom);
		values.team_with = text(saved.team_with);
		values.team_avoid = text(saved.team_avoid);
		values.dietary_restrictions = text(saved.dietary_restrictions);
		values.attendance_confirmed = Boolean(saved.attendance_confirmed);
	} else if (suggested) {
		values.sport_frequency = text(suggested.sport_frequency);
		values.dietary_restrictions = text(suggested.dietary_restrictions);
		values.sports = (suggested.sports ?? []).map(sportFrom);
	}
	if (values.sports.length === 0) values.sports = [emptySport()];
	return values;
}

const SPORT_FIELD = /^sport\.(\d+)\.(sport|level|practice|years|months|notes)$/;

/**
 * The form model of a posted `FormData`: the skills listed in the hidden `skill` fields, the
 * sports rows by index (blank rows dropped), the tick as a boolean. Pure, so the server
 * action can return it to the page after a refusal.
 */
export function valuesFromForm(form) {
	const rows = new Map();
	for (const [name, value] of form.entries()) {
		const match = SPORT_FIELD.exec(name);
		if (!match) continue;
		const index = Number(match[1]);
		if (!rows.has(index)) rows.set(index, emptySport());
		rows.get(index)[match[2]] = String(value);
	}
	const sports = [...rows.entries()]
		.sort(([a], [b]) => a - b)
		.map(([, row]) => row)
		.filter((row) => Object.values(row).some((value) => value.trim() !== ''));
	return {
		ratings: Object.fromEntries(form.getAll('skill').map((id) => [id, text(form.get(`rating.${id}`))])),
		global_level: text(form.get('global_level')),
		sport_frequency: text(form.get('sport_frequency')),
		sports,
		team_with: text(form.get('team_with')),
		team_avoid: text(form.get('team_avoid')),
		dietary_restrictions: text(form.get('dietary_restrictions')),
		attendance_confirmed: form.get('attendance_confirmed') === 'on',
		email: text(form.get('email'))
	};
}

const WHOLE = /^-?\d+$/;

/** A number field as the API wants it: a whole number as a number, a blank as `blank`, anything else as typed (the API refuses it). */
const asNumber = (value, blank) => {
	const s = text(value).trim();
	if (s === '') return blank;
	return WHOLE.test(s) ? Number(s) : s;
};

/**
 * The `PUT /registration/` body of a form model. A blank rating is left out and a blank
 * global level sent as null, so the API reports them; nothing is corrected silently. The
 * email only goes when the form asked for one (the account had no usable address).
 */
export function bodyFromValues(values, emailEditable) {
	const ratings = {};
	for (const [id, value] of Object.entries(values.ratings)) {
		const rating = asNumber(value, undefined);
		if (rating !== undefined) ratings[id] = rating;
	}
	const body = {
		ratings,
		global_level: asNumber(values.global_level, null),
		sport_frequency: values.sport_frequency,
		sports: values.sports.map((row) => ({
			sport: row.sport.trim(),
			level: row.level,
			practice: row.practice,
			duration_months: monthsOf(row.years, row.months),
			notes: row.notes.trim()
		})),
		team_with: values.team_with,
		team_avoid: values.team_avoid,
		dietary_restrictions: values.dietary_restrictions,
		attendance_confirmed: values.attendance_confirmed
	};
	if (emailEditable) body.email = values.email.trim();
	return body;
}

const ERROR_CODES = new Set([
	'missing_rating', 'invalid_rating', 'invalid_global_level', 'missing_frequency',
	'invalid_frequency', 'invalid_sport', 'too_many_sports', 'too_long', 'invalid_text',
	'attendance_required', 'no_email', 'invalid_email', 'email_taken'
]);

/**
 * The dictionary keys for the API's validation codes, once each, in its order. A code this
 * page does not know (added on the server later), or none, reads as one generic refusal.
 */
export function errorKeys(codes) {
	const keys = (Array.isArray(codes) ? codes : []).map((code) =>
		ERROR_CODES.has(code) ? `register.error.${code}` : 'register.error.invalid'
	);
	return keys.length > 0 ? [...new Set(keys)] : ['register.error.invalid'];
}

const STEP_ONE = new Set(['missing_frequency', 'invalid_frequency', 'invalid_sport', 'too_many_sports']);
const STEP_TWO = new Set(['missing_rating', 'invalid_rating', 'invalid_global_level']);

/**
 * The wizard step (1 to 3) to open after a refusal: the step of the first API code, step 3
 * for every other code (texts, email, the tick, a closed or throttled form) and for none.
 */
export function stepOfErrors(codes) {
	const first = Array.isArray(codes) ? codes[0] : undefined;
	if (STEP_ONE.has(first)) return 1;
	if (STEP_TWO.has(first)) return 2;
	return 3;
}

/** The step a page opens on given the last post result: 1 unless a save or withdrawal was refused. */
export function stepOfForm(form) {
	if (!form || form.ok) return 1;
	if (form.action === 'withdraw') return 3;
	return stepOfErrors(form.errors ?? (form.error ? [form.error] : []));
}

/** The label of a choice: the dictionary's (`register.<kind>.<value>`), else the API's for a value the front does not know. */
export function choiceLabel(t, kind, choice) {
	const key = `register.${kind}.${choice.value}`;
	const label = t(key);
	return label === key ? choice.label : label;
}

/** Names joined with the locale's conjunction (`Relais, Fléchettes et Darts`). */
export function listNames(locale, names) {
	return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(names);
}

/** Today's date in Paris as `YYYY-MM-DD`: the event's calendar, whatever the renderer's timezone. */
export function parisToday(now = new Date()) {
	return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Paris' }).format(now);
}

const dayBefore = (iso) => {
	const date = new Date(`${iso}T00:00:00Z`);
	date.setUTCDate(date.getUTCDate() - 1);
	return date.toISOString().slice(0, 10);
};

/**
 * Whether a visitor, who cannot ask the API, is shown the way in: the public window is open
 * (opening day set and reached, not past `registration_closes`, or the day before the start
 * when blank). The API decides for real once they log in; this only avoids a dead end.
 */
export function visitorCta(edition, today) {
	if (!edition?.registration_opens || !edition.start_date) return false;
	const closes = edition.registration_closes ?? dayBefore(edition.start_date);
	return today >= edition.registration_opens && today <= closes;
}

/**
 * The registration link of the hub and of the account page, from the layout data alone
 * (no API call): `{ href, year, visitor }` while the latest edition's public window is open,
 * else null. A visitor goes through the login; someone logged in who can register goes
 * straight to the form, which shows whether they are registered and offers the edit.
 */
export function registrationLink({ me, editions, today }) {
	const latest = editions?.[0];
	if (!latest || !visitorCta(latest, today)) return null;
	if (!me) return { href: '/login?next=/register', year: latest.year, visitor: true };
	return me.can_register ? { href: '/register', year: latest.year, visitor: false } : null;
}
