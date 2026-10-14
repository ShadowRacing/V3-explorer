"""
Media details for Shadows File Explorer's Properties dialog.

Reads the metadata Windows Explorer shows on its Details tab, in pure Python
(no extra packages): camera EXIF data from JPEG and TIFF photos, and the
duration, format and tags of MP3, FLAC, WAV and MP4/MOV/M4A files.
Every reader is defensive: a damaged file yields fewer details, never an error.
"""
import os
import struct

MAX_SCAN = 4 * 1024 * 1024  # Never read more than this much looking for headers


def media_details(path):
    """Details for a media file as (label, value) pairs; empty when there is nothing to show."""
    readers = {
        ".jpg": exif_details, ".jpeg": exif_details, ".tif": exif_details, ".tiff": exif_details,
        ".mp3": mp3_details, ".flac": flac_details, ".wav": wav_details,
        ".mp4": mp4_details, ".m4v": mp4_details, ".mov": mp4_details, ".m4a": mp4_details,
    }
    reader = readers.get(os.path.splitext(path)[1].lower())
    if reader is None:
        return []
    try:
        with open(path, "rb") as f:
            return reader(f)
    except (OSError, struct.error, ValueError, IndexError, UnicodeDecodeError):
        return []


def format_duration(seconds):
    """3725.4 -> "1:02:05", 65 -> "1:05"."""
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _channels(count):
    return {1: "Mono", 2: "Stereo"}.get(count, f"{count} channels")


# -------------------------- EXIF (JPEG / TIFF) --------------------------

EXIF_TAGS = {
    0x0100: "tiff_width", 0x0101: "tiff_height", 0x010F: "make", 0x0110: "model", 0x0112: "orientation", 0x0131: "software", 0x0132: "datetime",
    0x8769: "exif_ifd", 0x8825: "gps_ifd",
    0x829A: "exposure", 0x829D: "fnumber", 0x8827: "iso", 0x9003: "taken", 0x9209: "flash",
    0x920A: "focal", 0xA002: "width", 0xA003: "height", 0xA434: "lens",
}
GPS_TAGS = {1: "lat_ref", 2: "lat", 3: "lon_ref", 4: "lon", 6: "altitude"}
TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}


def _read_tiff(data):
    """Parse a TIFF/EXIF block into {name: value}."""
    endian = {b"II": "<", b"MM": ">"}.get(data[:2])
    if endian is None or struct.unpack(endian + "H", data[2:4])[0] != 42:
        return {}

    def read_ifd(offset, names):
        values = {}
        if not 0 < offset < len(data) - 2:
            return values
        count = struct.unpack(endian + "H", data[offset:offset + 2])[0]
        for i in range(min(count, 200)):
            entry = offset + 2 + i * 12
            if entry + 12 > len(data):
                break
            tag, kind, n = struct.unpack(endian + "HHI", data[entry:entry + 8])
            name = names.get(tag)
            if name is None or kind not in TYPE_SIZES:
                continue
            size = TYPE_SIZES[kind] * n
            start = entry + 8 if size <= 4 else struct.unpack(endian + "I", data[entry + 8:entry + 12])[0]
            raw = data[start:start + size]
            if len(raw) < size:
                continue
            if kind == 2:
                values[name] = raw.split(b"\0", 1)[0].decode("utf-8", "replace").strip()
            elif kind in (5, 10):
                fmt = endian + ("II" if kind == 5 else "ii") * n
                parts = struct.unpack(fmt, raw)
                fractions = [(parts[j], parts[j + 1]) for j in range(0, len(parts), 2)]
                values[name] = fractions if n > 1 else fractions[0]
            else:
                fmt = {1: "B", 3: "H", 4: "I", 7: "B", 9: "i"}[kind]
                parts = struct.unpack(endian + fmt * n, raw)
                values[name] = parts[0] if n == 1 else parts
        return values

    first = struct.unpack(endian + "I", data[4:8])[0]
    values = read_ifd(first, EXIF_TAGS)
    if isinstance(values.get("exif_ifd"), int):
        values.update(read_ifd(values["exif_ifd"], EXIF_TAGS))
    if isinstance(values.get("gps_ifd"), int):
        values["gps"] = read_ifd(values["gps_ifd"], GPS_TAGS)
    return values


