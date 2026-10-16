"""Cut the demo video from the rendered shots and the voice-over (the edit decision list is below).

    python submission/assemble_video.py --dir submission/video --out submission/video/shelfcast_demo.mp4

Inputs come from build_video_cards.py (type-on-black shots), record_dashboard.py (product shots) and
build_voice.py (voice-over). Each segment is one storyboard shot: its clip is trimmed to the moment
the subject appears, held on its last frame if the voice runs longer, and laid over the voice line.
Sound follows the storyboard: a quiet pad under the opening, silence before the wow shot, one soft
tone when the order lands. Every sound is synthesised here; nothing is downloaded.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

# (segment, [(clip, start_s, length_s or None for the rest)], voice line, voice offset_s, segment length_s)
# Product shots get their storyboard caption here; the type-on-black shots carry their own.
EDL = [
    ("01", [("shot_01.mp4", 0, None)], "vo_01.wav", 0.8, 7.0),
    ("02", [("shot_02.mp4", 0, None)], "vo_02.wav", 0.6, 6.5),
    ("03", [("shot_03.mp4", 0, None)], "vo_03.wav", 1.0, 10.5),
    ("04", [("shot_04.mp4", 0, None)], None, 0, 2.0),
    ("05", [("shot_05.mp4", 0, None)], "vo_05.wav", 0.4, 14.5),
    ("06", [("shot_06.mp4", 0.2, None)], "vo_06.wav", 0.5, 6.5),
    ("07", [("shot_07.mp4", 7.0, None)], "vo_07.wav", 0.3, 9.5),
    ("08", [("shot_08.mp4", 0, None)], "vo_08.wav", 0.6, 14.5),
    ("09", [("shot_09.mp4", 0, None)], "vo_09.wav", 0.5, 10.0),
    ("10", [("shot_10.mp4", 0, None)], "vo_10.wav", 0.6, 11.0),
    ("11", [("shot_11a.mp4", 0, 5.0), ("shot_11b.mp4", 0, None)], "vo_11.wav", 0.5, 15.5),
    ("12", [("shot_12.mp4", 0, None)], "vo_12.wav", 0.6, 7.0),
    ("13", [("shot_13.mp4", 0, None)], "vo_13.wav", 0.8, 8.0),
]
CAPTIONS = {"03": "The system forecast: 21.", "05": "Order 40, not 21.", "06": "Every change has a reason.",
            "07": "It reads what you know."}
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
TONE_AT = ("05", 10.2)          # the order tile finishes counting up
PAD_UNTIL = ("04", 0.0)         # the pad fades out into the silent beat
FPS, RATE = 30, 48000


def run(ffmpeg: str, *args: str) -> None:
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", *args], check=True)


def segment(ffmpeg: str, src: Path, tmp: Path, name: str, clips, voice, offset: float, length: float) -> Path:
    inputs, vparts = [], []
    remaining = length
    for i, (clip, start, dur) in enumerate(clips):
        take = remaining if dur is None or i == len(clips) - 1 else min(dur, remaining)
        inputs += ["-ss", str(start), "-i", str(src / clip)]
        vparts.append(f"[{i}:v]fps={FPS},scale=1920:1080,setsar=1,tpad=stop_mode=clone:stop_duration={take},"
                      f"trim=duration={take},setpts=PTS-STARTPTS[v{i}]")
        remaining -= take
    n = len(clips)
    graph = ";".join(vparts) + ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0"
    if name in CAPTIONS:
        txt = tmp / f"cap_{name}.txt"
        txt.write_text(CAPTIONS[name])
        graph += (f",drawtext=fontfile={FONT}:textfile={txt}:fontsize=34:fontcolor=0x8c96a5:x=96:y=h-84-th:"
                  f"alpha='min(1,max(0,(t-1.2)/0.8))'")
    graph += "[v]"
    if voice:
        inputs += ["-i", str(src / voice)]
        ms = int(offset * 1000)
        graph += (f";[{n}:a]aresample={RATE},aformat=channel_layouts=stereo,adelay={ms}|{ms},"
                  f"apad=whole_dur={length},atrim=duration={length}[a]")
    else:
        inputs += ["-f", "lavfi", "-t", str(length), "-i", f"anullsrc=r={RATE}:cl=stereo"]
        graph += f";[{n}:a]atrim=duration={length}[a]"
    out = tmp / f"seg_{name}.mp4"
    run(ffmpeg, *inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-crf", "17", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-t", str(length), str(out))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="submission/video")
    ap.add_argument("--out", default="submission/video/shelfcast_demo.mp4")
    args = ap.parse_args()

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    src = Path(args.dir)
    starts, t = {}, 0.0
    for name, *_rest, length in EDL:
        starts[name] = t
        t += length
    total = t
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        segs = [segment(ffmpeg, src, tmp, name, clips, voice, off, length)
                for name, clips, voice, off, length in EDL]
        listing = tmp / "list.txt"
        listing.write_text("".join(f"file '{s}'\n" for s in segs))
        joined = tmp / "joined.mp4"
        run(ffmpeg, "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined))

        pad_end = starts[PAD_UNTIL[0]] + PAD_UNTIL[1]
        tone = starts[TONE_AT[0]] + TONE_AT[1]
        # A low, sparse pad (A2, E3, A3) that swells in and fades out before the silent beat.
        pad = (f"aevalsrc='0.05*sin(2*PI*110*t)+0.035*sin(2*PI*164.81*t)+0.025*sin(2*PI*220*t)':s={RATE}:d={pad_end},"
               f"afade=t=in:d=3,afade=t=out:st={pad_end - 3}:d=3,aformat=channel_layouts=stereo")
        # One soft bell-like tone when the order lands.
        bell = (f"aevalsrc='0.18*exp(-3*t)*(sin(2*PI*660*t)+0.5*sin(2*PI*990*t))':s={RATE}:d=1.6,"
                f"aformat=channel_layouts=stereo,adelay={int(tone * 1000)}|{int(tone * 1000)}")
        graph = (f"{pad}[pad];{bell}[bell];[0:a][pad][bell]amix=inputs=3:duration=first:normalize=0,"
                 f"loudnorm=I=-16:TP=-1.5:LRA=11[a];"
                 f"[0:v]fade=t=in:d=0.6,fade=t=out:st={total - 1.2}:d=1.2[v]")
        run(ffmpeg, "-i", str(joined), "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.out)
    print(f"wrote {args.out}: {total:.1f}s")


if __name__ == "__main__":
    main()
