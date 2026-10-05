import { forward } from '$lib/server/builder-proxy';

export const PUT = (event) => forward(event, 'PUT', '/draft/', true);
export const DELETE = (event) => forward(event, 'DELETE', '/draft/');
