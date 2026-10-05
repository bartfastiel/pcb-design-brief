"""Routes a placed board with Freerouting: Specctra export, Freerouting (local Java or Docker), session import.
The session carries every track, so the board's tracks are replaced by it. Run with the Python that ships with KiCad.
  python autoroute.py board.kicad_pcb --jar freerouting.jar [--docker eclipse-temurin:25-jre] [--passes 60]"""
import argparse
import os
import shutil
import subprocess
import tempfile

import pcbnew


def run_freerouting(jar, work, passes, docker):
    args = ["-de", "board.dsn", "-do", "board.ses", "-mp", str(passes), "--gui.enabled=false"]
    if docker:
        jar_dir = os.path.dirname(os.path.abspath(jar))
        cmd = ["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", "-v", f"{jar_dir}:/fr", docker,
               "java", "-jar", "/fr/" + os.path.basename(jar)] + args
    else:
        cmd = [shutil.which("java") or "java", "-jar", os.path.abspath(jar)] + args
    result = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    with open(os.path.join(work, "freerouting.log"), "w", encoding="utf-8") as handle:
        handle.write(result.stdout + result.stderr)
    return os.path.join(work, "board.ses")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board")
    parser.add_argument("--jar", required=True, help="freerouting-x.y.z.jar")
    parser.add_argument("--docker", help="run Java in this Docker image instead of a local java")
    parser.add_argument("--passes", type=int, default=60)
    parser.add_argument("--attempts", type=int, default=5, help="Freerouting is not deterministic; retry until complete")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    for attempt in range(1, args.attempts + 1):
        board = pcbnew.LoadBoard(args.board)
        work = tempfile.mkdtemp(prefix="autoroute-")
        if not pcbnew.ExportSpecctraDSN(board, os.path.join(work, "board.dsn")):
            raise SystemExit("Specctra export failed")
        ses = run_freerouting(args.jar, work, args.passes, args.docker)
        if not os.path.exists(ses):
            raise SystemExit(f"Freerouting wrote no session; log: {os.path.join(work, 'freerouting.log')}")
        for track in list(board.GetTracks()):
            board.Delete(track)
        if not pcbnew.ImportSpecctraSES(board, ses):
            raise SystemExit("Specctra session import failed")
        board.BuildConnectivity()
        open_count = board.GetConnectivity().GetUnconnectedCount(False)
        print(f"attempt {attempt}: {open_count} unrouted, log {work}")
        if open_count == 0:
            break
    board.Save(args.output or args.board)
    print(f"routed: {sum(1 for t in board.GetTracks())} track segments and vias")


if __name__ == "__main__":
    main()
