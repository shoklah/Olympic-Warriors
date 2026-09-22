/** Four digits, so "/login" and "/ranking" never match the [year] route. */
export function match(param) {
	return /^\d{4}$/.test(param);
}
