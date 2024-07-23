import os
import tempfile
import shutil
import timeit
from pathlib import Path
import glob
import random
import string

# Approach 1: Using os.walk
def find_pyproject_toml_files_os_walk(base_directory, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.vscode', '.git']
    
    pyproject_files = []
    
    for root, dirs, files in os.walk(base_directory):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        if 'pyproject.toml' in files:
            pyproject_files.append(os.path.join(root, 'pyproject.toml'))
    
    return pyproject_files

# Approach 2: Using glob
def find_pyproject_toml_files_glob(base_directory, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.vscode', '.git']
    
    pyproject_files = []
    
    for filepath in glob.glob(os.path.join(base_directory, '**', 'pyproject.toml'), recursive=True):
        if not any(exclude in filepath for exclude in exclude_dirs):
            pyproject_files.append(filepath)
    
    return pyproject_files


# Approach 3: Using Path.glob with exclusion during traversal
def find_pyproject_toml_files_pathlib(base_directory, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.vscode', '.git']
    
    base_path = Path(base_directory)
    exclude_dirs = set(exclude_dirs)
    pyproject_files = []

    def recursive_search(current_path):
        for path in current_path.glob('*'):
            if path.is_dir():
                if path.name not in exclude_dirs:
                    recursive_search(path)
            elif path.name == 'pyproject.toml':
                pyproject_files.append(str(path))

    recursive_search(base_path)
    return pyproject_files

# Helper function to create random files
def create_random_files(directory, num_files):
    for _ in range(num_files):
        filename = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        with open(os.path.join(directory, filename), 'w') as f:
            f.write('')

# Setup a temporary directory for testing
def setup_test_environment():
    base_dir = tempfile.mkdtemp()
    excludes = ['__pycache__', '.vscode', '.git']
    for i in range(6):  # Create 5 top-level directories
        if i < len(excludes):
            top_level_dir = os.path.join(base_dir, excludes[i])
        else:
            top_level_dir = os.path.join(base_dir, f'dir{i}')
        os.makedirs(top_level_dir)
        
        for j in range(100):  # Each top-level directory has 100 subdirectories
            sub_dir = os.path.join(top_level_dir, f'subdir{j}')
            os.makedirs(sub_dir)
            
            create_random_files(sub_dir, 100)  # Each subdirectory has 50 random files
            
            if random.random() > 0.9:  # Randomly add a pyproject.toml file
                with open(os.path.join(sub_dir, 'pyproject.toml'), 'w') as f:
                    f.write('')
    
    return base_dir

def clean_test_environment(base_dir):
    shutil.rmtree(base_dir)

# Measure the performance of each approach
def measure_performance():
    base_dir = setup_test_environment()
    
    try:
        os_walk_time = timeit.timeit(lambda: find_pyproject_toml_files_os_walk(base_dir), number=10)
        glob_time = timeit.timeit(lambda: find_pyproject_toml_files_glob(base_dir), number=10)
        pathlib_time = timeit.timeit(lambda: find_pyproject_toml_files_pathlib(base_dir), number=10)
        
        print(f"os.walk approach: {os_walk_time:.6f} seconds")
        print(f"glob approach: {glob_time:.6f} seconds")
        print(f"Path.glob approach: {pathlib_time:.6f} seconds")
    finally:
        clean_test_environment(base_dir)

if __name__ == "__main__":
    measure_performance()