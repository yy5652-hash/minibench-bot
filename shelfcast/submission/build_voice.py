"""Synthesise the demo video's voice-over from the storyboard.

    python submission/build_voice.py --out submission/video

Reads the "Voice-over (exact)" column of submission/video_script.md and writes vo_NN.wav per shot
with Kokoro-82M (Apache-2.0) running locally through mlx-audio. A line that still has a [placeholder]
is skipped with a message: fill the number in the storyboard first, so the voice never says a figure
that is not in the results.

Needs Apple silicon: pip install mlx-audio "misaki[en]"
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def lines(storyboard: Path) -> list[tuple[int, str]]:
    out = []
    for row in storyboard.read_text().splitlines():
        cells = [c.strip() for c in row.split("|")]
        if len(cells) < 8 or not cells[1].isdigit():
            continue
        text = cells[6].strip().strip('"')
        if text and not text.startswith("("):
            out.append((int(cells[1]), text))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--storyboard", default="submission/video_script.md")
    ap.add_argument("--out", default="submission/video")
    ap.add_argument("--voice", default="bm_george")
    ap.add_argument("--speed", default="0.95")
    ap.add_argument("--model", default="mlx-community/Kokoro-82M-bf16")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for n, text in lines(Path(args.storyboard)):
        if re.search(r"\[[^\]]*\]", text):
            print(f"skipped shot {n}: the line still has a placeholder")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, "-m", "mlx_audio.tts.generate", "--model", args.model, "--voice", args.voice,
                            "--lang_code", args.voice[0], "--speed", args.speed, "--text", text, "--file_prefix", "vo"],
                           cwd=tmp, check=True, capture_output=True)
            made = sorted(Path(tmp).glob("vo*.wav"))
            if not made:
                raise RuntimeError(f"no audio produced for shot {n}")
            shutil.move(str(made[0]), out / f"vo_{n:02d}.wav")
        print(f"wrote {out / f'vo_{n:02d}.wav'}: {text[:60]}")


if __name__ == "__main__":
    main()
