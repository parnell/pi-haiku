import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import toml

from pi_haiku.models import PyPackage
from pi_haiku.utils.environment_detector import EnvironmentResult, EnvType
from pi_haiku.utils.environment_utils import EnvHelper

skip_if_no_env = pytest.mark.skipif(
    os.environ.get("HAIKU_TEST_ENVIRONMENT_UTILS") is None,
    reason="Environment variable HAIKU_TEST_ENVIRONMENT_UTILS is not set",
)


def create_conda_env(name, python_version="3.11"):
    subprocess.run(["conda", "create", "-n", name, f"python={python_version}", "-y"], check=True)


def remove_conda_env(name):
    subprocess.run(["conda", "env", "remove", "-n", name, "-y"], check=True)


def conda_env_exists(name):
    result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True)
    return name in result.stdout


@pytest.fixture
def sample_package():
    return PyPackage(name="test_package", version="1.0.0", path=Path("/path/to/test_package"))


@pytest.fixture
def env_helper(sample_package):
    return EnvHelper(package=sample_package)


@pytest.fixture(scope="function")
def temp_conda_env():
    env_name = "test_conda_env"
    create_conda_env(env_name)
    yield env_name
    remove_conda_env(env_name)


def write_pyproject_file(path):
    pyproject_content = {
        "build-system": {
            "build-backend": "poetry.core.masonry.api",
            "requires": ["poetry-core>=1.0.0"],
        },
        "tool": {
            "poetry": {
                "name": "test_package",
                "version": "0.1.0",
                "description": "A test package",
            }
        },
    }
    with open(path / "pyproject.toml", "w") as f:
        toml.dump(pyproject_content, f)


@skip_if_no_env
def test_env_helper_initialization(env_helper, sample_package):
    assert env_helper.package == sample_package
    assert env_helper.venv_path is None
    assert env_helper.conda_base_path == Path.home() / "miniforge3"
    assert env_helper.error_file == "test_package_install.log"


@skip_if_no_env
def test_create_conda_project_existing(tmp_path, temp_conda_env):
    # Create a temporary package
    package_dir = tmp_path / "test_package"
    package_dir.mkdir()
    write_pyproject_file(package_dir)
    # (package_dir / "pyproject.toml").touch()

    package = PyPackage.from_path(package_dir)

    # Set the conda base path to the temporary conda environment
    conda_base_path = Path(os.environ.get("CONDA_PREFIX")).parent

    # Initialize EnvHelper with the existing conda environment
    env_helper = EnvHelper(package=package, conda_base_path=conda_base_path)

    # Rename the package to match the existing conda environment
    env_helper.package.name = temp_conda_env

    # Test create_conda_project
    assert env_helper.create_conda_project() == True

    # Verify that the conda environment still exists and wasn't recreated
    assert conda_env_exists(temp_conda_env)


@skip_if_no_env
def test_env_helper_initialization_with_venv_path(tmp_path):
    # Create a temporary package directory
    package_dir = tmp_path / "test_package"
    package_dir.mkdir()

    # Create a pyproject.toml file with some basic content
    write_pyproject_file(package_dir)

    # Create a virtual environment path
    venv_path = tmp_path / "venv"

    # Initialize EnvHelper
    helper = EnvHelper(package=str(package_dir), venv_path=venv_path)

    # Assertions
    assert helper.package.name == "test_package"
    assert helper.package.version == "0.1.0"
    assert helper.venv_path == venv_path
    assert helper.error_file == "test_package_install.log"


# @patch("pi_haiku.environment_detector.EnvironmentDetector")
# @patch("pi_haiku.environment_utils.run_bash_command")
# def test_create_conda_project_new(mock_run_bash, mock_detector, env_helper):
#     mock_detector.return_value._detect_conda.side_effect = EnvironmentDetectionError()
#     mock_run_bash.return_value = MagicMock(returncode=0)

#     assert env_helper.create_conda_project() == True
#     mock_run_bash.assert_called_once_with("conda create -n test_package python=3.11 -y")


@skip_if_no_env
@patch("pi_haiku.environment_detector.EnvironmentDetector")
@patch("pi_haiku.environment_utils.run_bash_command")
def test_update_successful(mock_run_bash, mock_detector, env_helper):
    mock_detector.return_value.detect_environment.return_value = EnvironmentResult(
        env_type=EnvType.CONDA, activate_command="conda activate test_package"
    )
    mock_run_bash.return_value = MagicMock(stdout="Update successful")

    result = env_helper.poetry_update()
    assert result == "Update successful"
    mock_run_bash.assert_called_once()


@skip_if_no_env
@patch("pi_haiku.environment_detector.EnvironmentDetector")
@patch("pi_haiku.environment_utils.run_bash_command")
def test_update_no_dependencies(mock_run_bash, mock_detector, env_helper):
    mock_detector.return_value.detect_environment.return_value = EnvironmentResult(
        env_type=EnvType.CONDA, activate_command="conda activate test_package"
    )
    mock_run_bash.return_value = MagicMock(stdout="No dependencies to install or update")

    result = env_helper.poetry_update()
    assert result is None


# @patch("pi_haiku.environment_detector.EnvironmentDetector")
# @patch("pi_haiku.environment_utils.run_bash_command")
# def test_update_failed(mock_run_bash, mock_detector, env_helper):
#     mock_detector.return_value.detect_environment.side_effect = EnvironmentError("Test error")

#     result = env_helper.poetry_update()
#     assert result is None


@skip_if_no_env
def test_from_path():
    path = "/path/to/package"
    with patch("pi_haiku.models.PyPackage.from_path") as mock_from_path:
        mock_from_path.return_value = PyPackage(
            name="test_package", version="1.0.0", path=Path(path)
        )
        helper = EnvHelper.from_path(path)
        assert isinstance(helper, EnvHelper)
        assert helper.package.name == "test_package"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
