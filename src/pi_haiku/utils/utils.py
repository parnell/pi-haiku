import json
import os
import subprocess
import sys
from dataclasses import dataclass
from logging import getLogger
from subprocess import CalledProcessError
from typing import Any, Optional, Sequence

from pi_haiku.models import PathType, PyPackage

log = getLogger(__name__)


@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str

    def __bool__(self):
        return self.success


def get_conda_info() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["conda", "info", "--json"], check=True, capture_output=True, text=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        log.error(f"Error getting conda info: {e}")
        log.error(f"Error output: {e.stderr}")
        raise


def run_bash_command(
    command: str,
    output_file: Optional[str] = None,
    error_file: Optional[str] = None,
    cwd: Optional[PathType] = None,
    verbose: bool = True,
    check: bool = True,
) -> CommandResult:
    if cwd:
        cwd = str(cwd)
    try:
        if verbose:
            print(f"Cmd: {command}, cwd={cwd}", flush=True)
        conda_info = get_conda_info()
        activate_path = os.path.join(conda_info["root_prefix"], "bin", "activate")
        command = f"source {activate_path} && {command}"
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
        )

        if result.stdout and output_file:
            with open(output_file, "w") as f:
                f.write(result.stdout)
            if verbose:
                print(f"Command Output: {result.stdout}")
        if result.stderr and error_file:
            with open(error_file, "w") as f:
                f.write(result.stderr)
            if verbose:
                print("Command Error Output:\n", result.stderr)

        success = result.returncode == 0
        return CommandResult(success, result.stdout, result.stderr)

    except CalledProcessError as e:
        return CommandResult(False, e.stdout, e.stderr)


def _check_value_is_primitive(value: str) -> None:
    primitives = (bool, str, int, float, type(None))
    try:
        js = json.loads(value)
        if not isinstance(js, primitives):
            raise ValueError(
                f"Advanced types, i.e array or dict, are currently not supported. Got {js}"
            )
    except json.JSONDecodeError:
        print(f"Could not parse the package info: {value}", file=sys.stderr)
        raise


def custom_sort_dict(input_dict: dict[str, Any], order_list: list[str]) -> dict[str, Any]:
    def sort_key(key: str) -> tuple[int, int | str]:
        if key in order_list:
            return (0, order_list.index(key))
        else:
            return (1, key)

    sorted_keys = sorted(input_dict.keys(), key=sort_key)
    sorted_dict = {key: input_dict[key] for key in sorted_keys}
    return sorted_dict


def create_dag(packages: Sequence[PyPackage]) -> dict[str, set[str]]:
    dag: dict[str, set[str]] = {}
    for package in packages:
        if package.name not in dag:
            dag[package.name] = set()
        for dep in package.dependencies.keys():
            if dep not in dag:
                dag[dep] = set()
            dag[dep].add(package.name)
    return dag


def topological_sort(dag: dict[str, set[str]]) -> list[str]:
    def visit(node: str) -> None:
        if node in temp_mark:
            raise ValueError(f"Cycle detected: {node}")
        if node not in perm_mark:
            temp_mark.add(node)
            for neighbor in dag.get(node, set()):
                visit(neighbor)
            temp_mark.remove(node)
            perm_mark.add(node)
            result.append(node)

    temp_mark: set[str] = set()
    perm_mark: set[str] = set()
    result: list[str] = []

    for node in dag:
        if node not in perm_mark:
            visit(node)

    return result[::-1]  # reverse the result to get the correct order


def special_substitutions(s: str, pkg: PyPackage, other_pkg: Optional[PyPackage]) -> str:
    if "{package}" in s:
        s = s.replace("{package}", pkg.name)
    if "{version}" in s:
        s = s.replace("{version}", f'"{pkg.version}"')
    if "{package." in s and other_pkg is None:
        raise ValueError("other_pkg is required for special substitutions requiring other package")
    assert other_pkg  # to make mypy happy as it is already checked in the above line
    if "{package.version}" in s:
        caret_str = "^" if not "^" in other_pkg.version else ""
        s = s.replace("{package.version}", f'"{caret_str}{other_pkg.version}"')
    if "{package.path.relative}" in s:
        s = s.replace("{package.path.relative}", str(other_pkg.relative_to_package(pkg).parent))
    if "{package.path.absolute}" in s:
        s = s.replace("{package.path.absolute}", str(other_pkg.path.parent))
    ## use a regex to remove common mistakes such as double caret
    s = s.replace("^+", "^")
    return s


def find_duplicates(lst: Sequence[Any]) -> list[Any]:
    seen = set()
    duplicates = set()

    for item in lst:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)

    return list(duplicates)
