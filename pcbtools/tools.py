"""Finds the external programs the pipeline needs, so neither the agent nor the user types paths. Environment variables
win over the search: KICAD_CLI, KICAD_PYTHON, BLENDER, FREEROUTING_JAR, FREEROUTING_DOCKER."""
import glob
import importlib.util
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")


def first(candidates):
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def kicad_cli():
    return first([os.environ.get("KICAD_CLI"), shutil.which("kicad-cli")]
                 + sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"), reverse=True)
                 + sorted(glob.glob(HOME + r"\AppData\Local\Programs\KiCad\*\bin\kicad-cli.exe"), reverse=True)
                 + ["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"])


def kicad_python():
    """The interpreter that can import pcbnew: this one, KiCad's own on Windows and macOS, or the system's on Linux."""
    if importlib.util.find_spec("pcbnew"):
        return sys.executable
    cli = kicad_cli()
    candidates = [os.environ.get("KICAD_PYTHON")]
    if cli:
        candidates += [os.path.join(os.path.dirname(cli), "python.exe"),
                       "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"]
    candidates += ["/usr/bin/python3"]
    for path in candidates:
        if path and os.path.isfile(path):
            probe = subprocess.run([path, "-c", "import pcbnew"], capture_output=True)
            if probe.returncode == 0:
                return path
    return None


def kicad_share():
    """Symbol and footprint library directories of the installed KiCad."""
    cli = kicad_cli()
    roots = []
    if cli:
        roots += [os.path.join(os.path.dirname(os.path.dirname(cli)), "share", "kicad"),
                  os.path.join(os.path.dirname(cli), "..", "SharedSupport")]
    roots += ["/usr/share/kicad", "/usr/local/share/kicad"]
    env = {"symbols": os.environ.get("KICAD_SYMBOL_DIR"), "footprints": os.environ.get("KICAD_FOOTPRINT_DIR")}
    for root in roots:
        if os.path.isdir(os.path.join(root, "symbols")):
            env["symbols"] = env["symbols"] or os.path.join(root, "symbols")
            env["footprints"] = env["footprints"] or os.path.join(root, "footprints")
            break
    return env


def blender():
    return first([os.environ.get("BLENDER"), shutil.which("blender")]
                 + sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
                 + sorted(glob.glob(HOME + r"\tools\blender-*\blender.exe"), reverse=True)
                 + ["/Applications/Blender.app/Contents/MacOS/Blender"])


def freerouting():
    """The jar, and how to run Java: a local java, or a Docker image when none is installed."""
    jar = first([os.environ.get("FREEROUTING_JAR")]
                + sorted(glob.glob(HOME + "/tools/freerouting*/freerouting-*.jar"), reverse=True)
                + sorted(glob.glob(HOME + "/tools/freerouting-*.jar"), reverse=True))
    java = shutil.which("java")
    docker = os.environ.get("FREEROUTING_DOCKER") or ("eclipse-temurin:25-jre" if not java and shutil.which("docker")
                                                      else None)
    return jar, java, docker


PYTHON_MODULES = ["numpy", "PIL", "trimesh", "manifold3d", "shapely", "reportlab", "pymupdf"]


def report():
    """Each tool and whether it was found; returns True when everything for a full build is there."""
    jar, java, docker = freerouting()
    share = kicad_share()
    rows = [("kicad-cli", kicad_cli(), "KiCad 8 or newer, https://www.kicad.org"),
            ("KiCad Python (pcbnew)", kicad_python(), "comes with KiCad; on Linux the system python3"),
            ("KiCad symbols", share["symbols"], "set KICAD_SYMBOL_DIR"),
            ("KiCad footprints", share["footprints"], "set KICAD_FOOTPRINT_DIR"),
            ("Freerouting jar", jar, "https://github.com/freerouting/freerouting/releases, set FREEROUTING_JAR"),
            ("Java or Docker", java or (docker and f"docker {docker}"), "a Java 21+ runtime, or Docker"),
            ("Blender", blender(), "https://www.blender.org (portable zip is fine), set BLENDER")]
    for module in PYTHON_MODULES:
        found = importlib.util.find_spec(module)
        rows.append((f"python: {module}", found and found.origin, "pip install -r requirements.txt"))
    ok = True
    for name, value, hint in rows:
        print(f"{'ok ' if value else 'MISSING'}  {name:24} {value or hint}")
        ok = ok and bool(value)
    return ok
