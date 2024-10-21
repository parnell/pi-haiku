import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pi_haiku.models import PathType, PyPackage
from pi_haiku.utils.environment_detector import (
    EnvironmentDetectionError,
    EnvironmentDetector,
    EnvironmentResult,
)
from pi_haiku.utils.utils import run_bash_command

# Define the TRACE level; any integer lower than 10 (DEBUG's level) will work.
TRACE_LEVEL = 5

class CustomLogger(logging.getLoggerClass()):
    def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, message, args, **kwargs)

# Set the custom logger class
logging.setLoggerClass(CustomLogger)

log: CustomLogger = logging.getLogger(__name__)

VERBOSE_LEVEL = 1
class EnvType(Enum):
    VENV = auto()
    CONDA = auto()


@dataclass
class EnvHelper:
    package: PyPackage
    venv_path: Optional[Path] = None
    conda_base_path: Optional[Path] = field(default_factory=lambda: Path.home() / "miniforge3")
    error_file: str = field(init=False)

    def __post_init__(self):
        if isinstance(self.package, str):
            self.package = PyPackage.from_path(self.package)
        self.error_file = f"{self.package.name}_install.log"
        if self.venv_path:
            self.venv_path = Path(self.venv_path)
        if self.conda_base_path:
            self.conda_base_path = Path(self.conda_base_path)

    def has_conda(self) -> bool:
        # Check if the conda environment already exists
        try:
            detect = EnvironmentDetector(self.package, self.venv_path, self.conda_base_path)
            detect_result = detect._detect_conda()
            return detect_result is not None and detect_result.env_type == EnvType.CONDA
        except EnvironmentDetectionError:
            pass
        return False

    def create_conda_project(self) -> bool:
        """
        Create a conda project if it doesn't exist.

        Returns:
            bool: True if the project was created or already exists, False otherwise.
        """
        if self.has_conda():
            log.debug(f"Conda environment already exists for {self.package.name}")
            return True
        # Create the conda environment
        create_command = f"conda create -n {self.package.name} python=3.11 -y"
        return run_bash_command(create_command) == True

    def poetry_update(self) -> Optional[str]:
        try:
            detect = EnvironmentDetector(self.package, self.venv_path, self.conda_base_path)
            env_result = detect.detect_environment()
            command = f"{env_result.activate_command} && poetry update -vvv"
            sh_result = run_bash_command(command, cwd=self.package.path.parent)
            if command:
                if "No dependencies to install or update" in sh_result.stdout:
                    log.debug(f"No dependencies to install or update for {self.package.name}")
                    return None
                log.trace(sh_result.stdout)
                log.debug(
                    f"Update successful for {self.package.name} v{self.package.version} using {env_result.env_type} environment"
                )
            return sh_result.stdout
        except EnvironmentError as e:
            log.error(f"Installation failed for {self.package.name}: {e}")
        except subprocess.CalledProcessError as e:
            log.error(
                f"Installation command failed for {self.package.name}. Check {self.error_file} for details."
            )
        return None

    def poetry_install(self) -> Optional[str]:
        try:
            detect = EnvironmentDetector(self.package, self.venv_path, self.conda_base_path)
            env_result = detect.detect_environment()
            command = f"{env_result.activate_command} && poetry install -vvv"
            sh_result = run_bash_command(command, cwd=self.package.path.parent)
            if command:
                log.trace(sh_result.stdout)
                log.debug(
                    f"Install successful for {self.package.name} v{self.package.version} using {env_result.env_type} environment"
                )
            return sh_result.stdout
        except EnvironmentError as e:
            log.error(f"Installation failed for {self.package.name}: {e}")
        except subprocess.CalledProcessError as e:
            log.error(
                f"Installation command failed for {self.package.name}. Check {self.error_file} for details."
            )
        return None

    @staticmethod
    def from_path(path: PathType) -> "EnvHelper":
        return EnvHelper(PyPackage.from_path(path))
