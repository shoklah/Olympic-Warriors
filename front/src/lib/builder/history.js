/**
 * The builder's undo and redo (spec 2026-10-06-builder-undo-redo): snapshots of the whole draft,
 * in memory for the page visit. Pure and immutable. A snapshot is a draft the page already
 * holds, so nothing is copied.
 */

/** Most undo steps kept; the oldest go first. */
export const LIMIT = 50;

export const emptyHistory = () => ({ past: [], future: [], key: null });

/**
 * `draft` is about to be replaced by a new one: remember it, and forget any redo. Edits that
 * share a `key` (the team-size field, one commit per keystroke) make a single step: only the
 * first remembers the draft it replaced.
 */
export function record(history, draft, key = null) {
	if (key !== null && history.key === key) return { ...history, future: [], key };
	return { past: [...history.past, draft].slice(-LIMIT), future: [], key };
}

/** One step back from `current`, or null when there is none. */
export function undo(history, current) {
	if (history.past.length === 0) return null;
	const draft = history.past[history.past.length - 1];
	return { draft, history: { past: history.past.slice(0, -1), future: [...history.future, current], key: null } };
}

/** One step forward from `current`, or null when there is none. */
export function redo(history, current) {
	if (history.future.length === 0) return null;
	const draft = history.future[history.future.length - 1];
	return { draft, history: { past: [...history.past, current], future: history.future.slice(0, -1), key: null } };
}
