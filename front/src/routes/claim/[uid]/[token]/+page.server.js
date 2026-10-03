import { linkAction, linkLoad, linkPath } from '$lib/server/password-link';

/** The API path of the claim link, or null for a link not shaped like one. */
const claimPath = linkPath('/claim');

export const load = linkLoad(claimPath);

export const actions = {
	/** Set the chosen password and log the person in, landing on their profile when the API names them. */
	claim: linkAction(claimPath, ({ user_id }) =>
		Number.isInteger(user_id) && user_id > 0 ? `/players/${user_id}` : '/'
	)
};
