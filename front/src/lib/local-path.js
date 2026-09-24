/**
 * Where a header form (language, theme, logout) sends the visitor back: only a path on
 * this site, one leading slash, so `//host`, `/\host` (which browsers read as
 * scheme-relative), absolute URLs and control characters go home.
 */
export const localPath = (value) =>
	typeof value === 'string' && /^\/(?![/\\])[^\s\x00-\x1f\x7f]*$/.test(value) ? value : '/';
