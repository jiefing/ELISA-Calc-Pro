"""Create a portable ZIP with licenses, build versions and SHA-256 checksums.
Run with the same Python environment used by build_pack.py.
"""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = "3.0.0"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    app = ROOT / "dist" / "ELISA-Calc-Pro"
    if not (app / "ELISA-Calc-Pro.exe").is_file():
        raise SystemExit("Run build_pack.py first.")
    for name in ("LICENSE", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / name, app / name)
    shutil.copyfile(ROOT / "docs" / "KNOWN_ISSUES.md", app / "KNOWN_ISSUES.md")
    license_root = app / "third-party-licenses"
    license_root.mkdir(exist_ok=True)
    versions = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        versions[name] = dist.version
        for entry in dist.files or []:
            if not any(word in entry.name.lower() for word in ("license", "licence", "copying", "notice", "copyright")):
                continue
            source = Path(dist.locate_file(entry))
            if not source.is_file() or source.suffix.lower() in (".py", ".pyc", ".pyd"):
                continue
            dest = license_root / name / Path(*[part for part in entry.parts if part not in ("..", ".")])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copyfile(python_license, license_root / "Python-LICENSE.txt")
    # The PyQt5 wheel declares GPL v3 but may omit a separate license text.
    shutil.copyfile(ROOT / "LICENSE", license_root / "PyQt5-GPL-3.0.txt")
    info = {
        "version": VERSION,
        "source": "https://github.com/jiefing/ELISA-Calc-Pro",
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "packages": dict(sorted(versions.items())),
    }
    (app / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (app / "START_HERE.txt").write_text(
        "ELISA-Calc-Pro 3.0.0 - Windows x64 portable\n"
        "Extract the entire ZIP, then run ELISA-Calc-Pro.exe.\n"
        "Keep the _internal folder beside the EXE. Python is not required.\n"
        "Read KNOWN_ISSUES.md before using calculation results.\n"
        "Custom models are saved in user_models.json beside the EXE.\n",
        encoding="utf-8",
    )
    files = sorted(p for p in app.rglob("*") if p.is_file())
    archive = ROOT / "dist" / f"ELISA-Calc-Pro-v{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in files:
            z.write(path, (Path(app.name) / path.relative_to(app)).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP integrity verification failed")
        for path in files:
            name = (Path(app.name) / path.relative_to(app)).as_posix()
            if hashlib.sha256(z.read(name)).hexdigest() != sha256(path):
                raise RuntimeError(f"Archive mismatch: {name}")
    digest = sha256(archive)
    (ROOT / "dist" / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Verified {len(files)} archived files; {archive.stat().st_size} bytes")
    print(digest)


if __name__ == "__main__":
    main()
