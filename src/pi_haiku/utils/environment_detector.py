import logging
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pi_haiku.models import PyPackage
from pi_haiku.utils.utils import run_bash_command

log = logging.getLogger(__name__)

class EnvType(Enum):
    VENV = auto()
    CONDA = auto()



@dataclass
class EnvironmentResult:
    env_type: EnvType
    activate_command: str


class EnvironmentDetectionError(EnvironmentError):
    pass


class EnvironmentDetector:
    def __init__(
        self,
        package: Optional[PyPackage] = None,
        venv_path: Optional[Path] = None,
        conda_base_path: Optional[Path] = None,
        package_path: Optional[Path] = None,
    ):
        if package_path:
            package = PyPackage.from_path(package_path)
        self.package = package
        if self.package and not isinstance(self.package, PyPackage):
            self.package = PyPackage.from_path(self.package)
        if not self.package:
            raise ValueError(f"No package provided. {package}, {package_path}")
        if not isinstance(self.package, PyPackage):
            raise ValueError(f"Invalid package provided. {package}, {package_path}")
        self.venv_path = venv_path
        self.conda_base_path = conda_base_path
        

    def detect_environment(self) -> EnvironmentResult:
        venv_result = self._detect_venv()
        if venv_result:
            return venv_result

        conda_result = self._detect_conda()
        if conda_result:
            return conda_result

        log.error("No valid virtual environment found.")
        raise EnvironmentDetectionError("No valid virtual environment found.")

    def _detect_venv(self) -> Optional[EnvironmentResult]:
        venv_names = [".venv", "venv", "env"]
        venv_locations = [self.venv_path] if self.venv_path else []
        assert self.package
        venv_locations.extend([self.package.path.parent / name for name in venv_names])
        venv_locations.extend([self.package.path.parent.parent / name for name in venv_names])

        for venv_loc in venv_locations:
            if venv_loc and venv_loc.is_dir() and self._is_valid_environment(venv_loc):
                activate_path = self._get_activate_path(venv_loc)
                if activate_path:
                    log.info(f"Found venv at {venv_loc}")
                    return EnvironmentResult(EnvType.VENV, str(activate_path))
        return None

    def _detect_conda(self, include_base: bool = False) -> Optional[EnvironmentResult]:
        if not self.conda_base_path:
            return None
        assert self.package

        result = run_bash_command(f"conda env list | grep {self.package.name}")
        env_list = result.stdout.strip().split('\n')
        # Parse the output to get environment names and paths
        conda_envs = {}
        for line in env_list:  # Skip the first two lines (header)
            if "#" in line:
                continue
            if line.strip():
                parts = line.split()
                env_name = parts[0]
                env_path = parts[-1]
                conda_envs[env_name] = env_path

        env_names = [self.package.name]
        if include_base:
            env_names.append("base")

        for env_name in env_names:
            if env_name in conda_envs:
                log.info(f"Found conda environment: {env_name}")
                return EnvironmentResult(EnvType.CONDA, f"conda activate {env_name}")
            conda_env_path = self.conda_base_path / "envs" / env_name
            if conda_env_path.is_dir() and self._is_valid_environment(conda_env_path):
                log.info(f"Found conda environment: {env_name}")
                return EnvironmentResult(EnvType.CONDA, f"conda activate {env_name}")

        # If no environment found in 'envs', check if conda_base_path itself is a valid environment
        if self._is_valid_environment(self.conda_base_path):
            log.info("Found conda base environment")
            return EnvironmentResult(EnvType.CONDA, "conda activate base")

        return None

    @staticmethod
    def _get_activate_path(env_path: Path) -> Optional[Path]:
        if os.name == "nt":  # Windows
            activate_path = env_path / "Scripts" / "activate"
        else:  # Unix-like systems
            activate_path = env_path / "bin" / "activate"

        return activate_path if activate_path.exists() else None

    def _is_valid_environment(self, env_path: Path) -> bool:
        # Simplified check for testing purposes
        return (env_path / "bin" / "activate").exists() or (
            env_path / "Scripts" / "activate"
        ).exists()