import sys
from pathlib import Path

from pi_haiku.haiku import Haiku


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "install":
        print("Usage: haiku install <proj name>")
        sys.exit(1)

    proj_name = sys.argv[2]
    proj_path = Path(proj_name)

    Haiku.install(proj_path=proj_path)

if __name__ == "__main__":
    main()