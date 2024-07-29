import os
import tempfile
from typing import Callable, Optional

from pi_haiku import (
    PackageMatch,
    PyPackage,
    PyProjectModifier,
    ToLocalMatch,
    ToRemoteMatch,
)
from pi_haiku.models import PathType
from pi_haiku.utils import (
    create_dag,
    custom_sort_dict,
    run_bash_command,
    topological_sort,
)


class Haiku:

    @staticmethod
    def _convert_projects(
        dir: PathType,
        convert_function: Callable,
        exclude_projects: Optional[list[str]] = None,
        dry_run: bool = True,
        verbose: bool = False,
        update: bool = False,
        backup_dir: Optional[PathType] = None,
    ) -> dict[PyPackage, list[tuple[str, str]]]:
        projs = PyProjectModifier.find_pyprojects(dir)
        changes: dict[PyPackage, list[tuple[str, str]]] = {}
        dag = create_dag(list(projs.values()))
        flattened = topological_sort(dag)
        flattened = [p for p in flattened if p in projs]
        list_projs = list(projs.values())
        should_print = verbose or dry_run
        for proj_name in flattened:
            if exclude_projects and proj_name in exclude_projects:
                continue
            proj = projs[proj_name]
            if should_print:
                print(f"        =============== {proj} =============== ")
            pmod = PyProjectModifier(proj.path, packages=projs)

            if backup_dir:
                backup_file = os.path.join(backup_dir, f"{proj.name}_pyproject.toml")
            else:
                backup_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".toml", delete=False
                ).name

            file_changes = convert_function(
                pmod,
                dest_file=backup_file,
                packages=list_projs,
                use_toml_sort=False,
                update=update,
            )
            changes[proj] = file_changes
            if should_print and file_changes:
                for c in file_changes:
                    from_str, to_str = c[0].strip(), c[1].strip()
                    print(f"{from_str}  ->  {to_str}")

        return changes

    @staticmethod
    def convert_projects_to_local(
        dir: PathType,
        exclude_projects: Optional[list[str]] = None,
        dry_run: bool = True,
        verbose: bool = False,
        backup_dir: Optional[PathType] = None,
    ) -> dict[PyPackage, list[tuple[str, str]]]:
        return Haiku._convert_projects(
            dir,
            PyProjectModifier.convert_to_local,
            exclude_projects,
            dry_run,
            verbose,
            backup_dir=backup_dir,
        )

    @staticmethod
    def convert_projects_to_remote(
        dir: PathType,
        exclude_projects: Optional[list[str]] = None,
        dry_run: bool = True,
        verbose: bool = False,
        update: bool = False,
        backup_dir: Optional[PathType] = None,
    ) -> dict[PyPackage, list[tuple[str, str]]]:
        return Haiku._convert_projects(
            dir=dir,
            convert_function=PyProjectModifier.convert_to_remote,
            exclude_projects=exclude_projects,
            dry_run=dry_run,
            verbose=verbose,
            update=update,
            backup_dir=backup_dir,
        )
