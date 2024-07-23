import os
import re
import shutil
import sys
import tempfile
import tomllib as toml
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Optional, Sequence

from pi_haiku.models import (
    BuildSystem,
    BuildSystemError,
    PackageMatch,
    PathType,
    PyPackage,
)
import uuid
from pi_haiku.utils import find_duplicates, run_bash_command, special_substitutions

log = getLogger(__name__)
EXCLUDE_DIRS: list[PathType] = ["__pycache__", "dist", "docker_staging"]
lsentinel = [uuid.uuid4().hex]


@dataclass
class PyProjectModifier:
    src: PathType
    pyproj: PyPackage = field(init=False)
    package_dir: Optional[PathType] = None
    packages: dict[str, PyPackage] = field(default_factory=dict)
    exclude_dirs: list[PathType] = field(default_factory=lambda: EXCLUDE_DIRS)
    exclude_hidden: bool = True

    def __post_init__(self) -> None:
        self.src = Path(self.src).expanduser().resolve()
        if not self.src.exists():
            raise FileNotFoundError(f"Could not find the file {self.src}")
        with open(self.src, "rb") as fp:
            toml.load(fp)
        self.pyproj = PyPackage.from_path(self.src)
        if self.pyproj is None:
            raise ValueError(f"Could not load the pyproject.toml file: {self.src}")
        if self.package_dir and not self.packages:
            self.package_dir = Path(self.package_dir).expanduser().resolve()
            tomls = self.find_pyproject_tomls(self.package_dir, exclude_dirs=self.exclude_dirs)

            self.packages = self._tomls_to_packages(tomls)

    @staticmethod
    def _tomls_to_packages(tomls: Sequence[PathType]) -> dict[str, PyPackage]:
        pkgs = {}
        found = []
        for f in tomls:
            try:
                pkg = PyPackage.from_path(f)
                pkgs[pkg.name] = pkg
                found.append(pkg)
            except BuildSystemError as e:
                pass
            except Exception as e:
                log.error(f"File {f} had the following Error occurred: {e}")
                raise
        duplicates = find_duplicates(found)
        if duplicates:
            raise ValueError(f"Found duplicate packages: {duplicates}")
        return pkgs

    @staticmethod
    def find_pyproject_tomls(
        base_directory: PathType,
        exclude_dirs: Optional[Sequence[PathType]] = lsentinel,
        exclude_hidden: bool = True,
        file_match: str = "pyproject.toml",
    ) -> list[Path]:
        base_path = Path(base_directory).expanduser().resolve()
        pyproject_files = []

        if exclude_dirs is lsentinel:
            exclude_dirs = EXCLUDE_DIRS
        elif exclude_dirs is None:
            exclude_dirs = []
        set_exclude_dirs = set(exclude_dirs)

        for root, dirs, files in os.walk(base_path):
            # Check if the current directory should be excluded
            if any(excluded in Path(root).parts for excluded in set_exclude_dirs):
                continue

            # Filter out directories to skip
            dirs[:] = [
                d
                for d in dirs
                if (d not in set_exclude_dirs) and (not exclude_hidden or not d.startswith("."))
            ]

            if file_match in files:
                pyproject_files.append(Path(root) / file_match)

        return pyproject_files

    @staticmethod
    def find_pyprojects(
        base_directory: PathType,
        exclude_dirs: Optional[list[str]] = lsentinel,
        build_system: BuildSystem = BuildSystem.POETRY,
    ) -> dict[str, PyPackage]:
        tomls = PyProjectModifier.find_pyproject_tomls(base_directory, exclude_dirs)
        return PyProjectModifier._tomls_to_packages(tomls)

    def convert_to_remote(
        self,
        match_patterns: Optional[Sequence[PackageMatch]] = None,
        packages: Optional[Sequence[PyPackage]] = None,
        dest_file: Optional[str] = None,
        in_place: bool = False,
        use_toml_sort: bool = True,
    ) -> list[tuple[str, str]]:
        """
        Convert package dependencies to remote (published) versions.

        Args:
            match_patterns (Optional[Sequence[PackageMatch]]): List of patterns to match and convert packages.
            packages (Optional[Sequence[PyPackage]]): List of PyPackage objects to create PackageMatch from.
            dest_file (Optional[str]): Path to save the modified pyproject.toml. If None, uses in-place modification.
            in_place (bool): If True, modifies the original file. Cannot be used with dest_file.
            use_toml_sort (bool): If True, sorts the resulting TOML file using toml-sort.

        Returns:
            List[Tuple[str, str]]: A list of tuples containing the original and modified lines.

        Raises:
            ValueError: If both dest_file and in_place are specified, or if neither is specified.
            ValueError: If both match_patterns and packages are None.
        """
        if match_patterns is None and packages is None:
            raise ValueError("Either match_patterns or packages must be provided")

        if packages is not None:
            match_patterns = self._create_match_patterns_from_packages(
                packages=packages,
                version_to="{package.version}",
            )
        if not match_patterns:
            raise ValueError(
                "No match patterns were created. pyproject.toml would not be modified."
            )

        return self._convert_to(
            match_patterns=match_patterns,
            dest_file=dest_file,
            in_place=in_place,
            use_toml_sort=use_toml_sort,
        )

    def convert_to_local(
        self,
        match_patterns: Optional[Sequence[PackageMatch]] = None,
        packages: Optional[Sequence[PyPackage]] = None,
        dest_file: Optional[str] = None,
        in_place: bool = False,
        use_toml_sort: bool = True,
    ) -> list[tuple[str, str]]:
        """
        Convert package dependencies to local development versions.

        Args:
            match_patterns (Optional[Sequence[PackageMatch]]): List of patterns to match and convert packages.
            packages (Optional[Sequence[PyPackage]]): List of PyPackage objects to create PackageMatch from.
            dest_file (Optional[str]): Path to save the modified pyproject.toml. If None, uses in-place modification.
            in_place (bool): If True, modifies the original file. Cannot be used with dest_file.
            use_toml_sort (bool): If True, sorts the resulting TOML file using toml-sort.

        Returns:
            List[Tuple[str, str]]: A list of tuples containing the original and modified lines.

        Raises:
            ValueError: If both dest_file and in_place are specified, or if neither is specified.
            ValueError: If both match_patterns and packages are None.
        """
        if match_patterns is None and packages is None:
            raise ValueError("Either match_patterns or packages must be provided")

        if packages is not None:
            match_patterns = self._create_match_patterns_from_packages(
                packages=packages,
                version_to='{develop = true, path = "{package.path.relative}"}',
            )
        if not match_patterns:
            raise ValueError(
                "No match patterns were created. pyproject.toml would not be modified."
            )
        return self._convert_to(
            match_patterns=match_patterns,
            dest_file=dest_file,
            in_place=in_place,
            use_toml_sort=use_toml_sort,
        )

    def _create_match_patterns_from_packages(
        self,
        packages: Sequence[PyPackage],
        version_to: str,
    ) -> list[PackageMatch]:
        """
        Create PackageMatch objects from PyPackage objects.

        Args:
            packages (Sequence[PyPackage]): List of PyPackage objects.

        Returns:
            List[PackageMatch]: List of PackageMatch objects created from the provided packages.
        """
        match_patterns = []
        for package in packages:
            # Create a PackageMatch object for each package
            # You may need to adjust this based on your specific requirements
            match_pattern = PackageMatch(
                package_regex=f"^{re.escape(package.name)}$",
                version_regex=r"^.*$",
                version_to=version_to,
            )
            match_patterns.append(match_pattern)
        return match_patterns

    def _convert_to(
        self,
        match_patterns: Sequence[PackageMatch],
        dest_file: Optional[str] = None,
        in_place: bool = False,
        use_toml_sort: bool = True,
    ) -> list[tuple[str, str]]:
        """
        Convert package dependencies to remote (non-local) versions.

        This method modifies the pyproject.toml file, changing specified package
        dependencies to use remote versions based on the provided match patterns.

        Args:
            match_patterns (List[PackageMatch]): List of patterns to match and convert packages.
            dest_file (Optional[str]): Path to save the modified pyproject.toml. If None, uses in-place modification.
            in_place (bool): If True, modifies the original file. Cannot be used with dest_file.
            use_toml_sort (bool): If True, sorts the resulting TOML file using toml-sort.

        Returns:
            List[Tuple[str, str]]: A list of tuples containing the original and modified lines.

        Raises:
            ValueError: If both dest_file and in_place are specified, or if neither is specified.
        """
        pyproj = self.pyproj
        assert pyproj is not None

        with tempfile.TemporaryDirectory() as tmpdirname:
            backup_file = shutil.copy(pyproj.path, tmpdirname)
        if dest_file is not None and in_place:
            raise ValueError("Only one of dest_file or in_place can be specified")
        if in_place:
            dest_file = str(pyproj.path)
        if not in_place and not backup_file:
            raise ValueError("destination file is required when in_place is False")
        changes: list[tuple[str, str]] = []
        new_lines: list[str] = []
        with open(pyproj.path) as fp:
            for line in fp:
                if "=" not in line:
                    new_lines.append(line)
                    continue
                sline = line.strip()
                package, previous_package_info = sline.split("=", maxsplit=1)
                package = package.strip()
                previous_package_info = previous_package_info.strip()

                new_value = ""
                matched = False

                for mp in match_patterns:
                    m = re.match(mp.package_regex, package)
                    if not m:
                        continue
                    package_name = m.group(0)
                    matched = True
                    try:
                        matched_package = self.packages[package_name]
                    except KeyError:
                        matched_package = None

                    new_value = re.sub(mp.version_regex, mp.version_to, previous_package_info)
                    new_value = special_substitutions(
                        new_value, pkg=pyproj, other_pkg=matched_package
                    )

                if matched:
                    new_line = f"{package} = {new_value}\n"
                    if line != new_line:
                        changes.append((line, new_line))
                        line = new_line

                new_lines.append(line)
        if not changes:
            if use_toml_sort and dest_file:
                run_bash_command(f"toml-sort {dest_file}")
            return changes
        try:
            with tempfile.NamedTemporaryFile("w", delete=False) as tmpfile:
                tmpfile.writelines(new_lines)
                tmpfile.close()
                assert dest_file is not None
                shutil.copy(tmpfile.name, dest_file)
        except Exception as e:
            print(f"Error occurred: {e}", file=sys.stderr)
            raise

        if use_toml_sort and dest_file:
            run_bash_command(f"toml-sort {dest_file}")
        return changes
