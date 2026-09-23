import { fail } from '@sveltejs/kit';
import { apiPatch } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/** The dictionary key the page shows for an API status; anything else is a plain failure. */
const ERROR_KEYS = {
	400: 'orga.error.invalid',
	401: 'orga.error.unauthorised',
	403: 'orga.error.forbidden',
	409: 'orga.error.conflict'
};

/**
 * One organiser write: the token cookie, one PATCH, and either {ok} or a fail() carrying
 * the action and row so the page can show the line under the right control.
 */
async function patch({ cookies, fetch }, action, id, path, body) {
	const token = cookies.get(TOKEN_COOKIE);
	if (!token) return fail(401, { action, id, error: ERROR_KEYS[401] });
	try {
		await apiPatch(fetch, api(path), body, token);
		return { ok: true, action, id };
	} catch (err) {
		const status = Number.isInteger(err?.status) && err.status >= 400 && err.status <= 599 ? err.status : 500;
		return fail(status, { action, id, error: ERROR_KEYS[status] ?? 'orga.error.failed' });
	}
}

const id = (form, name) => Number(form.get(name));

export const actions = {
	score: async (event) => {
		const form = await event.request.formData();
		const game = id(form, 'game');
		const score1 = Number(form.get('score1'));
		const score2 = Number(form.get('score2'));
		if (!Number.isInteger(score1) || !Number.isInteger(score2) || score1 < 0 || score2 < 0) {
			return fail(400, { action: 'score', id: game, error: ERROR_KEYS[400] });
		}
		return patch(event, 'score', game, `/game/${game}/score/`, {
			score1,
			score2,
			is_played: form.get('is_played') === 'on'
		});
	},

	result: async (event) => {
		const form = await event.request.formData();
		const result = id(form, 'result');
		const raw = String(form.get('value') ?? '').trim();
		let body;
		if (form.get('kind') === 'TIM') {
			body = { time: raw === '' ? null : raw };
		} else {
			const points = raw === '' ? null : Number(raw);
			if (points !== null && (!Number.isInteger(points) || points < 0)) {
				return fail(400, { action: 'result', id: result, error: ERROR_KEYS[400] });
			}
			body = { points };
		}
		return patch(event, 'result', result, `/result/${result}/value/`, body);
	},

	reveal: async (event) => {
		const form = await event.request.formData();
		const discipline = id(form, 'discipline');
		return patch(event, 'reveal', discipline, `/discipline/${discipline}/reveal/`, {
			reveal_score: form.get('reveal_score') === 'true'
		});
	},

	close: async (event) => {
		const form = await event.request.formData();
		const round = id(form, 'round');
		return patch(event, 'close', round, `/round/${round}/close/`, {});
	}
};
