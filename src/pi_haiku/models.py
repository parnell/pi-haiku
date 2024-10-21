import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib as toml
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional, Self, TypeVar

PathType = str | Path

MATCH_ALL: str = r"^.*$"


class BuildSystemError(Exception):
    pass


@dataclass
class PackageMatch:
    """
    A class to match a package and change the version
    Special variables:
        {package} - The source package name
        {version} - The source version
        {package.version} - The matching package version
        {package.path.relative} - The relative path to the package from src
        {package.path.absolute} - The absolute path to the package
    """

    package_regex: str
    version_regex: str = MATCH_ALL
    version_to: str = "{package.version}"


@dataclass
class ToLocalMatch(PackageMatch):
    version_to: str = '{develop = true, path = "{package.path.relative}"}'


@dataclass
class ToRemoteMatch(PackageMatch):
    version_to: str = "{package.version}"


class BuildSystem(StrEnum):
    SETUPTOOLS = "setuptools"
    POETRY = "poetry"
    FLIT = "flit"
    HATCHLING = "hatchling"
    PDM = "pdm"


@dataclass
class PyPackage:
    name: str
    version: str
    path: Path
    dependencies: dict[str, Any] = field(default_factory=dict)
    toml_data: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def get_dependencies(file_path: PathType) -> dict[str, Any]:
        with open(file_path, "rb") as file:
            data: dict[str, Any] = toml.load(file)

        dependencies: dict[str, Any] = {}
        if _get_build_system(data, BuildSystem.POETRY, None):
            if "dependencies" in data["tool"]["poetry"]:
                dependencies.update(data["tool"]["poetry"]["dependencies"])

            if "group" in data["tool"]["poetry"]:
                for group, group_data in data["tool"]["poetry"]["group"].items():
                    if "dependencies" in group_data:
                        dependencies.update(group_data["dependencies"])
        elif _get_build_system(data, BuildSystem.SETUPTOOLS, None) and "project" in data:
            if "dependencies" in data["project"]:
                dependencies.update({dep: None for dep in data["project"]["dependencies"]})

        return dependencies
    
    @staticmethod
    def from_path(path: PathType) -> "PyPackage":
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            path = path / "pyproject.toml"
        with open(path, "rb") as fp:
            data: dict[str, Any] = toml.load(fp)
        dependencies = PyPackage.get_dependencies(path)
        build = _get_build_system(data, BuildSystem.POETRY, None)
        if build == BuildSystem.POETRY:
            poetry = data["tool"]["poetry"]
            return PyPackage(
                name=poetry["name"],
                version=poetry["version"],
                path=path,
                dependencies=dependencies,
                toml_data=data,
            )
        else:
            try:
                proj = data["project"]
                return PyPackage(
                    name=proj["name"],
                    version=proj["version"],
                    path=path,
                    dependencies=dependencies,
                    toml_data=data,
                )
            except:
                print(f"Could not read the {path} file", file=sys.stderr)
                raise

    def get_local_dependencies(self) -> dict[str, str]:
        local_deps: dict[str, str] = {}
        for dep, version in self.dependencies.items():
            if isinstance(version, dict) and "path" in version:
                local_deps[dep] = version["path"]
        return local_deps

    def __str__(self) -> str:
        return f"{self.name}=={self.version}"

    def __repr__(self) -> str:
        return str(self)

    def relative_to_package(self, other: Self) -> Path:
        return Path(os.path.relpath(self.path, other.path.parent))

    def _rmlock(self, missing_ok: bool = True) -> None:
        lockfile = self.path.parent / "poetry.lock"
        if lockfile.exists():
            lockfile.unlink(missing_ok=missing_ok)

    def __hash__(self) -> int:
        return hash(self.name)


def _get_build_system(
    data: dict[str, Any], search_for: Optional[BuildSystem] = None, default: Optional[Any] = None
) -> BuildSystem:
    build_system = data.get("build-system", {})
    for build_system in data["build-system"]["requires"]:
        v: Optional[BuildSystem] = None
        if "poetry-core" in build_system:
            v = BuildSystem.POETRY
        elif "setuptools" in build_system:
            v = BuildSystem.SETUPTOOLS
        elif "flit" in build_system:
            v = BuildSystem.FLIT
        elif "hatchling" in build_system:
            v = BuildSystem.HATCHLING
        elif "pdm" in build_system:
            v = BuildSystem.PDM
        if not search_for and v:
            return v
        if search_for and v is not None and v == search_for:
            return v
    else:
        if search_for:
            raise BuildSystemError(f"Could not find the build system: {search_for}")

    if default:
        return default
    raise BuildSystemError(f"Unsupported build system: {build_system}")
