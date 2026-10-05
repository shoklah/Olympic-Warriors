const DELAY = 800;

/**
 * Saves the builder's draft to the page's own endpoint, debounced, each save based on the
 * version the last one returned. A 409 hands the stored draft to `onStale` and stops saving
 * until the page loads that draft (a new saver); any other failure goes to `onError` and the
 * next change tries again.
 */
export function createSaver({ url, fetch = globalThis.fetch, based_on = null, onSaved, onStale, onError }) {
	let version = based_on;
	let timer = null;
	let pending = null;
	let stopped = false;

	let inflight = Promise.resolve();

	// The document and the version are read when the previous request is done, so each PUT
	// is based on the version the one before returned.
	async function request() {
		if (pending === null || stopped) return;
		const document = pending;
		pending = null;
		try {
			const response = await fetch(url, {
				method: 'PUT',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ document, based_on: version })
			});
			const body = await response.json().catch(() => ({}));
			if (response.status === 409) {
				stopped = true;
				onStale?.(body.draft ?? null);
			} else if (response.ok) {
				version = body.updated_at;
				onSaved?.(version);
			} else {
				if (pending === null) pending = document;
				onError?.(response.status);
			}
		} catch {
			if (pending === null) pending = document;
			onError?.(0);
		}
	}

	function send() {
		inflight = inflight.then(request);
		return inflight;
	}

	return {
		version: () => version,
		save(document) {
			pending = document;
			clearTimeout(timer);
			timer = setTimeout(send, DELAY);
		},
		async flush() {
			clearTimeout(timer);
			await send();
		},
		/** Whether a change newer than the request being answered waits to be sent. */
		pending: () => pending !== null
	};
}
