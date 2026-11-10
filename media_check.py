"""Container and codec sniffing for uploaded videos (stdlib only, no ffprobe needed).

The Pi 5 has a hardware decoder for HEVC only, and the player's dmabuf output cannot
display software-decoded frames, so an H.264 upload plays as a black screen. Checking
the codec at upload time turns that into a clear error message instead.
"""

import os
import struct

# Container suffixes the player scans for (signage.py EXTENSIONS).
ALLOWED_EXTENSIONS = (".mp4", ".mkv", ".mov")
MAX_NAME_BYTES = 150

_ISO_FOURCC = {
    b"hvc1": "hevc", b"hev1": "hevc", b"dvh1": "hevc", b"dvhe": "hevc",
    b"avc1": "h264", b"avc2": "h264", b"avc3": "h264", b"avc4": "h264",
    b"vp09": "vp9", b"av01": "av1", b"mp4v": "mpeg4", b"mjpa": "mjpeg", b"jpeg": "mjpeg",
}
_MKV_IDS = (
    (b"V_MPEGH/ISO/HEVC", "hevc"), (b"V_MPEG4/ISO/AVC", "h264"), (b"V_VP9", "vp9"),
    (b"V_VP8", "vp8"), (b"V_AV1", "av1"), (b"V_MPEG4/ISO/ASP", "mpeg4"), (b"V_MPEG2", "mpeg2"),
)
_MKV_SCAN_BYTES = 4 * 1024 * 1024  # Tracks normally sit in the first few KB


def validate_upload_name(name):
    """(ok, message) for a client-supplied file name; this is the only place names are vetted."""
    if not name or name in (".", ".."):
        return False, "File name is empty"
    if name.startswith("."):
        return False, "File names may not start with a dot"
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name) or "/" in name or "\\" in name:
        return False, "File name contains control or path characters"
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        return False, f"File name is longer than {MAX_NAME_BYTES} bytes"
    if os.path.splitext(name)[1].lower() not in ALLOWED_EXTENSIONS:
        return False, "Unsupported file type; use " + ", ".join(ALLOWED_EXTENSIONS)
    return True, ""


def _boxes(handle, start, end):
    """Yield (type, payload_start, box_end) for the ISO-BMFF boxes in [start, end)."""
    position = start
    while position + 8 <= end:
        handle.seek(position)
        header = handle.read(8)
        if len(header) < 8:
            return
        size, kind = struct.unpack(">I4s", header)
        header_size = 8
        if size == 1:
            extended = handle.read(8)
            if len(extended) < 8:
                return
            size = struct.unpack(">Q", extended)[0]
            header_size = 16
        elif size == 0:
            size = end - position
        if size < header_size or position + size > end:
            return  # truncated or corrupt box
        yield kind, position + header_size, position + size
        position += size


def _find(handle, start, end, kind):
    return next(((a, b) for k, a, b in _boxes(handle, start, end) if k == kind), None)


def _probe_iso(handle, size):
    moov = _find(handle, 0, size, b"moov")
    if not moov:
        return None
    for kind, a, b in _boxes(handle, moov[0], moov[1]):
        if kind != b"trak":
            continue
        mdia = _find(handle, a, b, b"mdia")
        hdlr = mdia and _find(handle, mdia[0], mdia[1], b"hdlr")
        if not hdlr:
            continue
        handle.seek(hdlr[0] + 8)
        if handle.read(4) != b"vide":
            continue
        minf = _find(handle, mdia[0], mdia[1], b"minf")
        stbl = minf and _find(handle, minf[0], minf[1], b"stbl")
        stsd = stbl and _find(handle, stbl[0], stbl[1], b"stsd")
        if not stsd:
            continue
        handle.seek(stsd[0] + 4)  # version/flags
        if struct.unpack(">I", handle.read(4))[0] < 1:
            continue
        entry = handle.read(8)
        if len(entry) < 8:
            continue
        fourcc = entry[4:8]
        info = {"container": "iso", "codec": _ISO_FOURCC.get(fourcc, fourcc.decode("latin-1").strip().lower()),
                "width": None, "height": None}
        dims = handle.read(28)  # skip reserved/data-ref/pre-defined fields up to width/height
        if len(dims) == 28:
            info["width"], info["height"] = struct.unpack(">HH", dims[24:28])
        return info
    return None


def _probe_matroska(handle):
    handle.seek(0)
    blob = handle.read(_MKV_SCAN_BYTES)
    best = None
    for needle, codec in _MKV_IDS:
        at = blob.find(needle)
        if at != -1 and (best is None or at < best[0]):
            best = (at, codec)
    return {"container": "matroska", "codec": best[1] if best else "unknown", "width": None, "height": None}


def probe_video(path):
    """Return {'container','codec','width','height'} or None when the file is not a known video container."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            head = handle.read(12)
            if len(head) >= 8 and head[4:8] == b"ftyp":
                return _probe_iso(handle, size)
            if head[:4] == b"\x1a\x45\xdf\xa3":
                return _probe_matroska(handle)
    except (OSError, struct.error):
        return None
    return None


def check_upload(path, filename, allowed_codecs):
    """(ok, message): the saved file must match its suffix and use a codec the player can render."""
    info = probe_video(path)
    suffix = os.path.splitext(filename)[1].lower()
    if info is None:
        return False, "Not a readable video file (expected MP4, MOV or MKV)"
    if (suffix in (".mp4", ".mov")) != (info["container"] == "iso"):
        return False, "File extension does not match the file contents"
    codec = info["codec"]
    if codec not in allowed_codecs:
        wanted = ", ".join(c.upper() for c in allowed_codecs)
        return False, (f"Video codec {codec.upper()} cannot be played on this device. "
                       f"Convert it to {wanted} (for example: ffmpeg -i in.mp4 -c:v libx265 -tag:v hvc1 out.mp4)")
    return True, ""
