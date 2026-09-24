"""
Players' photos (see the player profile customization design spec under
docs/superpowers/specs/). store_photo() turns an upload into two WebP squares and
remove_photo() takes them down; both live here and not in UserProfile.save() because they
touch the filesystem, not business rules. A deleted profile, its user's cascade included,
takes its files with it (signals.py calls delete_on_commit()).

The browser crops and shrinks before uploading, but the server trusts none of it: it
checks the size, the format and the pixel count from the header before decoding anything,
then re-encodes from the pixels alone, so no EXIF (GPS included), ICC profile, XMP or
trailing data survives. Every upload gets fresh random names, so a photo URL never changes
content and can be cached forever.

Both functions read the row under lock (select_for_update) rather than trusting the
profile they are handed: a lock set since it was read still refuses the upload, and the
files deleted are the ones the row points at, so a stale copy orphans nothing. Replaced
files are deleted only once the transaction that points the row away from them commits, so
a rollback never leaves the row pointing at a deleted file. store_photo() deletes the files
it wrote when its own block fails; a rollback of an enclosing transaction after it
returned still leaves them behind, unreferenced.
"""

import logging
import secrets
import struct
import warnings
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import ExifTags, Image

from .models import UserProfile

logger = logging.getLogger(__name__)

# Refused above this many bytes; the browser sends about 60 KB.
MAX_BYTES = 2 * 1024 * 1024
# The formats whose parsers may read an upload (Pillow format names): no other parser ever
# sees one.
FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
# What those parsers may hand back: a JPEG carrying extra pictures, as some phone cameras
# write, opens as MPO even when only JPEG is allowed; its first picture is used.
OPENED_AS = FORMATS | {"MPO"}
# Refused above this many pixels, read from the header before decoding: a small file can
# claim a huge image (a decompression bomb). Lower than Pillow's own limits, which are
# guarded too.
MAX_PIXELS = 4096 * 4096
# The two squares' sides, in pixels: the profile header, and everywhere else.
LARGE = 512
SMALL = 128
QUALITY = 82
# A JPEG is decoded at the smallest DCT scale that keeps both sides at least this long:
# cheap on memory for a big photo, and still twice the large square for the resize.
DRAFT = 2 * LARGE
# What a transparent pixel becomes. The output is RGB like every photo, and a plain RGB
# conversion would surface whatever colour hides under the transparent pixels; mid grey
# reads as a disc on both the black dark theme and the off-white light one, where white
# would glare and black would vanish.
BACKGROUND = (128, 128, 128)
# How to turn a picture upright for each EXIF orientation (1, or anything else, is left
# as is), as ImageOps.exif_transpose() does.
UPRIGHT = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}

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
    photo in two WebP squares and point the row at them; the files the row pointed at go
    once the transaction commits. Raises PhotoError, writing nothing, when the profile is
    locked or the upload is refused.
    """
    # Checked again on the locked row below; this one only spares a locked person the
    # decoding.
    if profile.photo_locked:
        raise PhotoError("photo_locked")
    if not upload:
        raise PhotoError("missing")
    if upload.size > MAX_BYTES:
        raise PhotoError("too_large")
    large = _decode(upload).resize((LARGE, LARGE), Image.Resampling.LANCZOS)
    small = large.resize((SMALL, SMALL), Image.Resampling.LANCZOS)
    contents = (_webp(large), _webp(small))
    base = f"{profile.user_id}-{secrets.token_hex(6)}"
    previous = (profile.photo.name, profile.photo_small.name)
    written = []
    try:
        with transaction.atomic():
            row = UserProfile.objects.select_for_update().get(pk=profile.pk)
            if row.photo_locked:
                raise PhotoError("photo_locked")
            for field, name, content in zip(
                PHOTO_FIELDS, (f"{base}.webp", f"{base}-sm.webp"), contents
            ):
                # The bare name: the field's upload_to adds "avatars/". The random token
                # makes the name free, so the storage keeps it as is.
                file = getattr(profile, field)
                file.save(name, content, save=False)
                written.append(file.name)
            profile.save(update_fields=[*PHOTO_FIELDS, "updated_at"])
            delete_on_commit(photo_names(row))
    except BaseException:
        # Nothing points at what was written: delete it now, and hand the caller its
        # profile back as it was.
        for name in written:
            _delete(name)
        profile.photo, profile.photo_small = previous
        raise


def remove_photo(profile):
    """
    Clear the saved `profile`'s photo and delete the files its row points at once the
    transaction commits, locked or not: a person can always take their own face down.
    Returns whether there was a photo; without one it writes nothing.
    """
    with transaction.atomic():
        row = UserProfile.objects.select_for_update().get(pk=profile.pk)
        names = photo_names(row)
        profile.photo = ""
        profile.photo_small = ""
        if not names:
            return False
        profile.save(update_fields=[*PHOTO_FIELDS, "updated_at"])
        delete_on_commit(names)
    return True


def photo_urls(profile):
    """{"large", "small"}: the site-relative URLs of the profile's photo (MEDIA_URL, so
    /media/avatars/...), or None without a profile row or a photo. No query."""
    if profile is None or not profile.photo or not profile.photo_small:
        return None
    return {"large": profile.photo.url, "small": profile.photo_small.url}


def photo_names(profile):
    """The stored file names of the profile's photo, if any."""
    return [getattr(profile, field).name for field in PHOTO_FIELDS if getattr(profile, field)]


