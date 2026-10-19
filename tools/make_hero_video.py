"""Turn any video clip into the home page hero loop.

    python tools/make_hero_video.py "C:\\footage\\carwash_b-roll.mov"
    python tools/make_hero_video.py clip.mp4 --start 12 --duration 15
    python tools/make_hero_video.py clip.mp4 --crf 30 --width 1600      # smaller file
    python tools/make_hero_video.py clip.mp4 --webm                     # also build hero.webm

Writes into static/video/ (replacing what is there):

    hero.mp4          H.264, no audio, fast-start. Plays in every browser.
    hero-poster.jpg   One frame, shown while the video loads and to visitors who
                      prefer reduced motion or have Data Saver on.
    hero.webm         Only with --webm. VP9; often smaller for Chrome/Firefox/Edge.

Then refresh the home page - it picks the files up by itself, nothing to configure.

It never deletes or overwrites anything: any hero.mp4 / hero.webm / hero-poster.jpg
already in static/video/ is moved to brand-source/video/replaced/ first (git-ignored).
That includes running it on a big hero.mp4 you dropped in - the original is archived
and the compact version takes its place.

Why it re-encodes: a hero loop is decoration. Raw footage is hundreds of MB; the
hero loop should be a few MB - 10-20 seconds, no audio track, capped at 1920px wide
and 30fps. Keep the raw footage OUT of git (brand-source/video/ is ignored for that).

Needs ffmpeg (https://ffmpeg.org) on PATH, or at C:\\ffmpeg\\bin.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "static", "video")
ARCHIVE_DIR = os.path.join(ROOT, "brand-source", "video", "replaced")   # git-ignored
FFMPEG_FALLBACKS = [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]

IDEAL_MB = 8
TOO_HEAVY_MB = 15


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for path in FFMPEG_FALLBACKS:
        if os.path.isfile(path):
            return path
    sys.exit("ffmpeg not found. Install it (https://ffmpeg.org/download.html) and make sure "
             "'ffmpeg' works in a terminal, then run this again.")


def run(cmd, label):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed while making {label}:\n{result.stderr[-1500:]}")


def size_mb(path):
    return os.path.getsize(path) / 1048576


def rel(path):
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:          # different drive: just show the full path
        return path


def same_file(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def archive(path, archive_dir):
    """Move an existing file out of the way. Nothing this script touches is ever deleted."""
    os.makedirs(archive_dir, exist_ok=True)
    dest = os.path.join(archive_dir, time.strftime("%Y%m%d-%H%M%S-") + os.path.basename(path))
    shutil.move(path, dest)
    return dest


def main():
    ap = argparse.ArgumentParser(
        description="Make the home page hero loop (static/video/) from any video file.",
        epilog="Example: python tools/make_hero_video.py footage.mov --start 12 --duration 15")
    ap.add_argument("source", help="the video file to turn into a hero loop")
    ap.add_argument("--start", type=float, default=0, help="seconds into the source to start (default 0)")
    ap.add_argument("--duration", type=float, default=15,
                    help="length of the loop in seconds (default 15; a shorter source uses what it has)")
    ap.add_argument("--width", type=int, default=1920, help="max width in pixels (default 1920)")
    ap.add_argument("--fps", type=int, default=30, help="max frames per second (default 30)")
    ap.add_argument("--crf", type=int, default=27,
                    help="quality: lower = sharper and bigger (default 27; try 30 for a smaller file)")
    ap.add_argument("--webm", action="store_true", help="also build hero.webm (slower to encode)")
    ap.add_argument("--poster-at", type=float, default=0.5,
                    help="which second of the loop to use for the poster image (default 0.5)")
    ap.add_argument("--outdir", default=OUT_DIR, help="where to write (default static/video/)")
    args = ap.parse_args()

    if not os.path.isfile(args.source):
        sys.exit(f"Cannot find the source video: {args.source}")
    ffmpeg = find_ffmpeg()
    os.makedirs(args.outdir, exist_ok=True)

    mp4 = os.path.join(args.outdir, "hero.mp4")
    webm = os.path.join(args.outdir, "hero.webm")
    poster = os.path.join(args.outdir, "hero-poster.jpg")
    scale = f"scale='min({args.width},iw)':-2,format=yuv420p"   # -2 keeps the height even

    # Never overwrite: move anything already there aside first. This covers a big
    # hero.mp4 you dropped in and then ran this on - the source IS the output, so
    # it is archived and encoded from the archived copy. A stale hero.webm is
    # archived too, or the page would keep serving the old video to Chrome/Firefox.
    default_dir = os.path.normcase(os.path.abspath(args.outdir)) == os.path.normcase(os.path.abspath(OUT_DIR))
    archive_dir = ARCHIVE_DIR if default_dir else os.path.join(args.outdir, "_replaced")
    source = args.source
    for path in (mp4, webm, poster):
        if os.path.exists(path):
            dest = archive(path, archive_dir)
            print(f"Archived existing {os.path.basename(path)} -> {rel(dest)}")
            if same_file(source, path):
                source = dest

    base = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(args.start), "-i", source, "-t", str(args.duration), "-an", "-vf", scale]

    print(f"Encoding hero.mp4 from {os.path.basename(args.source)} "
          f"(start {args.start:g}s, up to {args.duration:g}s) ...")
    mp4_cmd = base + ["-fpsmax", str(args.fps), "-c:v", "libx264", "-preset", "slow",
                      "-crf", str(args.crf), "-profile:v", "high", "-movflags", "+faststart", mp4]
    result = subprocess.run(mp4_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0 and "fpsmax" in result.stderr:
        # Older ffmpeg without -fpsmax: cap the frame rate with the fps filter instead.
        mp4_cmd = base[:-1] + [scale + f",fps={args.fps}", "-c:v", "libx264", "-preset", "slow",
                               "-crf", str(args.crf), "-profile:v", "high", "-movflags", "+faststart", mp4]
        run(mp4_cmd, "hero.mp4")
    elif result.returncode != 0:
        sys.exit(f"ffmpeg failed while making hero.mp4:\n{result.stderr[-1500:]}")

    print("Making hero-poster.jpg ...")
    run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(args.poster_at), "-i", mp4,
         "-frames:v", "1", "-update", "1",
         "-vf", f"scale='min({min(args.width, 1600)},iw)':-2", "-q:v", "4", poster], "hero-poster.jpg")

    if args.webm:
        print("Encoding hero.webm (VP9 - this one takes a while) ...")
        run(base + ["-fpsmax", str(args.fps), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(args.crf + 6),
                    "-row-mt", "1", webm], "hero.webm")

    print("\nDone:")
    for path in (mp4, poster) + ((webm,) if args.webm else ()):
        print(f"  {rel(path):32s} {size_mb(path):6.2f} MB")

    mb = size_mb(mp4)
    if mb > TOO_HEAVY_MB:
        print(f"\nhero.mp4 is {mb:.0f} MB - too heavy for a hero loop. Try: --crf 31 --width 1600, "
              "or a shorter --duration.")
    elif mb > IDEAL_MB:
        print(f"\nhero.mp4 is {mb:.1f} MB - works, but lighter is better (aim for under {IDEAL_MB} MB). "
              "Try --crf 30 or a shorter --duration.")
    else:
        print(f"\nhero.mp4 is {mb:.1f} MB - a good size.")
    print("Refresh the home page to see it. Commit static/video/ when you are happy with it.")


if __name__ == "__main__":
    main()
