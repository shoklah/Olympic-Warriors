import { localeFrom } from '$lib/i18n/locale.js';
import { THEME_COOKIE, themeFrom } from '$lib/theme';

/**
 * `<html lang>` follows the `lang` cookie, which the root layout reads for the pages too;
 * `<html data-theme>` follows the `theme` cookie (`system` without one), which styles.css reads.
 */
export const handle = async ({ event, resolve }) => {
	const locale = localeFrom(event.cookies.get('lang'));
	const theme = themeFrom(event.cookies.get(THEME_COOKIE));
	// The same URL renders differently per cookie: keep shared caches from cross-serving languages.
	event.setHeaders({ vary: 'Cookie' });
	return resolve(event, {
		transformPageChunk: ({ html }) => html.replace('%lang%', locale).replace('%theme%', theme)
	});
};
