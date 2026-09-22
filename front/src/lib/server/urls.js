import { API_URL } from '$env/static/private';

if (!API_URL) {
	// Under Vite dev a missing variable is silently undefined; fail loudly instead of
	// fetching "undefined/..." relative to the app.
	throw new Error('API_URL is not set: copy front/.env.example to front/.env');
}

/** Absolute API URL for a path such as "/editions/". */
export const api = (path) => `${API_URL}${path}`;
