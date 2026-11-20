import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def mocked_backup_environment(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mock_s3 = tmp_path / "mock-s3"
    mock_s3.mkdir()
    backup_dir = tmp_path / "backups"

    write_executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
set -eu
case "$*" in
  *pg_dump*) printf 'mock-postgresql-dump\\n' ;;
  *pg_restore*) exit 0 ;;
  *"compose cp"*) exit 0 ;;
  *"rm -f"*) exit 0 ;;
  *) exit 0 ;;
esac
""",
    )
    write_executable(
        bin_dir / "aws",
        """#!/usr/bin/env python3
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
if len(args) < 4 or args[:2] != ["s3", "cp"]:
    raise SystemExit("unexpected mock aws command")
source, destination = args[2], args[3]
root = Path(os.environ["MOCK_S3_ROOT"])

def local_s3_path(uri):
    if not uri.startswith("s3://"):
        raise SystemExit("not an S3 URI")
    return root / uri[5:]

if source.startswith("s3://"):
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_s3_path(source), target)
else:
    target = local_s3_path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
""",
    )

    env = dict(os.environ)
    env.update(
        {
            "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
            "MOCK_S3_ROOT": str(mock_s3),
            "BACKUP_DIR": str(backup_dir),
            "OFFSITE_S3_URI": "s3://officeflow-test-bucket/officeflow",
            "OFFSITE_S3_SSE": "AES256",
        }
    )
    return env, backup_dir, mock_s3


def test_offsite_backup_uploads_and_verifies_dump_and_checksum(mocked_backup_environment):
    env, backup_dir, mock_s3 = mocked_backup_environment
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/backup-offsite.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OFFSITE_BACKUP_OK" in result.stdout
    dumps = list(backup_dir.glob("officeflow-*.dump"))
    assert len(dumps) == 1
    remote_dump = mock_s3 / "officeflow-test-bucket/officeflow" / dumps[0].name
    remote_checksum = Path(str(remote_dump) + ".sha256")
    assert remote_dump.read_bytes() == dumps[0].read_bytes()
    assert remote_checksum.is_file()


def test_offsite_backup_requires_s3_destination(mocked_backup_environment):
    env, _, _ = mocked_backup_environment
    env.pop("OFFSITE_S3_URI")
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/backup-offsite.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "Set OFFSITE_S3_URI" in result.stderr


def test_offsite_backup_rejects_unknown_encryption_mode(mocked_backup_environment):
    env, _, _ = mocked_backup_environment
    env["OFFSITE_S3_SSE"] = "NONE"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/backup-offsite.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    assert "must be AES256 or aws:kms" in result.stderr


def test_offsite_backup_requires_kms_key_when_kms_selected(mocked_backup_environment):
    env, _, _ = mocked_backup_environment
    env["OFFSITE_S3_SSE"] = "aws:kms"
    env.pop("OFFSITE_S3_KMS_KEY_ID", None)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/backup-offsite.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "Set OFFSITE_S3_KMS_KEY_ID" in result.stderr


def test_offsite_backup_script_passes_bash_syntax_check():
    result = subprocess.run(
        ["bash", "-n", str(ROOT / "scripts/backup-offsite.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
