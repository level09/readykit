import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
PYTHON_CANDIDATES = ("python3.14", "python3.13", "python3.12", "python3.11", "python3")


def _write_executable(path, contents):
    path.write_text(contents)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_python_candidates(bin_dir, supported_name=None):
    for name in PYTHON_CANDIDATES:
        supported = name == supported_name
        version = "3.14.0" if supported else "3.10.14"
        _write_executable(
            bin_dir / name,
            (
                "#!/bin/sh\n"
                f'if [ "$1" = "-c" ]; then exit {0 if supported else 1}; fi\n'
                f"printf 'Python {version}\\n'\n"
            ),
        )


def _run_setup(tmp_path, path, answer="n\n"):
    shutil.copy(PROJECT_ROOT / "setup.sh", tmp_path / "setup.sh")
    shutil.copy(PROJECT_ROOT / ".env-sample", tmp_path / ".env-sample")

    return subprocess.run(
        ["bash", "setup.sh"],
        cwd=tmp_path,
        env={**os.environ, "PATH": path},
        input=answer,
        capture_output=True,
        text=True,
        check=False,
    )


def test_setup_rejects_unsupported_python(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_python_candidates(bin_dir)
    _write_executable(bin_dir / "uv", "#!/bin/sh\nexit 0\n")

    result = _run_setup(tmp_path, f"{bin_dir}:/usr/bin:/bin")

    assert result.returncode != 0
    assert "Python 3.11 or newer is required" in result.stdout


@pytest.mark.parametrize("python_name", ["python3", "python3.14"])
def test_setup_installs_full_dependencies_with_selected_python(tmp_path, python_name):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_python_candidates(bin_dir, supported_name=python_name)
    _write_executable(
        bin_dir / "uv",
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > uv-args.txt\n",
    )

    result = _run_setup(tmp_path, f"{bin_dir}:/usr/bin:/bin")
    assert result.returncode == 0, result.stdout + result.stderr

    uv_args = (tmp_path / "uv-args.txt").read_text().splitlines()
    assert uv_args == [
        "sync",
        "--python",
        str(bin_dir / python_name),
        "--extra",
        "dev",
        "--extra",
        "full",
    ]


def test_setup_configures_local_sessions_for_the_application(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_python_candidates(bin_dir, supported_name="python3")
    _write_executable(bin_dir / "uv", "#!/bin/sh\nexit 0\n")

    result = _run_setup(tmp_path, f"{bin_dir}:/usr/bin:/bin")
    assert result.returncode == 0, result.stdout + result.stderr

    config_result = subprocess.run(
        [
            str(PROJECT_ROOT / ".venv/bin/python"),
            "-c",
            (
                "from enferno.settings import Config; "
                "print(Config.SESSION_TYPE); "
                "print(Config.SESSION_COOKIE_SECURE)"
            ),
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(PROJECT_ROOT),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert config_result.returncode == 0, config_result.stderr
    assert config_result.stdout.splitlines() == ["redis", "False"]


def test_setup_keeps_secure_cookies_for_docker(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_python_candidates(bin_dir, supported_name="python3")
    _write_executable(bin_dir / "uv", "#!/bin/sh\nexit 0\n")

    result = _run_setup(tmp_path, f"{bin_dir}:/usr/bin:/bin", answer="y\n")
    assert result.returncode == 0, result.stdout + result.stderr

    config = (tmp_path / ".env").read_text()
    assert "SESSION_COOKIE_SECURE=True" in config
