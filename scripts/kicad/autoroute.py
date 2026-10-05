"""Routes a placed board with Freerouting: Specctra export, Freerouting (local Java or Docker), session import.
The session carries every routed track, so those are replaced by it; locked tracks (pre-routes) and tracks of ignored net
classes stay. Run with the Python that ships with KiCad.
  python autoroute.py board.kicad_pcb --jar freerouting.jar [--docker eclipse-temurin:25-jre] [--passes 60]"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew


def run_freerouting(jar, work, passes, docker, ignore):
    args = ["-de", "board.dsn", "-do", "board.ses", "-mp", str(passes), "--gui.enabled=false"]
    if ignore:
        args += ["-inc", ",".join(ignore)]
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


def drc_unconnected(board_path, ignored_nets):
    """Unconnected items KiCad finds, not counting ignored nets. Freerouting's own count is not used: it misjudges
    pre-routed islands in both directions."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from check import find_cli
    report = board_path + ".drc.json"
    subprocess.run([find_cli(None), "pcb", "drc", "--format", "json", "--severity-all", "-o", report, board_path],
                   capture_output=True)
    data = json.load(open(report, encoding="utf-8"))
    os.remove(report)
    return sum(1 for item in data.get("unconnected_items", [])
               if not any(f"[{net}]" in i.get("description", "") for i in item.get("items", []) for net in ignored_nets))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board")
    parser.add_argument("--jar", required=True, help="freerouting-x.y.z.jar")
    parser.add_argument("--docker", help="run Java in this Docker image instead of a local java")
    parser.add_argument("--passes", type=int, default=60)
    parser.add_argument("--ignore-net", action="append", default=[], help="net the router leaves alone, e.g. /GND")
    parser.add_argument("--ignore-netclass", action="append", default=[],
                        help="net class the router leaves alone, e.g. a ground connected by a pour and fan-out vias")
    parser.add_argument("--attempts", type=int, default=5, help="Freerouting is not deterministic; retry until complete")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    for attempt in range(1, args.attempts + 1):
        board = pcbnew.LoadBoard(args.board)
        ignored_nets = set(args.ignore_net) | {p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads()
                                               if p.GetNetClassName() in args.ignore_netclass}
        work = tempfile.mkdtemp(prefix="autoroute-")
        if not pcbnew.ExportSpecctraDSN(board, os.path.join(work, "board.dsn")):
            raise SystemExit("Specctra export failed")
        ses = run_freerouting(args.jar, work, args.passes, args.docker, args.ignore_netclass)
        if not os.path.exists(ses):
            raise SystemExit(f"Freerouting wrote no session; log: {os.path.join(work, 'freerouting.log')}")
        for track in list(board.GetTracks()):
            if track.GetNetname() not in ignored_nets and not track.IsLocked():
                board.Delete(track)
        kept = {(t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetLayer()) for t in board.GetTracks()}
        if not pcbnew.ImportSpecctraSES(board, ses):
            raise SystemExit("Specctra session import failed")
        seen = set()
        for track in list(board.GetTracks()):
            key = (track.GetStart().x, track.GetStart().y, track.GetEnd().x, track.GetEnd().y, track.GetLayer())
            if key in kept and not track.IsLocked() or key in seen:
                board.Delete(track)
            seen.add(key)
        board.Save(os.path.join(work, "check.kicad_pcb"))
        open_count = drc_unconnected(os.path.join(work, "check.kicad_pcb"), ignored_nets)
        print(f"attempt {attempt}: {open_count} unrouted, log {work}")
        if open_count == 0:
            break
    board.Save(args.output or args.board)
    print(f"routed: {sum(1 for t in board.GetTracks())} track segments and vias")


if __name__ == "__main__":
    main()
