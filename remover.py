import requests
import logging
import argparse
import os
import shutil

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

REPOS_DIR = "repos"  # Carpeta donde están los repos locales

def parse_args():
    parser = argparse.ArgumentParser(description="Delete GitHub repos and local copies")
    parser.add_argument("--org", required=True, help="GitHub organization name")
    parser.add_argument("--token", required=True, help="GitHub personal access token")
    return parser.parse_args()

def get_repos(org, headers):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"Error fetching repos: {resp.status_code} {resp.text}")
            break
        page_repos = resp.json()
        if not page_repos:
            break
        repos.extend(page_repos)
        page += 1
    return repos

def delete_repo(org, repo_name, headers):
    url = f"https://api.github.com/repos/{org}/{repo_name}"
    resp = requests.delete(url, headers=headers)
    if resp.status_code == 204:
        logger.info(f"Repository '{repo_name}' deleted successfully.")
    else:
        logger.error(f"Error deleting '{repo_name}': {resp.status_code} {resp.text}")

def delete_local_dirs(repo_dir):
    if not os.path.isdir(repo_dir):
        return

    for name in os.listdir(repo_dir):
        full_path = os.path.join(repo_dir, name)
        if os.path.isdir(full_path) and (name.startswith("local_repo_") or name.startswith("remote_repo_")):
            logger.info(f"Deleting local folder: {full_path}")
            shutil.rmtree(full_path, ignore_errors=True)

def main():
    args = parse_args()
    org = args.org
    token = args.token
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    repos = get_repos(org, headers)
    for repo in repos:
        name = repo["name"]
        if "_commitrextractor" in name:
            logger.info(f"Deleting repo: {name}")
            delete_repo(org, name, headers)

    if os.path.exists(REPOS_DIR):
        for subdir in os.listdir(REPOS_DIR):
            full_path = os.path.join(REPOS_DIR, subdir)
            if os.path.isdir(full_path):
                delete_local_dirs(full_path)

if __name__ == "__main__":
    main()
