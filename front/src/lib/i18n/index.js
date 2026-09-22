import { getContext } from 'svelte';
import fr from './fr.js';
import en from './en.js';
import { FRENCH_NAMES } from './disciplines.js';
import { DEFAULT_LOCALE } from './locale.js';

/** Svelte context key under which the root layout stores the locale. */
export const I18N = 'i18n';

const MESSAGES = { fr, en };

const fill = (text, params) =>
	text.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));

/**
 * The message `key` in `locale`, placeholders filled from `params`. Falls back to the
 * French message, then to the key itself so a typo shows on the page. A counting
 * message ({ one, other }) is picked with the locale's plural rules on `params.n`.
 */
export function t(locale, key, params = {}) {
	const message = MESSAGES[locale]?.[key] ?? fr[key];
	if (message === undefined) return key;
	if (typeof message === 'string') return fill(message, params);
	const form = new Intl.PluralRules(locale in MESSAGES ? locale : DEFAULT_LOCALE).select(
		Number(params.n ?? 0)
	);
	return fill(message[form] ?? message.other, params);
}

/** `t` with the locale bound. */
export const translator = (locale) => (key, params) => t(locale, key, params);

/** The locale the root layout put in context; French outside any layout (tests). */
export const useLocale = () => getContext(I18N) ?? DEFAULT_LOCALE;

/** For a component's script: `const t = useT();` then `{t('nav.ranking')}`. */
export const useT = () => translator(useLocale());

/** French name of a discipline when the locale is French and the map knows it. */
export function disciplineName(locale, name) {
	return locale === 'fr' ? (FRENCH_NAMES[name] ?? name) : name;
}
