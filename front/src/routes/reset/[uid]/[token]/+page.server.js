import { linkAction, linkLoad, linkPath } from '$lib/server/password-link';

/** The API path of the reset link, or null for a link not shaped like one. */
const resetPath = linkPath('/password-reset');

export const load = linkLoad(resetPath);

export const actions = {
	/** Set the chosen password and log the person in, landing on the home page. */
	reset: linkAction(resetPath, () => '/')
};
