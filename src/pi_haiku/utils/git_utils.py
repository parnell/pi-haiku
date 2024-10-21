import json

import requests


class PackageNotFoundError(Exception):
    pass


def get_package_versions(package_name) -> list[str] | None:
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            versions = list(data["releases"].keys())
            versions.sort(key=lambda s: [int(u) for u in s.split(".")])
            return versions
        elif response.status_code == 404:
            return None
        else:
            print(f"Unexpected response code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to PyPI: {e}")
    except json.JSONDecodeError:
        print("Error decoding JSON response")
    return None
