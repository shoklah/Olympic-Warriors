import { localeFrom } from '$lib/i18n/locale.js';

/** `<html lang>` follows the `lang` cookie; the root layout reads the same cookie for the pages. */
export const handle = async ({ event, resolve }) => {
	const locale = localeFrom(event.cookies.get('lang'));
	// The same URL renders differently per cookie: keep shared caches from cross-serving languages.
	event.setHeaders({ vary: 'Cookie' });
	return resolve(event, { transformPageChunk: ({ html }) => html.replace('%lang%', locale) });
};
