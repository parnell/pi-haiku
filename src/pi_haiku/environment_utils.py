import logging
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pi_haiku.models import PathType, PyPackage
from pi_haiku.utils import run_bash_command
from pi_haiku.environment_detector import EnvironmentDetector, EnvironmentResult


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
        

    def update(self) -> Optional[str]:
        try:
            detect = EnvironmentDetector(self.package, self.venv_path, self.conda_base_path)
            env_result = detect.detect_environment()
            # env_type, activate_command = self.detect_environment()
            # command = f"source {env_result.activate_command} && poetry install -vvv"
            command = f"{env_result.activate_command} && poetry update -vvv"
            sh_result = run_bash_command(command, cwd=self.package.path.parent)
            if command:
                if "No dependencies to install or update" in sh_result.stdout:
                    print(f"No dependencies to install or update for {self.package.name}")
                    return None
                print(sh_result.stdout)
                print(
                    f"Update successful for {self.package.name} v{self.package.version} using {env_result.env_type} environment"
                )
            return sh_result.stdout
        except EnvironmentError as e:
            print(f"Installation failed for {self.package.name}: {e}")
        except subprocess.CalledProcessError as e:
            print(
                f"Installation command failed for {self.package.name}. Check {self.error_file} for details."
            )
        return None

    @staticmethod
    def from_path(path: PathType) -> "EnvHelper":
        return EnvHelper(PyPackage.from_path(path))

