/**
 * Discipline name to icon URL. Every SVG in ./img/icons is bundled; the file stem is
 * the slug of the discipline name ("Hide and Seek" -> hideandseek.svg).
 */
const files = import.meta.glob('./img/icons/*.svg', { eager: true, query: '?url', import: 'default' });

const icons = Object.fromEntries(
	Object.entries(files).map(([path, url]) => [path.slice('./img/icons/'.length, -'.svg'.length), url])
);

export function iconSlug(name) {
	return name.toLowerCase().replace(/[\s']/g, '');
}

export function iconFor(name) {
	return icons[iconSlug(name)] ?? icons.default;
}
