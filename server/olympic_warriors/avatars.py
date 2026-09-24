"""
Players' photos (see the player profile customization design spec under
docs/superpowers/specs/). store_photo() turns an upload into two WebP squares and
remove_photo() takes them down; both live here and not in UserProfile.save() because they
touch the filesystem, not business rules.

The browser crops and shrinks before uploading, but the server trusts none of it: it
checks the size, the format and the pixel count from the header before decoding anything,
then re-encodes from the pixels alone, so no EXIF (GPS included), ICC profile or trailing
data survives. Every upload gets fresh random names, so a photo URL never changes content
and can be cached forever; the files it replaces are deleted only once the transaction
that points the row away from them has committed, so a rollback never leaves the row
pointing at a deleted file (at worst an unreferenced new file stays behind).
"""

import secrets
import struct
import warnings
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps

# Refused above this many bytes; the browser sends about 60 KB.
MAX_BYTES = 2 * 1024 * 1024
# Pillow format names accepted; anything else, GIF and MPO included, is bad_format.
FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
# Refused above this many pixels, read from the header before decoding: a small file can
# claim a huge image (a decompression bomb). Lower than Pillow's own limits, which are
# guarded too.
MAX_PIXELS = 4096 * 4096
# The two squares' sides, in pixels: the profile header, and everywhere else.
LARGE = 512
SMALL = 128
QUALITY = 82
# What a transparent pixel becomes. The output is RGB like every photo, and a plain RGB
# conversion would surface whatever colour hides under the transparent pixels; mid grey
# reads as a disc on both the black dark theme and the off-white light one, where white
# would glare and black would vanish.
BACKGROUND = (128, 128, 128)

PHOTO_FIELDS = ("photo", "photo_small")

# What Pillow raises on a malformed file: its decoders OSError or ValueError, its parsers
# the ones Image.open() itself catches while probing formats.
UNREADABLE = (OSError, ValueError, SyntaxError, IndexError, TypeError, struct.error)


class PhotoError(ValueError):
    """An upload store_photo() refuses. `code` is what the API answers: missing,
    too_large, bad_format, too_many_pixels or photo_locked."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def store_photo(profile, upload):
    """
    Validate `upload` (a Django UploadedFile, or None), store it as the saved `profile`'s
    photo in two WebP squares and point the row at them; the previous files go once the
    transaction commits. Raises PhotoError, writing nothing, when the profile is locked or
    the upload is refused.
    """
    if profile.photo_locked:
        raise PhotoError("photo_locked")
    if not upload:
        raise PhotoError("missing")
    if upload.size > MAX_BYTES:
        raise PhotoError("too_large")
    square = _decode(upload)
    token = secrets.token_hex(6)
    base = f"{profile.user_id}-{token}"
    old = _names(profile)
    with transaction.atomic():
        # The bare name: the field's upload_to adds "avatars/". The random token makes the
        # name free, so the storage keeps it as is.
        profile.photo.save(f"{base}.webp", _webp(square, LARGE), save=False)
        profile.photo_small.save(f"{base}-sm.webp", _webp(square, SMALL), save=False)
        profile.save(update_fields=[*PHOTO_FIELDS, "updated_at"])
        _delete_on_commit(profile, old)


def remove_photo(profile):
    """
    Clear the saved `profile`'s photo and delete its files once the transaction commits,
    locked or not: a person can always take their own face down. Returns whether there was
    a photo; without one it writes nothing.
    """
    old = _names(profile)
    if not old:
        return False
    with transaction.atomic():
        profile.photo = ""
        profile.photo_small = ""
        profile.save(update_fields=[*PHOTO_FIELDS, "updated_at"])
        _delete_on_commit(profile, old)
    return True


def _decode(upload):
    """The upload as an upright RGB square, after the format and pixel-count checks.
    Pillow reads only the header in open() and decodes in load(), so the pixel count is
    checked in between."""
    upload.seek(0)
    with warnings.catch_warnings():
        # Pillow warns above its MAX_IMAGE_PIXELS and raises above twice that, both while
        # reading the header: either way the image is too big.
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            image = Image.open(upload, formats=sorted(FORMATS))
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise PhotoError("too_many_pixels") from error
        except UNREADABLE as error:
            raise PhotoError("bad_format") from error
    # A JPEG carrying extra pictures opens as MPO even when only JPEG is allowed.
    if image.format not in FORMATS:
        raise PhotoError("bad_format")
    width, height = image.size
    if width * height > MAX_PIXELS:
        raise PhotoError("too_many_pixels")
    try:
        image.load()
        # After load(): a PNG's getexif(), which exif_transpose() calls, decodes the image
        # itself.
        return _square(ImageOps.exif_transpose(image))
    except UNREADABLE as error:
        raise PhotoError("bad_format") from error


def _square(image):
    """The largest centred square of `image`, in RGB with any transparency flattened on
    BACKGROUND. The browser already sends a square; a direct upload may not."""
    if image.has_transparency_data:
        flat = Image.new("RGBA", image.size, (*BACKGROUND, 255))
        flat.alpha_composite(image.convert("RGBA"))
        image = flat
    image = image.convert("RGB")
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def _webp(square, side):
    """`square` resized to side x side and encoded as WebP, which carries no metadata
    unless asked to."""
    buffer = BytesIO()
    square.resize((side, side), Image.Resampling.LANCZOS).save(buffer, "WEBP", quality=QUALITY)
    return ContentFile(buffer.getvalue())


def _names(profile):
    """The stored file names of the profile's photo, if any."""
    return [getattr(profile, field).name for field in PHOTO_FIELDS if getattr(profile, field)]


def _delete_on_commit(profile, names):
    """Delete `names` from the photo storage once the current transaction commits. Robust:
    a file that cannot be deleted is logged and does not fail a request that succeeded."""
    if not names:
        return
    storage = profile.photo.storage

    def delete():
        for name in names:
            storage.delete(name)

    transaction.on_commit(delete, robust=True)
