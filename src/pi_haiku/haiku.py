import os
import tempfile
from typing import Callable, Optional, Union

from pi_haiku import (
    PackageMatch,
    PyPackage,
    PyProjectModifier,
    ToLocalMatch,
    ToRemoteMatch,
)
from pi_haiku.models import PathType
from pi_haiku.utils.environment_utils import EnvHelper
from pi_haiku.utils.utils import (
    create_dag,
    custom_sort_dict,
    run_bash_command,
    topological_sort,
)

PackageType = Union[PyPackage, str]


class Haiku:
    """
    A class for managing and converting Python projects between local and remote configurations.
    """

    @staticmethod
    def install(proj_path: Optional[PathType] = None, pkg: Optional[PyPackage] = None) -> None:
        """
        Install a package in the specified project.
        """
        if proj_path is None and pkg is None:
            raise ValueError("Either proj_path or pkg must be specified")

        if proj_path is not None:
            pkg = PyPackage.from_path(proj_path)
        if pkg is None:
            raise ValueError(f"Package could not be found from proj_path: {proj_path}, pkg: {pkg}")
        main_pkg = pkg
        local_deps = main_pkg.get_local_dependencies()
        all_local_deps: dict[str, PyPackage] = {}
        for dep in local_deps:
            projs = PyProjectModifier.find_pyprojects(dep)
            all_local_deps.update(projs)
        dag = create_dag(list(all_local_deps.values()))
        flattened = topological_sort(dag)
        flattened = [p for p in flattened if p in all_local_deps]
        local_projs_to_install = [all_local_deps[p] for p in flattened]
        for proj in local_projs_to_install:
            eh = EnvHelper(proj)
            eh.poetry_install()
        eh = EnvHelper(main_pkg)
        eh.poetry_install()

    @staticmethod
    def _convert_projects(
        dir: PathType,
        convert_function: Callable,
        exclude_projects: Optional[list[PackageType]] = None,
        include_projects: Optional[list[PackageType]] = None,
        only_change_projects: Optional[list[PackageType]] = None,
        source_projects: Optional[list[PackageType]] = None,
        dry_run: bool = True,
        verbose: bool = False,
        update: bool = False,
        backup_dir: Optional[PathType] = None,
    ) -> dict[PyPackage, list[tuple[str, str]]]:
        """
        Internal method to convert projects using the specified conversion function.
        """
        projs = PyProjectModifier.find_pyprojects(dir)
        changes: dict[PyPackage, list[tuple[str, str]]] = {}
        dag = create_dag(list(projs.values()))

        flattened = topological_sort(dag)
        flattened = [p for p in flattened if p in projs]

        list_projs = list(projs.values())
        should_print = verbose or dry_run

        def get_project_name(project: PackageType) -> str:
            return project.name if isinstance(project, PyPackage) else project

        def should_process_project(proj_name: str) -> bool:
            if exclude_projects and any(get_project_name(p) == proj_name for p in exclude_projects):
                return False
            if include_projects and not any(
                get_project_name(p) == proj_name for p in include_projects
            ):
                return False
            return True

        def should_change_module(module_name: str) -> bool:
            if only_change_projects:
                v = any(get_project_name(p) == module_name for p in only_change_projects)
                return v
            return True

        for proj_name in flattened:
            if not should_process_project(proj_name):
                # if should_print:
                #     print(f"Skipped project {proj_name} due to include/exclude restrictions")
                continue

            proj = projs[proj_name]
            if should_print:
                print(f"        =============== {proj} =============== ")

            pmod = PyProjectModifier(proj.path, packages=projs)

            # Apply the conversion function to the project
            file_changes = convert_function(
                pmod,
                packages=list_projs,
                use_toml_sort=False,
                update=update,
                in_place=not dry_run,
                backup_dir=backup_dir if not dry_run else None,
                should_change_module=should_change_module,  # Pass this function to control which modules are changed
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
        exclude_projects: Optional[list[PackageType]] = None,
        include_projects: Optional[list[PackageType]] = None,
        only_change_projects: Optional[list[PackageType]] = None,
        dry_run: bool = True,
        verbose: bool = False,
        backup_dir: Optional[PathType] = None,
    ) -> dict[PyPackage, list[tuple[str, str]]]:
        """
        Convert multiple projects to local configuration.
        """
        return Haiku._convert_projects(
            dir=dir,
            convert_function=PyProjectModifier.convert_to_local,
            exclude_projects=exclude_projects,
            include_projects=include_projects,
            only_change_projects=only_change_projects,
            dry_run=dry_run,
            verbose=verbose,
            backup_dir=backup_dir,
        )

    @staticmethod
    def convert_projects_to_remote(
        dir: PathType,
        exclude_projects: Optional[list[PackageType]] = None,
        include_projects: Optional[list[PackageType]] = None,
        only_change_projects: Optional[list[PackageType]] = None,
        dry_run: bool = True,
        verbose: bool = False,
        update: bool = False,
        backup_dir: Optional[PathType] = None,
    ) -> dict[PyPackage, list[tuple[str, str]]]:
        """
        Convert multiple projects to remote configuration.
        """
        return Haiku._convert_projects(
            dir=dir,
            convert_function=PyProjectModifier.convert_to_remote,
            exclude_projects=exclude_projects,
            include_projects=include_projects,
            only_change_projects=only_change_projects,
            dry_run=dry_run,
            verbose=verbose,
            update=update,
            backup_dir=backup_dir,
        )
