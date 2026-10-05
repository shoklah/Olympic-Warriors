/**
 * The team sizes for `n` players at about `perTeam` each: `ceil(n / perTeam)` teams, as even
 * as possible (sizes differ by at most one, the larger first). null when that is under two teams.
 */
export function teamSizes(n, perTeam) {
	const count = Math.ceil(n / perTeam);
	if (!Number.isFinite(count) || count < 2 || n < count) return null;
	const base = Math.floor(n / count);
	const extra = n % count;
	return Array.from({ length: count }, (_, i) => (i < extra ? base + 1 : base));
}
