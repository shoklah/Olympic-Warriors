/** The two themes a visitor can pick in the header; without a choice the device setting decides. */
export const THEMES = ['light', 'dark'];

/** Cookie holding the choice, set by the /theme action. */
export const THEME_COOKIE = 'theme';

/** A picked theme, or `system` for anything else (a missing or foreign cookie). */
export const themeFrom = (value) => (THEMES.includes(value) ? value : 'system');
