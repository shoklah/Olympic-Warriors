import { apiGet } from '$lib/api';
import { linkAction, linkLoad, linkPath } from '$lib/server/password-link';
import { api } from '$lib/server/urls';

/** The API path of the claim link, or null for a link not shaped like one. */
const claimPath = linkPath('/claim');

export const load = linkLoad(claimPath);

export const actions = {
	/**
	 * Set the chosen password and log the person in. A person lands on their profile, an
	 * invited newcomer (no profile yet) on the registration, found by asking /me/ with the
	 * fresh token; if that fails, the profile when the API named the person, else home.
	 */
	claim: linkAction(claimPath, async ({ user_id }, { fetch, token }) => {
		const profile = Number.isInteger(user_id) && user_id > 0 ? `/players/${user_id}` : '/';
		try {
			const me = await apiGet(fetch, api('/me/'), token);
			if (me?.is_person !== true && me?.can_register === true) return '/register';
		} catch {
			// Unreadable: land as before.
		}
		return profile;
	})
};
