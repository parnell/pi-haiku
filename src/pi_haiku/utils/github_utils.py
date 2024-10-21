import os
from pathlib import Path
from typing import Optional

from git import Repo
from github import Github
from pi_conf import ConfigSettings
from pydantic import SecretStr, BaseModel, Field


from pi_haiku import PyPackage


class Indexes(BaseModel):
    uri: str
    access_token: SecretStr


class GitHubSettings(ConfigSettings):
    indexes: list[Indexes] = Field(default_factory=list, alias="index")

    model_config = {
        "appname": "pi-haiku",
    }


class GithubManager:
    def __init__(self, settings: Optional[GitHubSettings] = None):
        self.settings = settings or GitHubSettings()
        self.access_map = {index.uri: index.access_token for index in self.settings.indexes}

    @staticmethod
    def get_github_url(package: PyPackage) -> Optional[str]:
        try:
            repo = Repo(package.path.parent, search_parent_directories=False)
            remote_url = repo.remotes.origin.url

            # Remove .git extension if present
            github_url = remote_url.rstrip(".git")
            return github_url
        except Exception as e:
            print(f"Error: {e}")
            return None

    def create_github_release_with_dist(self, package: PyPackage, release_body: str = ""):
        repo_url = self.get_github_url(package)
        if not repo_url:
            raise ValueError("Could not determine the GitHub repository name")

        # Extract the owner url
        owner_url = repo_url.rsplit("/", 1)[0]

        # Extract the owner/repo part
        repo_name = "/".join(repo_url.split("/")[-2:])

        access_token = self.access_map[owner_url].get_secret_value()
        tag_name = f"v{package.version}"
        release_name = package.version
        g = Github(access_token)
        repo = g.get_repo(repo_name)

        # Create the release
        release = repo.create_git_release(
            tag=tag_name, name=release_name, message=release_body, draft=False, prerelease=False
        )

        return release


# pkg = PyPackage.from_path("~/workspace/qrev-cache")
# gm = GithubManager()
# gm.create_github_release_with_dist(pkg)


# print(pkg, pkg.path)
# print(GithubManager.get_github_repo_name(pkg))
# # Example usage
# token = "your_github_personal_access_token"
# repo_name = "owner/repo"
# tag_name = "v1.0.0"
# release_name = "Version 1.0.0"
# release_body = "Description of this release"
# dist_path = "dist"  # This is where Poetry typically puts build artifacts

# # Assuming you've already run `poetry build`
# try:
#     release = create_github_release_with_dist(token, repo_name, tag_name, release_name, release_body, dist_path)
#     print(f"Release created successfully: {release.html_url}")
#     print("Distribution files uploaded.")
# except Exception as e:
#     print(f"An error occurred: {str(e)}")
