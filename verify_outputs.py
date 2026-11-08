"""Read PNG and MP4 metadata without external tools."""

import os
import struct
import sys

ROOT = r"E:\Work\2026-11-08-oriental-pearl-blender\2026-11-08-project"
MP4 = os.path.join(ROOT, "oriental_pearl.mp4")
STILLS = (
    os.path.join(ROOT, "frame_0001.png"),
    os.path.join(ROOT, "frame_0120.png"),
    os.path.join(ROOT, "frame_0240.png"),
)


def png_size(path):
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise RuntimeError(f"not a PNG: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def iter_boxes(data, start, end):
    pos = start
    while pos + 8 <= end:
        size = struct.unpack_from(">I", data, pos)[0]
        box_type = data[pos + 4 : pos + 8]
        header = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            return
        yield box_type, pos, size, header
        pos += size


def child_map(data, pos, size, header):
    found = {}
    for box_type, child_pos, child_size, child_header in iter_boxes(data, pos + header, pos + size):
        found.setdefault(box_type, []).append((child_pos, child_size, child_header))
    return found


def mvhd_timing(data, pos, size, header):
    offset = pos + header
    version = data[offset]
    if version == 0:
        timescale, duration = struct.unpack_from(">II", data, offset + 12)
    else:
        timescale = struct.unpack_from(">I", data, offset + 20)[0]
        duration = struct.unpack_from(">Q", data, offset + 24)[0]
    return timescale, duration


def mdhd_timing(data, pos, size, header):
    return mvhd_timing(data, pos, size, header)


def tkhd_size(data, pos, size):
    width = struct.unpack_from(">I", data, pos + size - 8)[0] / 65536.0
    height = struct.unpack_from(">I", data, pos + size - 4)[0] / 65536.0
    return width, height


def stsd_codecs(data, pos, size, header):
    offset = pos + header
    entry_count = struct.unpack_from(">I", data, offset + 4)[0]
    cursor = offset + 8
    codecs = []
    for _ in range(entry_count):
        if cursor + 8 > pos + size:
            break
        entry_size = struct.unpack_from(">I", data, cursor)[0]
        codecs.append(data[cursor + 4 : cursor + 8].decode("latin1", "replace"))
        if entry_size < 8:
            break
        cursor += entry_size
    return codecs


def stts_rate(data, pos, size, header, media_timescale):
    offset = pos + header
    count = struct.unpack_from(">I", data, offset + 4)[0]
    cursor = offset + 8
    samples = 0
    deltas = []
    for _ in range(count):
        sample_count, sample_delta = struct.unpack_from(">II", data, cursor)
        samples += sample_count
        deltas.append((sample_count, sample_delta))
        cursor += 8
    if len(deltas) == 1 and deltas[0][1]:
        fps = media_timescale / deltas[0][1]
    else:
        fps = None
    return samples, deltas, fps


def inspect_mp4(path):
    with open(path, "rb") as handle:
        data = handle.read()
    top = {}
    for box_type, pos, size, header in iter_boxes(data, 0, len(data)):
        top.setdefault(box_type, []).append((pos, size, header))
    if b"moov" not in top:
        raise RuntimeError("moov box not found")
    moov_pos, moov_size, moov_header = top[b"moov"][0]
    moov = child_map(data, moov_pos, moov_size, moov_header)
    timescale, duration = mvhd_timing(data, *moov[b"mvhd"][0])
    report = {
        "bytes": len(data),
        "timescale": timescale,
        "duration_units": duration,
        "duration_s": duration / timescale if timescale else None,
        "tracks": [],
    }
    for trak_pos, trak_size, trak_header in moov.get(b"trak", []):
        trak = child_map(data, trak_pos, trak_size, trak_header)
        width, height = tkhd_size(data, *trak[b"tkhd"][0][:2]) if b"tkhd" in trak else (None, None)
        # tkhd_size needs pos, size only; child tuple is pos, size, header
        if b"tkhd" in trak:
            width, height = tkhd_size(data, trak[b"tkhd"][0][0], trak[b"tkhd"][0][1])
        media_timescale = None
        codecs = []
        samples = None
        fps = None
        mdia = child_map(data, *trak[b"mdia"][0]) if b"mdia" in trak else {}
        if b"mdhd" in mdia:
            media_timescale, _media_duration = mdhd_timing(data, *mdia[b"mdhd"][0])
        minf = child_map(data, *mdia[b"minf"][0]) if b"minf" in mdia else {}
        stbl = child_map(data, *minf[b"stbl"][0]) if b"stbl" in minf else {}
        if b"stsd" in stbl:
            codecs = stsd_codecs(data, *stbl[b"stsd"][0])
        if b"stts" in stbl and media_timescale:
            samples, _deltas, fps = stts_rate(data, *stbl[b"stts"][0], media_timescale)
        report["tracks"].append(
            {
                "width": width,
                "height": height,
                "codecs": codecs,
                "media_timescale": media_timescale,
                "samples": samples,
                "fps": fps,
            }
        )
    return report


def main():
    ok = True
    for path in STILLS:
        if not os.path.exists(path):
            print(f"MISSING {path}")
            ok = False
            continue
        width, height = png_size(path)
        print(f"PNG {path} {width}x{height} bytes={os.path.getsize(path)}")
        if (width, height) != (1920, 1080):
            ok = False
    if not os.path.exists(MP4):
        print(f"MISSING {MP4}")
        return 1
    info = inspect_mp4(MP4)
    print(
        f"MP4 {MP4} bytes={info['bytes']} duration_s={info['duration_s']:.4f} "
        f"timescale={info['timescale']} units={info['duration_units']}"
    )
    for index, track in enumerate(info["tracks"]):
        print(
            f"TRACK {index} {track['width']}x{track['height']} codecs={track['codecs']} "
            f"samples={track['samples']} fps={track['fps']} media_timescale={track['media_timescale']}"
        )
    video = next((track for track in info["tracks"] if track["codecs"] and track["codecs"][0] not in {"mp4a", "sowt"}), None)
    if video is None:
        print("NO_VIDEO_TRACK")
        return 1
    if abs(info["duration_s"] - 10.0) > 0.05:
        print("DURATION_OUT_OF_RANGE")
        ok = False
    if (round(video["width"]), round(video["height"])) != (1920, 1080):
        print("RESOLUTION_MISMATCH")
        ok = False
    if video["fps"] is None or abs(video["fps"] - 24.0) > 0.05:
        print("FPS_MISMATCH")
        ok = False
    if "avc1" not in video["codecs"] and "avc3" not in video["codecs"]:
        print("CODEC_NOT_H264")
        ok = False
    print("VERIFY_OK" if ok else "VERIFY_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
