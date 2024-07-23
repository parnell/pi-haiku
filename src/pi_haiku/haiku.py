from pi_haiku import PyProjectModifier, ToLocalMatch, ToRemoteMatch, PackageMatch, PyPackage
from pi_haiku.utils import (
    create_dag,
    topological_sort,
    custom_sort_dict,
    run_bash_command,
)
from pi_haiku.models import PathType
import tempfile
from typing import Optional


class Haiku:

    @staticmethod
    def convert_projects_to_local(
        dir: PathType,
        exclude_projects: Optional[list[str]] = None,
        dry_run: bool = True,
        verbose: bool = False,
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
                print(f" =============== {proj} =============== ")
            pmod = PyProjectModifier(proj.path, packages=projs)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as tmp:

                file_changes = pmod.convert_to_local(
                    dest_file=tmp.name,
                    packages=list_projs,
                    use_toml_sort=False,
                )
                changes[proj] = file_changes
                if should_print and file_changes:
                    for c in file_changes:
                        from_str, to_str = c[0].strip(), c[1].strip()  
                        print(f"{from_str}  ->  {to_str}")
                    
            
        return changes
