import { error, fail } from '@sveltejs/kit';
import { apiGet, apiSend } from '$lib/api';
import { api } from '$lib/server/urls';
import { TOKEN_COOKIE } from '$lib/session';

/**
 * One person's profile by user id. Only a canonical decimal integer reaches the API: the id
 * is spliced into an API path, a decoded `..` could otherwise walk to another endpoint, a
 * leading zero would give the same player two URLs (`/players/0055` and `/players/55`), and
 * the digit run is capped so an absurdly long string is refused up front. The API's 404
 * (unknown id, or a user who never played) becomes the error page through apiGet.
 */
export const load = async ({ fetch, params }) => {
	if (!/^[1-9]\d{0,9}$/.test(params.id)) error(404, 'No such player');
	return { profile: await apiGet(fetch, api(`/profile/${params.id}/`)) };
};

const FORBIDDEN = 'photo.error.forbidden';
const FAILED = 'photo.error.failed';

/** The API's photo refusal codes (spec §5), each worded as `photo.error.<code>`. */
const PHOTO_CODES = new Set(['missing', 'too_large', 'bad_format', 'too_many_pixels', 'photo_locked']);

/** A failed call's status when fail() can carry it, else 500. */
const statusOf = (err) =>
	Number.isInteger(err?.status) && err.status >= 400 && err.status <= 599 ? err.status : 500;

/**
 * The dictionary key for a failed photo call. nginx refuses an oversized body (413) before
 * Django answers, with an HTML page and no code, and the throttle (429) carries DRF's
 * English detail, so both go by status. apiSend puts the API's `{"error": code}` in the
 * message; anything else (a 404 for someone who is not a person, an outage) is a plain
 * failure.
 */
function photoError(err) {
	const status = statusOf(err);
	if (status === 413) return 'photo.error.too_large';
	if (status === 429) return 'photo.error.throttled';
	const code = err?.body?.message;
	return PHOTO_CODES.has(code) ? `photo.error.${code}` : FAILED;
}

/**
 * Run `send()` as `action` when this page is the profile of the token's owner: `/me/` must
 * be this page's id, compared as the canonical string, so `/players/034` is nobody's. The
 * API's `/me/photo/` only ever touches the caller's own photo, whatever page posts: the check
 * keeps an upload from someone else's profile page from landing on the visitor's own.
 * Returns `{ok, action}` or a fail() with a dictionary key.
 */
async function onOwnPhoto({ fetch, params }, action, token, send) {
	let me;
	try {
		me = await apiGet(fetch, api('/me/'), token);
	} catch (err) {
		const status = statusOf(err);
		// A dead token: the next load drops the cookie, and the camera button with it.
		if (status === 401 || status === 403) return fail(403, { action, error: FORBIDDEN });
		return fail(status, { action, error: FAILED });
	}
	if (!Number.isInteger(me?.id) || String(me.id) !== params.id) return fail(403, { action, error: FORBIDDEN });

	try {
		await send();
	} catch (err) {
		return fail(statusOf(err), { action, error: photoError(err) });
	}
	return { ok: true, action };
}

/** The form's `photo` file, or null for no form, no file, an empty one or a text field. */
function photoIn(form) {
	const file = form?.get('photo') ?? null;
	return file === null || typeof file === 'string' || file.size === 0 ? null : file;
}

export const actions = {
	/**
	 * A new photo, cropped and shrunk by the page's editor, forwarded as multipart to
	 * `PUT /me/photo/`, which validates and re-encodes it. A form without a file is refused
	 * before any API call.
	 */
	photo: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'photo', error: FORBIDDEN });
		let form = null;
		try {
			form = await event.request.formData();
		} catch (err) {
			// adapter-node stops reading a body past BODY_SIZE_LIMIT with a 413 error.
			if (err?.status === 413) return fail(413, { action: 'photo', error: 'photo.error.too_large' });
			// Anything else is not a form body at all: nothing was sent.
		}
		const file = photoIn(form);
		if (!file) return fail(400, { action: 'photo', error: 'photo.error.missing' });
		return onOwnPhoto(event, 'photo', token, () => {
			const body = new FormData();
			body.append('photo', file, file.name || 'photo.jpg');
			return apiSend(event.fetch, api('/me/photo/'), { method: 'PUT', token, body });
		});
	},

	/** Take the caller's photo down; the API allows it even when uploads are locked. */
	removePhoto: async (event) => {
		const token = event.cookies.get(TOKEN_COOKIE);
		if (!token) return fail(403, { action: 'removePhoto', error: FORBIDDEN });
		return onOwnPhoto(event, 'removePhoto', token, () =>
			apiSend(event.fetch, api('/me/photo/'), { method: 'DELETE', token })
		);
	}
};
