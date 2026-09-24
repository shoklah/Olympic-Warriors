/**
 * The visitor's address for the API's per-IP throttles (the login and the claim link count
 * attempts per client IP). This server calls the API itself, so without the header every
 * visitor would share its address. Behind nginx, adapter-node needs ADDRESS_HEADER to see
 * past the proxy, and throws when that header is missing from a request: the API then falls
 * back to this server's address.
 */
export function forwardedFor(getClientAddress) {
	try {
		const address = getClientAddress();
		return address ? { 'x-forwarded-for': address } : {};
	} catch {
		return {};
	}
}
