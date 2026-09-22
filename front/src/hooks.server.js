import { localeFrom } from '$lib/i18n/locale.js';

/** `<html lang>` follows the `lang` cookie; the root layout reads the same cookie for the pages. */
export const handle = async ({ event, resolve }) => {
	const locale = localeFrom(event.cookies.get('lang'));
	return resolve(event, { transformPageChunk: ({ html }) => html.replace('%lang%', locale) });
};