def _ratio(value):
    numerator, denominator = value
    return numerator / denominator if denominator else 0.0


def _exif_rows(values):
    rows = []
    camera = " ".join(v for v in (values.get("make"), values.get("model")) if v)
    # Many cameras repeat the make in the model ("Canon Canon EOS R6")
    make, model = values.get("make", ""), values.get("model", "")
    if make and model.lower().startswith(make.lower().split()[0]):
        camera = model
    if camera:
        rows.append(("Camera", camera))
    if values.get("lens"):
        rows.append(("Lens", values["lens"]))
    taken = values.get("taken") or values.get("datetime")
    if taken:
        # EXIF dates look like "2024:05:17 14:03:22"
        rows.append(("Date taken", taken.replace(":", "-", 2)))
    width = values.get("width", values.get("tiff_width"))
    height = values.get("height", values.get("tiff_height"))
    if isinstance(width, int) and isinstance(height, int):
        rows.append(("Dimensions", f"{width} x {height}"))
    if isinstance(values.get("exposure"), tuple):
        seconds = _ratio(values["exposure"])
        if seconds:
            rows.append(("Exposure", f"1/{round(1 / seconds)} s" if seconds < 1 else f"{seconds:g} s"))
    if isinstance(values.get("fnumber"), tuple) and _ratio(values["fnumber"]):
        rows.append(("Aperture", f"f/{_ratio(values['fnumber']):.1f}"))
    if isinstance(values.get("iso"), int):
        rows.append(("ISO", str(values["iso"])))
    if isinstance(values.get("focal"), tuple) and _ratio(values["focal"]):
        rows.append(("Focal length", f"{_ratio(values['focal']):g} mm"))
    if isinstance(values.get("flash"), int):
        rows.append(("Flash", "Fired" if values["flash"] & 1 else "Did not fire"))
    gps = values.get("gps") or {}
    if isinstance(gps.get("lat"), list) and isinstance(gps.get("lon"), list):
        def degrees(parts, ref, negative):
            d, m, s = (_ratio(p) for p in parts[:3])
            value = d + m / 60 + s / 3600
            return -value if ref == negative else value
        lat = degrees(gps["lat"], gps.get("lat_ref"), "S")
        lon = degrees(gps["lon"], gps.get("lon_ref"), "W")
        rows.append(("Location", f"{lat:.5f}, {lon:.5f}"))
    if values.get("software"):
        rows.append(("Software", values["software"]))
    return rows


def exif_details(f):
    head = f.read(4)
    if head[:2] in (b"II", b"MM"):  # TIFF file: the whole file is the EXIF structure
        f.seek(0)
        return _exif_rows(_read_tiff(f.read(MAX_SCAN)))
    if head[:2] != b"\xff\xd8":
        return []
    f.seek(2)
    rows_from_exif = []
    dimensions = None
    while f.tell() < MAX_SCAN:
        marker = f.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            break
        if marker[1] in (0xD9, 0xDA):  # End of image, or the image data starts
            break
        length = struct.unpack(">H", f.read(2))[0]
        segment = f.read(length - 2)
        if marker[1] == 0xE1 and segment.startswith(b"Exif\0\0") and not rows_from_exif:
            rows_from_exif = _exif_rows(_read_tiff(segment[6:]))
        elif marker[1] in (0xC0, 0xC1, 0xC2) and len(segment) >= 5:
            height, width = struct.unpack(">HH", segment[1:5])
            dimensions = (width, height)
    if dimensions and not any(label == "Dimensions" for label, _ in rows_from_exif):
        rows_from_exif.insert(0, ("Dimensions", f"{dimensions[0]} x {dimensions[1]}"))
    return rows_from_exif


# -------------------------- MP3 --------------------------

