import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pi_haiku.environment_detector import (
    EnvironmentDetectionError,
    EnvironmentDetector,
    EnvType,
    PyPackage,
)


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def mock_package(temp_dir):
    package_path = temp_dir / "mock_package"
    package_path.mkdir()
    return PyPackage(
        name="mock_package",
        version="0.1.0",
        path=package_path,
        dependencies={},
        toml_data={}
    )


@pytest.fixture
def mock_venv_path(temp_dir):
    venv_path = temp_dir / ".venv"
    (venv_path / "bin").mkdir(parents=True)
    (venv_path / "bin" / "activate").touch()
    return venv_path


@pytest.fixture
def mock_conda_path(temp_dir):
    conda_path = temp_dir / "conda"
    (conda_path / "envs" / "mock_package" / "bin").mkdir(parents=True)
    (conda_path / "envs" / "mock_package" / "bin" / "activate").touch()
    return conda_path


def test_detect_venv(mock_package, mock_venv_path):
    detector = EnvironmentDetector(package=mock_package, venv_path=mock_venv_path)
    r = detector.detect_environment()
    env_type, activate_cmd = r.env_type, r.activate_command
    assert env_type == EnvType.VENV
    assert str(mock_venv_path / "bin" / "activate") in activate_cmd


def test_detect_conda(mock_package, mock_conda_path):
    detector = EnvironmentDetector(package=mock_package, conda_base_path=mock_conda_path)
    r = detector.detect_environment()
    env_type, activate_cmd = r.env_type, r.activate_command
    assert env_type == EnvType.CONDA
    assert "conda activate mock_package" in activate_cmd


def test_no_environment_found(mock_package):
    detector = EnvironmentDetector(package=mock_package)
    with pytest.raises(EnvironmentDetectionError):
        detector.detect_environment()


@patch("os.name", "nt")
def test_windows_activate_path(mock_package, mock_venv_path):
    windows_venv_path = mock_venv_path
    (windows_venv_path / "Scripts").mkdir(parents=True)
    (windows_venv_path / "Scripts" / "activate").touch()

    detector = EnvironmentDetector(package=mock_package, venv_path=windows_venv_path)
    r = detector.detect_environment()
    env_type, activate_cmd = r.env_type, r.activate_command
    assert env_type == EnvType.VENV
    assert str(windows_venv_path / "Scripts" / "activate") in activate_cmd



def test_multiple_venv_locations(temp_dir, mock_package):
    # Create a venv in the parent directory of the mock package
    venv_path = mock_package.path.parent / "venv"
    (venv_path / "bin").mkdir(parents=True)
    (venv_path / "bin" / "activate").touch()

    detector = EnvironmentDetector(package=mock_package)
    try:
        r = detector.detect_environment()
        env_type, activate_cmd = r.env_type, r.activate_command
        assert env_type == EnvType.VENV
        assert str(venv_path / "bin" / "activate") in activate_cmd
    except EnvironmentDetectionError as e:
        print(f"Error: {e}")
        print(f"Venv path exists: {venv_path.exists()}")
        print(f"Venv activate exists: {(venv_path / 'bin' / 'activate').exists()}")
        raise


def test_conda_base_environment(mock_package, mock_conda_path):
    (mock_conda_path / "envs" / "base" / "bin").mkdir(parents=True)
    (mock_conda_path / "envs" / "base" / "bin" / "activate").touch()

    detector = EnvironmentDetector(package=mock_package, conda_base_path=mock_conda_path)
    r = detector.detect_environment()
    env_type, activate_cmd = r.env_type, r.activate_command
    assert env_type == EnvType.CONDA
    assert "conda activate mock_package" in activate_cmd


@patch.object(EnvironmentDetector, "_is_valid_environment", return_value=False)
def test_invalid_environment(mock_is_valid, mock_package, mock_venv_path):
    detector = EnvironmentDetector(package=mock_package, venv_path=mock_venv_path)
    with pytest.raises(EnvironmentDetectionError):
        detector.detect_environment()


@patch("logging.Logger.info")
def test_logging(mock_log, mock_package, mock_venv_path):
    detector = EnvironmentDetector(package=mock_package, venv_path=mock_venv_path)
    detector.detect_environment()
    mock_log.assert_called_with(f"Found venv at {mock_venv_path}")


if __name__ == "__main__":
    pytest.main([__file__])