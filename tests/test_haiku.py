from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pi_haiku import PyPackage, PyProjectModifier
from pi_haiku.haiku import Haiku


@pytest.fixture
def local_package1_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package1"
version = "0.1.0"
description = ""
authors = ["Author One <author1@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
package2 = { path = "../package2" }
numpy = "^1.21.0"
"""

@pytest.fixture
def remote_package1_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package1"
version = "0.1.0"
description = ""
authors = ["Author One <author1@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
package2 = "^0.2.0"
numpy = "^1.21.0"
"""

@pytest.fixture
def remote_package2_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package2"
version = "^0.2.0"
description = ""
authors = ["Author Two <author2@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
"""

@pytest.fixture
def remote_package3_toml_content():
    return """
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "package3"
version = "^0.3.0"
description = ""
authors = ["Author Three <author3@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
"""


@pytest.fixture
def mock_pyproject_modifier(remote_package1_toml_content, remote_package2_toml_content, remote_package3_toml_content):
    with patch('pi_haiku.PyProjectModifier') as mock:
        mock_instance = mock.return_value
        mock_instance.read_toml.side_effect = [
            remote_package1_toml_content,
            remote_package2_toml_content,
            remote_package3_toml_content
        ]
        yield mock

@pytest.fixture
def mock_create_dag():
    with patch('pi_haiku.utils.utils.create_dag') as mock:
        yield mock

@pytest.fixture
def mock_topological_sort():
    with patch('pi_haiku.utils.utils.topological_sort') as mock:
        yield mock

## TODO - Add tests for Haiku class methods
# def test_convert_projects_to_local(mock_pyproject_modifier, mock_create_dag, mock_topological_sort, local_package1_toml_content):
#     mock_dir = Path('/mock/dir')
#     mock_pyprojects = {
#         'package1': PyPackage('package1', "0.2.0", Path('/mock/dir/package1')),
#         'package2': PyPackage('package2', "0.2.0", Path('/mock/dir/package2')),
#         'package3': PyPackage('package3', "0.2.0", Path('/mock/dir/package3')),
#     }
#     mock_pyproject_modifier.find_pyprojects.return_value = mock_pyprojects
#     mock_create_dag.return_value = {'package1': ['package2'], 'package2': [], 'package3': []}
#     mock_topological_sort.return_value = ['package2', 'package3', 'package1']

#     mock_pyproject_modifier.return_value.convert_to_local.return_value = [
#         ('package2 = "^0.2.0"', 'package2 = { path = "../package2" }')
#     ]

#     result = Haiku.convert_projects_to_local(mock_dir, dry_run=True, verbose=True)

#     assert len(result) == 3
#     assert all(isinstance(key, PyPackage) for key in result.keys())
#     assert result[mock_pyprojects['package1']] == [('package2 = "^0.2.0"', 'package2 = { path = "../package2" }')]
#     assert result[mock_pyprojects['package2']] == []
#     assert result[mock_pyprojects['package3']] == []


# def test_convert_projects_to_remote(mock_pyproject_modifier, mock_create_dag, mock_topological_sort, remote_package1_toml_content):
#     mock_dir = Path('/mock/dir')
#     mock_pyprojects = {
#         'package1': PyPackage('package1', "0.1.0", Path('/mock/dir/package1')),
#         'package2': PyPackage('package2', "0.2.0", Path('/mock/dir/package2')),
#         'package3': PyPackage('package3', "0.3.0", Path('/mock/dir/package3')),
#     }
#     mock_pyproject_modifier.find_pyprojects.return_value = mock_pyprojects
#     mock_create_dag.return_value = {'package1': ['package2'], 'package2': [], 'package3': []}
#     mock_topological_sort.return_value = ['package2', 'package3', 'package1']

#     mock_pyproject_modifier.return_value.convert_to_remote.return_value = [
#         ('package2 = { path = "../package2" }', 'package2 = "^0.2.0"')
#     ]

#     result = Haiku.convert_projects_to_remote(mock_dir, dry_run=True, verbose=True, update=True)

#     assert len(result) == 3
#     assert all(isinstance(key, PyPackage) for key in result.keys())
#     assert result[mock_pyprojects['package1']] == [('package2 = { path = "../package2" }', 'package2 = "^0.2.0"')]
#     assert result[mock_pyprojects['package2']] == []
#     assert result[mock_pyprojects['package3']] == []


def test_exclude_projects():
    with patch.object(Haiku, '_convert_projects') as mock_convert:
        mock_dir = Path('/mock/dir')
        exclude_list = ['package2']
        Haiku.convert_projects_to_local(mock_dir, exclude_projects=exclude_list)
        mock_convert.assert_called_once()
        _, kwargs = mock_convert.call_args
        assert kwargs['exclude_projects'] == exclude_list

def test_include_projects():
    with patch.object(Haiku, '_convert_projects') as mock_convert:
        mock_dir = Path('/mock/dir')
        include_list = ['package1']
        Haiku.convert_projects_to_local(mock_dir, include_projects=include_list)
        mock_convert.assert_called_once()
        _, kwargs = mock_convert.call_args
        assert kwargs['include_projects'] == include_list

def test_only_change_projects():
    with patch.object(Haiku, '_convert_projects') as mock_convert:
        mock_dir = Path('/mock/dir')
        only_change_list = ['package1']
        Haiku.convert_projects_to_local(mock_dir, only_change_projects=only_change_list)
        mock_convert.assert_called_once()
        _, kwargs = mock_convert.call_args
        assert kwargs['only_change_projects'] == only_change_list

if __name__ == '__main__':
    pytest.main([__file__])