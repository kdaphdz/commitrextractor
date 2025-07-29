import requests
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ORG = "kdaphdz"
GITHUB_TOKEN = "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"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

def get_repos(org):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            logger.error(f"Error al obtener repos: {resp.status_code} {resp.text}")
            break
        page_repos = resp.json()
        if not page_repos:
            break
        repos.extend(page_repos)
        page += 1
    return repos

def delete_repo(org, repo_name):
    url = f"https://api.github.com/repos/{org}/{repo_name}"
    resp = requests.delete(url, headers=HEADERS)
    if resp.status_code == 204:
        logger.info(f"Repositorio {repo_name} borrado correctamente.")
    else:
        logger.error(f"Error borrando {repo_name}: {resp.status_code} {resp.text}")

def main():
    repos = get_repos(ORG)
    for repo in repos:
        name = repo["name"]
        if "_commitrextractor" in name:
            logger.info(f"Borrando repo: {name}")
            delete_repo(ORG, name)

if __name__ == "__main__":
    main()