def delete_on_commit(names):
    """Delete the photo files `names` once the current transaction commits (at once
    outside one). One robust callback per file: a file that cannot be deleted is logged,
    keeps no other file, and does not fail a request that succeeded."""
    for name in names:
        transaction.on_commit(_deleter(name), robust=True)


def _deleter(name):
    """A callback deleting `name`: a named function, which Django's on_commit log needs."""

    def delete_photo_file():
        _storage().delete(name)

    return delete_photo_file


def _delete(name):
    """Delete `name` now, logging a failure instead of raising it."""
    try:
        _storage().delete(name)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Could not delete the photo file %s", name)


def _storage():
    """Where photos are stored: the photo fields' storage (MEDIA_ROOT by default)."""
    return UserProfile._meta.get_field("photo").storage


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
    if image.format not in OPENED_AS:
        raise PhotoError("bad_format")
    width, height = image.size
    if width * height > MAX_PIXELS:
        raise PhotoError("too_many_pixels")
    try:
        if image.format in ("JPEG", "MPO"):
            # After the check: draft() changes the size the header gave.
            image.draft("RGB", (DRAFT, DRAFT))
        image.load()
        # After load(): a PNG's getexif() decodes the image itself.
        turn = _upright(image)
        return _square(image, turn)
    except UNREADABLE as error:
        raise PhotoError("bad_format") from error


def _upright(image):
    """How to turn `image` upright, from its EXIF orientation. A photo is worth more than
    its metadata: an EXIF block Pillow cannot read, or an orientation it cannot use, means
    no turn rather than a refusal (ImageOps.exif_transpose() also rewrites the EXIF, and
    raised on some malformed blocks)."""
    try:
        return UPRIGHT.get(image.getexif().get(ExifTags.Base.Orientation))
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _square(image, turn):
    """The largest centred square of `image`, turned by `turn`, in RGB with any
    transparency flattened on BACKGROUND and no metadata left in `info`. The browser
    already sends a square; a direct upload may not. Cropping first leaves less to turn
    and convert (a centred square turns into the centred square of the turned image)."""
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    square = image.crop((left, top, left + side, top + side))
    if turn is not None:
        square = square.transpose(turn)
    if square.has_transparency_data:
        flat = Image.new("RGBA", square.size, (*BACKGROUND, 255))
        flat.alpha_composite(square.convert("RGBA"))
        square = flat
    square = square.convert("RGB")
    # Pillow copies info (EXIF, ICC profile, XMP...) from image to image: none of it goes
    # on, whatever the encoder would keep.
    square.info = {}
    return square


def _webp(image):
    """`image` encoded as WebP."""
    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=QUALITY)
    return ContentFile(buffer.getvalue())