MP3_BITRATES = {  # kbps by (MPEG version 1?, index)
    True: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    False: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
MP3_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
ID3_FRAMES = {"TIT2": "Title", "TPE1": "Artist", "TALB": "Album", "TPE2": "Album artist",
              "TYER": "Year", "TDRC": "Year", "TCON": "Genre", "TRCK": "Track"}


def _id3_text(raw):
    encoding = raw[:1]
    body = raw[1:]
    if encoding == b"\x01":
        text = body.decode("utf-16", "replace")
    elif encoding == b"\x02":
        text = body.decode("utf-16-be", "replace")
    elif encoding == b"\x03":
        text = body.decode("utf-8", "replace")
    else:
        text = body.decode("latin-1")
    return text.replace("\0", " ").strip()


def _synchsafe(raw):
    return (raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]


def mp3_details(f):
    size = os.fstat(f.fileno()).st_size
    tags, audio_start = [], 0
    header = f.read(10)
    if header[:3] == b"ID3":
        version = header[3]
        tag_size = _synchsafe(header[6:10])
        audio_start = 10 + tag_size
        data = f.read(min(tag_size, MAX_SCAN))
        position = 0
        while position + 10 <= len(data):
            frame_id = data[position:position + 4].decode("latin-1")
            if not frame_id.strip("\0"):
                break
            frame_size = (_synchsafe(data[position + 4:position + 8]) if version >= 4
                          else struct.unpack(">I", data[position + 4:position + 8])[0])
            if frame_id in ID3_FRAMES and frame_size:
                label = ID3_FRAMES[frame_id]
                value = _id3_text(data[position + 10:position + 10 + frame_size])
                if value and label not in dict(tags):
                    tags.append((label, value))
            position += 10 + frame_size

    # The first frame header: sync bits, then version, layer, bitrate and sample rate
    f.seek(audio_start)
    chunk = f.read(65536)
    rows = []
    for i in range(len(chunk) - 4):
        b1, b2, b3, b4 = chunk[i:i + 4]
        if b1 != 0xFF or (b2 & 0xE0) != 0xE0:
            continue
        version, layer = (b2 >> 3) & 3, (b2 >> 1) & 3
        bitrate_index, rate_index = b3 >> 4, (b3 >> 2) & 3
        if version == 1 or layer != 1 or bitrate_index in (0, 15) or rate_index == 3:
            continue  # Not a valid MPEG Layer III header
        mpeg1 = version == 3
        bitrate = MP3_BITRATES[mpeg1][bitrate_index] * 1000
        sample_rate = MP3_RATES[version][rate_index]
        channels = 1 if (b4 >> 6) == 3 else 2
        # A Xing/Info header (VBR files) gives the exact number of frames
        side_info = (32 if channels == 2 else 17) if mpeg1 else (17 if channels == 2 else 9)
        xing = chunk[i + 4 + side_info:i + 4 + side_info + 12]
        samples_per_frame = 1152 if mpeg1 else 576
        bitrate_text = f"{bitrate // 1000} kbps"
        if xing[:4] in (b"Xing", b"Info") and struct.unpack(">I", xing[4:8])[0] & 1:
            frames = struct.unpack(">I", xing[8:12])[0]
            duration = frames * samples_per_frame / sample_rate
            if xing[:4] == b"Xing" and duration:  # "Info" marks a constant bit rate file
                bitrate_text = f"{round((size - audio_start) * 8 / duration / 1000)} kbps (variable)"
        else:
            duration = (size - audio_start - i) * 8 / bitrate
        rows = [("Length", format_duration(duration)), ("Bit rate", bitrate_text)]
        rows += [("Sample rate", f"{sample_rate / 1000:g} kHz"), ("Channels", _channels(channels))]
        break
    return tags + rows


# -------------------------- FLAC --------------------------

def flac_details(f):
    if f.read(4) != b"fLaC":
        return []
    rows, tags = [], []
    while True:
        header = f.read(4)
        if len(header) < 4:
            break
        last, kind = header[0] & 0x80, header[0] & 0x7F
        length = int.from_bytes(header[1:4], "big")
        block = f.read(length)
        if kind == 0 and len(block) >= 18:  # STREAMINFO
            bits = int.from_bytes(block[10:18], "big")
            sample_rate = bits >> 44
            channels = ((bits >> 41) & 7) + 1
            depth = ((bits >> 36) & 31) + 1
            samples = bits & 0xFFFFFFFFF
            if sample_rate:
                rows = [("Length", format_duration(samples / sample_rate)),
                        ("Sample rate", f"{sample_rate / 1000:g} kHz"),
                        ("Bit depth", f"{depth}-bit"), ("Channels", _channels(channels))]
        elif kind == 4:  # Vorbis comments: TITLE=..., ARTIST=...
            vendor = struct.unpack("<I", block[:4])[0]
            position = 4 + vendor
            count = struct.unpack("<I", block[position:position + 4])[0]
            position += 4
            names = {"TITLE": "Title", "ARTIST": "Artist", "ALBUM": "Album", "DATE": "Year",
                     "GENRE": "Genre", "TRACKNUMBER": "Track"}
            for _ in range(min(count, 500)):
                size = struct.unpack("<I", block[position:position + 4])[0]
                comment = block[position + 4:position + 4 + size].decode("utf-8", "replace")
                position += 4 + size
                key, _, value = comment.partition("=")
                label = names.get(key.upper())
                if label and value and label not in dict(tags):
                    tags.append((label, value))
        if last:
            break
    return tags + rows


# -------------------------- WAV --------------------------

def wav_details(f):
    header = f.read(12)
    if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        return []
    channels = sample_rate = byte_rate = depth = None
    data_size = None
    while True:
        chunk = f.read(8)
        if len(chunk) < 8:
            break
        kind, size = chunk[:4], struct.unpack("<I", chunk[4:])[0]
        if kind == b"fmt ":
            fmt = f.read(size)
            _, channels, sample_rate, byte_rate, _, depth = struct.unpack("<HHIIHH", fmt[:16])
        elif kind == b"data":
            data_size = size
            break
        else:
            f.seek(size + (size & 1), os.SEEK_CUR)
    if not sample_rate:
        return []
    rows = []
    if data_size is not None and byte_rate:
        rows.append(("Length", format_duration(data_size / byte_rate)))
    rows += [("Sample rate", f"{sample_rate / 1000:g} kHz"), ("Bit depth", f"{depth}-bit"),
             ("Channels", _channels(channels))]
    return rows


# -------------------------- MP4 / MOV / M4A --------------------------

def _boxes(f, end):
    """Yield (type, payload start, payload end) for the boxes from f's position up to end."""
    while f.tell() + 8 <= end:
        start = f.tell()
        size, kind = struct.unpack(">I4s", f.read(8))
        header = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            header = 16
        elif size == 0:
            size = end - start
        if size < header:
            return
        yield kind, start + header, min(start + size, end)
        f.seek(start + size)


def mp4_details(f):
    end = os.fstat(f.fileno()).st_size
    rows = {}
    for kind, start, stop in _boxes(f, end):
        if kind != b"moov":
            continue
        f.seek(start)
        for child, child_start, child_stop in _boxes(f, stop):
            here = f.tell()
            if child == b"mvhd":
                f.seek(child_start)
                version = f.read(4)[0]
                if version == 1:
                    f.seek(16, os.SEEK_CUR)
                    timescale, duration = struct.unpack(">IQ", f.read(12))
                else:
                    f.seek(8, os.SEEK_CUR)
                    timescale, duration = struct.unpack(">II", f.read(8))
                if timescale:
                    rows["Length"] = format_duration(duration / timescale)
            elif child == b"trak" and "Frame size" not in rows:
                f.seek(child_start)
                for box, box_start, _ in _boxes(f, child_stop):
                    if box == b"tkhd":
                        f.seek(box_start)
                        version = f.read(4)[0]
                        # Width and height are the last 8 bytes, as 16.16 fixed point
                        f.seek(box_start + (88 if version == 1 else 76))
                        width, height = struct.unpack(">II", f.read(8))
                        if width >> 16 and height >> 16:
                            rows["Frame size"] = f"{width >> 16} x {height >> 16}"
                        break
            f.seek(here)
        break
    return list(rows.items())
