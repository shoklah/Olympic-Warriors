/** The two languages the site speaks. French is the default and the reference file. */
export const LOCALES = ['fr', 'en'];
export const DEFAULT_LOCALE = 'fr';

/** A known locale, or the default for anything else (a missing or foreign cookie). */
export const localeFrom = (value) => (LOCALES.includes(value) ? value : DEFAULT_LOCALE);
