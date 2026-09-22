import { API_URL } from '$env/static/private';

/** Absolute API URL for a path such as "/editions/". */
export const api = (path) => `${API_URL}${path}`;
