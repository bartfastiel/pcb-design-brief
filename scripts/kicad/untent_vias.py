"""Removes the solder mask from every via on both sides (rule HS-5), including vias a router created.
Run with the Python that ships with KiCad 9 or newer."""
import argparse

import pcbnew


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", help=".kicad_pcb")
    parser.add_argument("-o", "--output", help="write here instead of overwriting the input")
    args = parser.parse_args()

    board = pcbnew.LoadBoard(args.board)
    count = 0
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T:
            track.SetFrontTentingMode(pcbnew.TENTING_MODE_NOT_TENTED)
            track.SetBackTentingMode(pcbnew.TENTING_MODE_NOT_TENTED)
            count += 1
    board.Save(args.output or args.board)
    print(f"{count} vias untented")


if __name__ == "__main__":
    main()
