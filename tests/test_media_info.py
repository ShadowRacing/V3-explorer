import struct
import wave

from shadows_explorer.core.media_info import format_duration, media_details


def _tiff_with_exif():
    """A little-endian TIFF/EXIF block: IFD0 (make, model, EXIF pointer) and an EXIF IFD."""
    make, model = b"Canon\0", b"Canon EOS R6\0"
    ifd0_offset = 8
    ifd0_entries = 3
    ifd0_size = 2 + ifd0_entries * 12 + 4
    exif_offset = ifd0_offset + ifd0_size
    exif_entries = 5
    exif_size = 2 + exif_entries * 12 + 4
    data_offset = exif_offset + exif_size
    taken = b"2024:05:17 14:03:22\0"
    blobs = [make, model, taken, struct.pack("<II", 1, 250), struct.pack("<II", 28, 10)]
    offsets = []
    position = data_offset
    for blob in blobs:
        offsets.append(position)
        position += len(blob)

    out = b"II" + struct.pack("<HI", 42, ifd0_offset)
    out += struct.pack("<H", ifd0_entries)
    out += struct.pack("<HHII", 0x010F, 2, len(make), offsets[0])
    out += struct.pack("<HHII", 0x0110, 2, len(model), offsets[1])
    out += struct.pack("<HHII", 0x8769, 4, 1, exif_offset)
    out += struct.pack("<I", 0)
    out += struct.pack("<H", exif_entries)
    out += struct.pack("<HHII", 0x9003, 2, len(taken), offsets[2])
    out += struct.pack("<HHII", 0x829A, 5, 1, offsets[3])
    out += struct.pack("<HHII", 0x829D, 5, 1, offsets[4])
    out += struct.pack("<HHI", 0x8827, 3, 1) + struct.pack("<HH", 400, 0)
    out += struct.pack("<HHI", 0x9209, 3, 1) + struct.pack("<HH", 16, 0)
    out += struct.pack("<I", 0)
    return out + b"".join(blobs)


def test_jpeg_exif(tmp_path):
    exif = b"Exif\0\0" + _tiff_with_exif()
    sof = b"\x08" + struct.pack(">HH", 3000, 4000) + b"\x03" + b"\0" * 9
    jpeg = (b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
            + b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof + b"\xff\xda\0\x02" + b"\0" * 10)
    path = tmp_path / "photo.JPG"
    path.write_bytes(jpeg)
    details = dict(media_details(str(path)))
    assert details["Camera"] == "Canon EOS R6"
    assert details["Date taken"] == "2024-05-17 14:03:22"
    assert details["Exposure"] == "1/250 s"
    assert details["Aperture"] == "f/2.8"
    assert details["ISO"] == "400"
    assert details["Flash"] == "Did not fire"
    assert details["Dimensions"] == "4000 x 3000"


def test_tiff_file(tmp_path):
    path = tmp_path / "scan.tif"
    path.write_bytes(_tiff_with_exif())
    assert dict(media_details(str(path)))["Camera"] == "Canon EOS R6"


def test_wav(tmp_path):
    path = tmp_path / "beep.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\0\0\0\0" * 44100 * 3)
    assert media_details(str(path)) == [("Length", "0:03"), ("Sample rate", "44.1 kHz"),
                                        ("Bit depth", "16-bit"), ("Channels", "Stereo")]


def test_flac(tmp_path):
    sample_rate, channels, depth, samples = 48000, 2, 24, 48000 * 125
    bits = (sample_rate << 44) | ((channels - 1) << 41) | ((depth - 1) << 36) | samples
    streaminfo = b"\0" * 10 + bits.to_bytes(8, "big") + b"\0" * 16
    vendor = b"test"
    comments = [b"TITLE=Song", b"ARTIST=Band"]
    vorbis = struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", len(comments))
    vorbis += b"".join(struct.pack("<I", len(c)) + c for c in comments)
    data = (b"fLaC" + bytes([0]) + len(streaminfo).to_bytes(3, "big") + streaminfo
            + bytes([0x84]) + len(vorbis).to_bytes(3, "big") + vorbis)
    path = tmp_path / "song.flac"
    path.write_bytes(data)
    assert media_details(str(path)) == [("Title", "Song"), ("Artist", "Band"), ("Length", "2:05"),
                                        ("Sample rate", "48 kHz"), ("Bit depth", "24-bit"),
                                        ("Channels", "Stereo")]


def _id3_frame(frame_id, text):
    body = b"\x03" + text.encode("utf-8")
    return frame_id.encode() + struct.pack(">I", len(body)) + b"\0\0" + body


def test_mp3_with_id3_cbr(tmp_path):
    frames = _id3_frame("TIT2", "Intro") + _id3_frame("TPE1", "Artist Name")
    size = len(frames)
    synchsafe = bytes([(size >> 21) & 127, (size >> 14) & 127, (size >> 7) & 127, size & 127])
    id3 = b"ID3\x03\x00\x00" + synchsafe + frames
    # MPEG-1 Layer III, 128 kbps, 44.1 kHz, stereo; 160000 bytes of audio = 10 seconds
    frame_header = bytes([0xFF, 0xFB, 0x90, 0x00])
    audio = (frame_header + b"\0" * 413) * (160000 // 417) + b"\0" * (160000 % 417)
    path = tmp_path / "track.mp3"
    path.write_bytes(id3 + audio)
    details = dict(media_details(str(path)))
    assert details["Title"] == "Intro" and details["Artist"] == "Artist Name"
    assert details["Length"] == "0:10"
    assert details["Bit rate"] == "128 kbps"
    assert details["Sample rate"] == "44.1 kHz" and details["Channels"] == "Stereo"


def _box(kind, payload):
    return struct.pack(">I", len(payload) + 8) + kind + payload


def test_mp4_duration_and_frame_size(tmp_path):
    mvhd = _box(b"mvhd", b"\0" * 4 + b"\0" * 8 + struct.pack(">II", 1000, 95_000) + b"\0" * 80)
    tkhd = _box(b"tkhd", b"\0" * 76 + struct.pack(">II", 1920 << 16, 1080 << 16))
    moov = _box(b"moov", mvhd + _box(b"trak", tkhd))
    path = tmp_path / "clip.mp4"
    path.write_bytes(_box(b"ftyp", b"isom" + b"\0" * 4) + moov + _box(b"mdat", b"\0" * 100))
    assert media_details(str(path)) == [("Length", "1:35"), ("Frame size", "1920 x 1080")]


def test_damaged_and_unknown_files(tmp_path):
    for name, data in (("bad.jpg", b"\xff\xd8\xff\xe1\x00"), ("bad.mp3", b"ID3\x04"), ("bad.flac", b"fLaC\x00"),
                       ("bad.mp4", b"\0\0\0\x01moov"), ("bad.wav", b"RIFF"), ("notes.txt", b"hello")):
        path = tmp_path / name
        path.write_bytes(data)
        assert isinstance(media_details(str(path)), list)
    assert media_details(str(tmp_path / "missing.mp3")) == []


def test_format_duration():
    assert format_duration(65) == "1:05"
    assert format_duration(3725.4) == "1:02:05"
    assert format_duration(0) == "0:00"
