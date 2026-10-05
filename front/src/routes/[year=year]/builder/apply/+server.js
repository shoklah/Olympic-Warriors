import { forward } from '$lib/server/builder-proxy';

export const POST = (event) => forward(event, 'POST', '/apply/', true);
