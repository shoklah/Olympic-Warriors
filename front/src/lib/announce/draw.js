import { initials } from '$lib/avatar.js';
import { fontString } from './layout.js';
import { PALETTE } from './palette.js';

/** A rounded rectangle path (the context's own roundRect is not everywhere yet). */
function roundedRect(ctx, x, y, w, h, r) {
	const radius = Math.min(r, w / 2, h / 2);
	ctx.beginPath();
	ctx.moveTo(x + radius, y);
	ctx.arcTo(x + w, y, x + w, y + h, radius);
	ctx.arcTo(x + w, y + h, x, y + h, radius);
	ctx.arcTo(x, y + h, x, y, radius);
	ctx.arcTo(x, y, x + w, y, radius);
	ctx.closePath();
}

function drawRect(ctx, item) {
	if (item.radius) roundedRect(ctx, item.x, item.y, item.w, item.h, item.radius);
	else {
		ctx.beginPath();
		ctx.rect(item.x, item.y, item.w, item.h);
	}
	ctx.fillStyle = PALETTE[item.fill];
	ctx.fill();
	if (item.stroke) {
		ctx.strokeStyle = PALETTE[item.stroke];
		ctx.lineWidth = 2;
		ctx.stroke();
	}
}

function drawText(ctx, item) {
	ctx.font = fontString(item);
	ctx.fillStyle = PALETTE[item.color];
	ctx.textAlign = item.align ?? 'left';
	ctx.textBaseline = item.baseline ?? 'alphabetic';
	ctx.fillText(item.text, item.x, item.y);
}

/** A player's round: the photo clipped to a circle, else their initials on a plain round. */
function drawAvatar(ctx, item, images) {
	const { x, y, size, player } = item;
	const cx = x + size / 2;
	const cy = y + size / 2;
	const photo = player.photo ? images.get(player.photo) : null;
	if (photo) {
		ctx.save();
		ctx.beginPath();
		ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
		ctx.clip();
		ctx.drawImage(photo, x, y, size, size);
		ctx.restore();
	} else {
		ctx.beginPath();
		ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
		ctx.fillStyle = PALETTE.sunken;
		ctx.fill();
		ctx.font = fontString({ family: 'body', weight: 700, size: Math.round(size * 0.38) });
		ctx.fillStyle = PALETTE.muted;
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(initials(player.first_name, player.last_name), cx, cy);
	}
	ctx.beginPath();
	ctx.arc(cx, cy, size / 2 - 1, 0, Math.PI * 2);
	ctx.strokeStyle = PALETTE.line;
	ctx.lineWidth = 2;
	ctx.stroke();
}

/**
 * Paint a layout (`layout.js`) onto a 2D context. `images` maps `'logo'`, `'title'` and the
 * photo URLs to loaded images; a missing one is simply skipped (initials for a player).
 */
export function drawLayout(ctx, layout, { images }) {
	for (const item of layout.items) {
		if (item.type === 'rect') drawRect(ctx, item);
		else if (item.type === 'text') drawText(ctx, item);
		else if (item.type === 'avatar') drawAvatar(ctx, item, images);
		else {
			const image = images.get(item.type);
			if (image) ctx.drawImage(image, item.x, item.y, item.w, item.h);
		}
	}
}
