import argparse
import os
import stat
import shutil
import git
import requests
import logging
from shutil import rmtree

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

REPOS_DIR = "repos"
WORKFLOWS_SUBDIR = os.path.join(".github", "workflows")
MAX_COMMITS = 10

def parse_args():
    parser = argparse.ArgumentParser(description="Script to manage repos and workflows")
    parser.add_argument("--org", required=True, help="GitHub organization name")
    parser.add_argument("--token", required=True, help="GitHub personal access token")
    return parser.parse_args()

def read_file(path, token=None):
    with open(path, "r") as f:
        content = f.read().strip()
        if token:
            content = content.replace("${{TOKEN}}", token)
        return content

def create_repo_if_not_exists(org, repo_name, token):
    logger.info(f"Checking if repository '{repo_name}' exists in organization '{org}'...")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(f"https://api.github.com/repos/{org}/{repo_name}", headers=headers)
    if response.status_code == 200:
        logger.info("Repository already exists.")
        return

    logger.info("Repository does not exist. Creating...")
    data = {
        "name": repo_name,
        "private": True,
        "auto_init": False,
    }
    response = requests.post(f"https://api.github.com/orgs/{org}/repos", headers=headers, json=data)
    if response.status_code == 201:
        logger.info("Repository created successfully.")
    else:
        logger.error(f"Failed to create repository: {response.status_code} {response.text}")
        raise RuntimeError("Failed to create repository")

def handle_remove_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def clone_or_update_local_repo(url, path):
    if not os.path.exists(path):
        logger.info(f"Cloning original repository from {url} into {path}...")
        git.Repo.clone_from(url, path)
    else:
        logger.info(f"Local repository at '{path}' already exists.")

def clone_or_update_remote_repo(url, path, default_branch):
    if os.path.exists(path):
        logger.info(f"Remote repository at '{path}' exists.")
        repo = git.Repo(path)
        try:
            logger.info("Trying to pull latest changes...")
            repo.remotes.origin.pull()
        except git.exc.GitCommandError as e:
            if any(msg in str(e) for msg in ["Couldn't find remote ref", "fatal: couldn't find remote ref", "error: could not fetch"]):
                logger.warning("Remote repository empty or no default branch yet, skipping pull.")
            else:
                raise
    else:
        logger.info(f"Cloning remote repository from {url} into {path}...")
        repo = git.Repo.clone_from(url, path)

    if default_branch not in repo.heads:
        logger.info(f"Creating local branch '{default_branch}' in remote repo clone.")
        repo.git.checkout('-b', default_branch)
    else:
        repo.git.checkout(default_branch)

    return repo

def clear_workflows_directory(workflows_dir):
    if os.path.exists(workflows_dir):
        logger.info(f"Clearing workflows directory: {workflows_dir}")
        for entry in os.listdir(workflows_dir):
            path_entry = os.path.join(workflows_dir, entry)
            if os.path.isfile(path_entry) or os.path.islink(path_entry):
                os.remove(path_entry)
            elif os.path.isdir(path_entry):
                rmtree(path_entry, onerror=handle_remove_error)
    else:
        logger.info(f"Workflows directory does not exist. Creating {workflows_dir}")
        os.makedirs(workflows_dir, exist_ok=True)

def copy_repo_files(src_root, dst_root):
    logger.info(f"Copying files from {src_root} to {dst_root} excluding .git")
    for root, dirs, files in os.walk(src_root):
        if ".git" in dirs:
            dirs.remove(".git")
        rel_path = os.path.relpath(root, src_root)
        dest_path = os.path.join(dst_root, rel_path)
        os.makedirs(dest_path, exist_ok=True)
        for file in files:
            shutil.copy2(os.path.join(root, file), os.path.join(dest_path, file))

def process_commits(original_repo, remote_repo, commits, workflow_content, workflow_file_name, default_branch):
    workflows_dir = os.path.join(original_repo.working_tree_dir, WORKFLOWS_SUBDIR)
    for commit in commits:
        logger.info(f"Processing commit {commit.hexsha}")
        original_repo.git.checkout(commit.hexsha)

        clear_workflows_directory(workflows_dir)

        workflow_path = os.path.join(workflows_dir, workflow_file_name)
        with open(workflow_path, "w") as f:
            f.write(workflow_content)

        copy_repo_files(original_repo.working_tree_dir, remote_repo.working_tree_dir)

        remote_repo.git.add(all=True)
        remote_repo.index.commit(f"commitrextractor for commit {commit.hexsha}")
        logger.info(f"Pushing changes to remote repository '{remote_repo.working_tree_dir}' on branch '{default_branch}'...")
        remote_repo.git.push('origin', default_branch)

    original_repo.git.checkout(default_branch)
    logger.info(f"Checked out original repository back to default branch '{default_branch}'.")

def main():
    args = parse_args()
    ORG = args.org
    GITHUB_TOKEN = args.token

    repo_dirs = [d for d in os.listdir(REPOS_DIR) if os.path.isdir(os.path.join(REPOS_DIR, d))]

    for repo_dir in repo_dirs:
        repo_path = os.path.join(REPOS_DIR, repo_dir)
        logger.info(f"Starting processing for repo folder: {repo_dir}")

        try:
            repo_url = read_file(os.path.join(repo_path, "repo_url.txt"))
            workflow_file_name = read_file(os.path.join(repo_path, "workflow_file.txt"))
            workflow_path = os.path.join(repo_path, workflow_file_name)
            workflow_content = read_file(workflow_path, token=GITHUB_TOKEN)
        except Exception as e:
            logger.error(f"Skipping repo {repo_dir} due to error reading files: {e}")
            continue

        repo_base_name = os.path.basename(repo_url.rstrip("/")).replace(".git", "")
        local_repo_path = os.path.join(repo_path, f"local_repo_{repo_base_name}")
        remote_repo_name = f"{repo_base_name}_commitrextractor"
        remote_repo_path = os.path.join(repo_path, f"remote_repo_{repo_base_name}")
        remote_repo_url = f"https://{GITHUB_TOKEN}@github.com/{ORG}/{remote_repo_name}.git"

        create_repo_if_not_exists(ORG, remote_repo_name, GITHUB_TOKEN)
        clone_or_update_local_repo(repo_url, local_repo_path)

        original_repo = git.Repo(local_repo_path)
        default_branch_ref = original_repo.git.symbolic_ref('refs/remotes/origin/HEAD')
        default_branch = default_branch_ref.split('/')[-1]

        remote_repo = clone_or_update_remote_repo(remote_repo_url, remote_repo_path, default_branch)

        commits = list(original_repo.iter_commits(default_branch, max_count=MAX_COMMITS))
        commits.reverse()

        process_commits(original_repo, remote_repo, commits, workflow_content, workflow_file_name, default_branch)

        original_repo.close()
        remote_repo.close()

if __name__ == "__main__":
    main()
