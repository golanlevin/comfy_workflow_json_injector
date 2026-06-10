#!/usr/bin/env python3
"""Inject ComfyUI workflow JSON into a PNG tEXt chunk."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TEXT_CHUNKS = {b"tEXt", b"zTXt", b"iTXt"}


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def text_chunk_key(chunk_type: bytes, payload: bytes) -> str | None:
    if chunk_type not in TEXT_CHUNKS:
        return None

    raw_key = payload.split(b"\x00", 1)[0]
    try:
        return raw_key.decode("latin-1")
    except UnicodeDecodeError:
        return None


def make_text_chunk(key: str, value: str) -> bytes:
    if not key or len(key.encode("latin-1")) > 79 or "\x00" in key:
        raise ValueError("PNG tEXt keyword must be 1-79 Latin-1 bytes and contain no NUL")

    key_bytes = key.encode("latin-1")
    # json.dumps defaults to ensure_ascii=True, so this is valid Latin-1 for PNG tEXt.
    value_bytes = value.encode("latin-1")
    return png_chunk(b"tEXt", key_bytes + b"\x00" + value_bytes)


def iter_chunks(data: bytes):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("input is not a PNG file")

    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk header")

        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_start = offset
        chunk_type = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        chunk_end = payload_end + 4

        if chunk_end > len(data):
            raise ValueError(f"truncated PNG chunk {chunk_type!r}")

        yield chunk_type, data[payload_start:payload_end], data[chunk_start:chunk_end]
        offset = chunk_end

        if chunk_type == b"IEND":
            break


def compact_json(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return json.dumps(value, separators=(",", ":"))


def inject_workflow(png_in: Path, workflow_json: Path, png_out: Path, key: str = "workflow") -> None:
    workflow = compact_json(workflow_json)
    injected_chunk = make_text_chunk(key, workflow)
    wanted_keys = {key}

    data = png_in.read_bytes()
    output = bytearray(PNG_SIGNATURE)
    inserted = False
    saw_iend = False

    for chunk_type, payload, raw_chunk in iter_chunks(data):
        if chunk_type == b"IHDR":
            output.extend(raw_chunk)
            output.extend(injected_chunk)
            inserted = True
            continue

        if text_chunk_key(chunk_type, payload) in wanted_keys:
            continue

        output.extend(raw_chunk)
        if chunk_type == b"IEND":
            saw_iend = True

    if not inserted:
        raise ValueError("PNG is missing required IHDR chunk")
    if not saw_iend:
        raise ValueError("PNG is missing required IEND chunk")

    png_out.write_bytes(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inject a ComfyUI workflow JSON into a PNG tEXt metadata chunk."
    )
    parser.add_argument("png_in", type=Path, help="source PNG screenshot")
    parser.add_argument("workflow_json", type=Path, help="ComfyUI workflow JSON file")
    parser.add_argument("png_out", type=Path, help="output PNG path")
    parser.add_argument(
        "--key",
        default="workflow",
        help='PNG text keyword to write; ComfyUI expects "workflow" by default',
    )
    args = parser.parse_args(argv)

    try:
        inject_workflow(args.png_in, args.workflow_json, args.png_out, args.key)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {args.png_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
