# Haiku: PyProject.toml Dependency Converter

Haiku is a Python tool designed to simplify the process of switching between local and remote package dependencies in `pyproject.toml` files. This is particularly useful for developers working on multiple interconnected packages who need to frequently switch between local development versions and published releases.

## Features

- Convert local package dependencies to remote (published) versions
- Convert remote package dependencies to local development versions
- In-place modification of `pyproject.toml` files
- Option to save modifications to a new file
- Automatic sorting of the modified TOML file (optional)

## Installation

To install Haiku, run the following command:

```bash
pip install pi-haiku
```