#!/usr/bin/env python3
"""
Prepare and install the Proxmox automated installer ISO for PXE boot.

Safe default:
  writes under /tmp/recovery-pxe-test unless --pxe-web-root is provided.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ISO_INDEX_URL = "https://enterprise.proxmox.com/iso/"
DEFAULT_TEST_ROOT = Path("/tmp/recovery-pxe-test")
DEFAULT_ANSWER_URL = "http://recovery-server/answer"
DEFAULT_PXE_BASE_URL = "http://recovery-server/pxe/proxmox"


@dataclass(frozen=True)
class ProxmoxIso:
    filename: str
    url: str
    sha256: str


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def info(message: str) -> None:
    print(message, flush=True)


def fetch_text(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        fail(f"could not fetch {url}: {exc.reason}")


def find_latest_iso(index_url: str) -> ProxmoxIso:
    html = fetch_text(index_url)
    matches = re.findall(
        r"(proxmox-ve_([0-9][^<\s]+)\.iso).*?SHA256:\s*([a-fA-F0-9]{64})",
        html,
        flags=re.DOTALL,
    )
    if not matches:
        fail(f"could not find any Proxmox VE ISO entries in {index_url}")

    def version_key(match: tuple[str, str, str]) -> tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", match[1]))

    filename, _version, sha256 = sorted(matches, key=version_key, reverse=True)[0]
    return ProxmoxIso(
        filename=filename,
        url=urllib.request.urljoin(index_url, filename),
        sha256=sha256.lower(),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except urllib.error.URLError as exc:
        fail(f"could not download {url}: {exc.reason}")
    tmp.replace(output)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run(command: list[str], dry_run: bool) -> None:
    printable = " ".join(shlex_quote(part) for part in command)
    if dry_run:
        info(f"would run: {printable}")
        return
    info(f"running: {printable}")
    subprocess.run(command, check=True)


def shlex_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def read_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        fail(f"manifest is not valid JSON: {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"manifest is not a JSON object: {path}")
    return data


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def pxe_paths(pxe_web_root: Path) -> dict[str, Path]:
    proxmox_dir = pxe_web_root / "proxmox"
    return {
        "pxe_web_root": pxe_web_root,
        "proxmox_dir": proxmox_dir,
        "manifest": proxmox_dir / "manifest.json",
        "prepared_iso": proxmox_dir / "proxmox-auto.iso",
        "vmlinuz": proxmox_dir / "vmlinuz",
        "initrd": proxmox_dir / "initrd",
        "ipxe_script": pxe_web_root / "auto-proxmox.ipxe",
    }


def render_ipxe_script(pxe_base_url: str) -> str:
    return "\n".join(
        [
            "#!ipxe",
            "dhcp",
            f"set pxe_base {pxe_base_url.rstrip('/')}",
            "imgfree",
            "kernel ${pxe_base}/vmlinuz vga=791 video=vesafb:ywrap,mtrr ramdisk_size=16777216 rw quiet splash=silent proxmox-start-auto-installer initrd=initrd.magic",
            "initrd ${pxe_base}/initrd",
            "initrd ${pxe_base}/proxmox-auto.iso /proxmox.iso",
            "boot",
            "",
        ]
    )


def assistant_version() -> str | None:
    binary = shutil.which("proxmox-auto-install-assistant")
    if binary is None:
        return None
    for args in (["--version"], ["version"]):
        try:
            completed = subprocess.run(
                [binary, *args],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError:
            continue
        output = completed.stdout.strip().splitlines()
        if output:
            return output[0]
    return "installed"


def choose_extractor() -> str | None:
    for name in ("xorriso", "bsdtar", "7z"):
        if command_exists(name):
            return name
    return None


def extract_boot_files(prepared_iso: Path, output_dir: Path, dry_run: bool) -> None:
    extractor = choose_extractor()
    if extractor is None:
        if dry_run:
            extractor = "xorriso"
        else:
            fail("missing ISO extractor; install xorriso, bsdtar, or 7z")

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
    vmlinuz = output_dir / "vmlinuz"
    initrd = output_dir / "initrd"

    if extractor == "xorriso":
        run(
            [
                "xorriso",
                "-osirrox",
                "on",
                "-indev",
                str(prepared_iso),
                "-extract",
                "/boot/linux26",
                str(vmlinuz),
                "-extract",
                "/boot/initrd.img",
                str(initrd),
            ],
            dry_run,
        )
    elif extractor == "bsdtar":
        with tempfile.TemporaryDirectory(prefix="proxmox-iso-extract-") as tmp_name:
            tmp = Path(tmp_name)
            run(["bsdtar", "-xf", str(prepared_iso), "-C", str(tmp), "boot/linux26", "boot/initrd.img"], dry_run)
            if not dry_run:
                shutil.copy2(tmp / "boot" / "linux26", vmlinuz)
                shutil.copy2(tmp / "boot" / "initrd.img", initrd)
    else:
        with tempfile.TemporaryDirectory(prefix="proxmox-iso-extract-") as tmp_name:
            tmp = Path(tmp_name)
            run(["7z", "x", f"-o{tmp}", str(prepared_iso), "boot/linux26", "boot/initrd.img"], dry_run)
            if not dry_run:
                shutil.copy2(tmp / "boot" / "linux26", vmlinuz)
                shutil.copy2(tmp / "boot" / "initrd.img", initrd)


def install_staged(staged: dict[str, Path], live: dict[str, Path], manifest: dict, dry_run: bool) -> None:
    for key in ("prepared_iso", "vmlinuz", "initrd", "ipxe_script"):
        if not staged[key].exists() and not dry_run:
            fail(f"staged file is missing: {staged[key]}")

    if dry_run:
        info(f"would install staged files into {live['pxe_web_root']}")
        return

    live["proxmox_dir"].mkdir(parents=True, exist_ok=True)
    live["pxe_web_root"].mkdir(parents=True, exist_ok=True)

    backup_dir = live["proxmox_dir"] / "previous"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for key in ("prepared_iso", "vmlinuz", "initrd"):
        destination = live[key]
        if destination.exists():
            shutil.move(str(destination), str(backup_dir / destination.name))

    for key in ("prepared_iso", "vmlinuz", "initrd", "ipxe_script"):
        shutil.copy2(staged[key], live[key])

    write_manifest(live["manifest"], manifest)


def manifest_current(manifest: dict, latest: ProxmoxIso, answer_url: str, pxe_base_url: str) -> bool:
    return (
        manifest.get("stock_iso_filename") == latest.filename
        and manifest.get("stock_iso_sha256") == latest.sha256
        and manifest.get("answer_url") == answer_url
        and manifest.get("pxe_base_url") == pxe_base_url
    )


def print_status(latest: ProxmoxIso, manifest: dict, paths: dict[str, Path], answer_url: str, pxe_base_url: str) -> None:
    info(f"Latest upstream ISO: {latest.filename}")
    info(f"Upstream SHA256:     {latest.sha256}")
    info(f"Download URL:        {latest.url}")
    info("")
    info(f"PXE web root:        {paths['pxe_web_root']}")
    info(f"Answer URL:          {answer_url}")
    info(f"PXE base URL:        {pxe_base_url}")
    info(f"Manifest:            {paths['manifest']}")
    if manifest:
        info(f"Installed ISO:       {manifest.get('stock_iso_filename', 'unknown')}")
        info(f"Installed SHA256:    {manifest.get('stock_iso_sha256', 'unknown')}")
        if manifest_current(manifest, latest, answer_url, pxe_base_url):
            info("Status:              current")
        else:
            info("Status:              update needed")
    else:
        info("Installed ISO:       none")
        info("Status:              install needed")


def prepare(args: argparse.Namespace) -> None:
    pxe_web_root = args.pxe_web_root
    work_dir = args.work_dir
    downloads_dir = work_dir / "downloads"
    staging_root = work_dir / "staging"
    staged_pxe_root = staging_root / "pxe"
    live_paths = pxe_paths(pxe_web_root)
    staged_paths = pxe_paths(staged_pxe_root)

    latest = find_latest_iso(args.iso_index_url)
    current_manifest = read_manifest(live_paths["manifest"])

    if not args.force and manifest_current(current_manifest, latest, args.answer_url, args.pxe_base_url):
        required = ("prepared_iso", "vmlinuz", "initrd", "ipxe_script")
        if all(live_paths[key].exists() for key in required):
            info("PXE ISO assets are already current. Use --force to rebuild.")
            return

    print_status(latest, current_manifest, live_paths, args.answer_url, args.pxe_base_url)
    info("")

    if not args.dry_run:
        missing_tools = []
        if not command_exists("proxmox-auto-install-assistant"):
            missing_tools.append("proxmox-auto-install-assistant")
        if choose_extractor() is None:
            missing_tools.append("xorriso, bsdtar, or 7z")
        if missing_tools:
            fail("missing required tool(s): " + "; ".join(missing_tools))

    stock_iso = downloads_dir / latest.filename
    if args.dry_run:
        info(f"would download stock ISO to {stock_iso}")
    else:
        if stock_iso.exists():
            info(f"stock ISO already exists: {stock_iso}")
        else:
            info(f"downloading {latest.url}")
            download_file(latest.url, stock_iso)
        actual_sha = sha256_file(stock_iso)
        if actual_sha != latest.sha256:
            fail(f"checksum mismatch for {stock_iso}: expected {latest.sha256}, got {actual_sha}")
        info("stock ISO checksum ok")

    if not args.dry_run:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staged_paths["proxmox_dir"].mkdir(parents=True, exist_ok=True)

    run(
        [
            "proxmox-auto-install-assistant",
            "prepare-iso",
            str(stock_iso),
            "--fetch-from",
            "http",
            "--url",
            args.answer_url,
            "--output",
            str(staged_paths["prepared_iso"]),
        ],
        args.dry_run,
    )

    if not args.dry_run:
        prepared_sha = sha256_file(staged_paths["prepared_iso"])
    else:
        prepared_sha = "dry-run"

    extract_boot_files(staged_paths["prepared_iso"], staged_paths["proxmox_dir"], args.dry_run)

    ipxe_text = render_ipxe_script(args.pxe_base_url)
    if args.dry_run:
        info(f"would write {staged_paths['ipxe_script']}")
    else:
        staged_paths["ipxe_script"].write_text(ipxe_text, encoding="utf-8")

    new_manifest = {
        "answer_url": args.answer_url,
        "prepared_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "prepared_iso_sha256": prepared_sha,
        "proxmox_auto_install_assistant": assistant_version() or "not-detected",
        "pxe_base_url": args.pxe_base_url,
        "source_index_url": args.iso_index_url,
        "stock_iso_filename": latest.filename,
        "stock_iso_sha256": latest.sha256,
        "stock_iso_url": latest.url,
    }

    install_staged(staged_paths, live_paths, new_manifest, args.dry_run)
    if not args.dry_run:
        info(f"installed PXE ISO assets under {pxe_web_root}")


def check(args: argparse.Namespace) -> None:
    latest = find_latest_iso(args.iso_index_url)
    paths = pxe_paths(args.pxe_web_root)
    manifest = read_manifest(paths["manifest"])
    print_status(latest, manifest, paths, args.answer_url, args.pxe_base_url)

    info("")
    info("Local tools:")
    info(f"  proxmox-auto-install-assistant: {'yes' if command_exists('proxmox-auto-install-assistant') else 'missing'}")
    info(f"  ISO extractor:                  {choose_extractor() or 'missing'}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage the prepared Proxmox automated installer ISO for PXE boot.",
    )
    parser.add_argument(
        "--pxe-web-root",
        type=Path,
        default=Path(os.environ.get("PXE_WEB_ROOT", DEFAULT_TEST_ROOT / "www" / "pxe")),
        help="PXE HTTP root containing auto-proxmox.ipxe and proxmox/. Defaults to a /tmp test root.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.environ.get("WORK_DIR", DEFAULT_TEST_ROOT / "work")),
        help="Working directory for downloads and staging.",
    )
    parser.add_argument(
        "--answer-url",
        default=os.environ.get("ANSWER_URL", DEFAULT_ANSWER_URL),
        help="Answer endpoint to embed into the prepared ISO.",
    )
    parser.add_argument(
        "--pxe-base-url",
        default=os.environ.get("PXE_BASE_URL", DEFAULT_PXE_BASE_URL),
        help="Base HTTP URL used by iPXE to fetch Proxmox boot assets.",
    )
    parser.add_argument(
        "--iso-index-url",
        default=os.environ.get("ISO_INDEX_URL", ISO_INDEX_URL),
        help="Proxmox ISO index URL.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="Show latest upstream ISO and local PXE asset status.")

    prepare_parser = subparsers.add_parser("prepare", help="Download, prepare, stage, and install PXE ISO assets.")
    prepare_parser.add_argument("--dry-run", action="store_true", help="Print actions without downloading or installing.")
    prepare_parser.add_argument("--force", action="store_true", help="Rebuild even if the manifest looks current.")

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.command == "check":
            check(args)
        elif args.command == "prepare":
            prepare(args)
        else:
            fail(f"unknown command: {args.command}")
    except KeyboardInterrupt:
        fail("interrupted")
    except subprocess.CalledProcessError as exc:
        fail(f"command failed with exit {exc.returncode}: {' '.join(exc.cmd)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
