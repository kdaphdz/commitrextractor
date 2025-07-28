import os
import stat
import shutil
import git
import requests
from shutil import rmtree

repo_url = "https://github.com/django/django"
REPO_BASE_NAME = os.path.basename(repo_url.rstrip("/")).replace(".git", "")

local_repo_path = f"./local_repo_{REPO_BASE_NAME}"
remote_repo_path = f"./remote_repo_{REPO_BASE_NAME}"
file_to_modify = ".github/workflows/benchmark.yml"

NEW_REPO_NAME = f"{REPO_BASE_NAME}_commitrextractor"

GITHUB_TOKEN = "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"
ORG = "kdaphdz"
remote_repo_url = f"https://{GITHUB_TOKEN}@github.com/{ORG}/{NEW_REPO_NAME}.git"

with open("new.yml", "r") as f:
    new_content = f.read()

def create_repo_in_org():
    print(f"[INFO] Checking if repository '{NEW_REPO_NAME}' exists in organization '{ORG}'...")
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(f"https://api.github.com/repos/{ORG}/{NEW_REPO_NAME}", headers=headers)
    if response.status_code == 200:
        print("[INFO] Repository already exists.")
        return
    print("[INFO] Repository does not exist. Creating...")
    data = {
        "name": NEW_REPO_NAME,
        "private": True,
        "auto_init": False,
    }
    response = requests.post(f"https://api.github.com/orgs/{ORG}/repos", headers=headers, json=data)
    if response.status_code == 201:
        print("[INFO] Repository created successfully.")
    else:
        print("[ERROR] Failed to create repository:")
        print(response.status_code, response.text)
        exit(1)

def handle_remove_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

create_repo_in_org()

if not os.path.exists(local_repo_path):
    print("[INFO] Cloning original repository...")
    git.Repo.clone_from(repo_url, local_repo_path)
else:
    print("[INFO] Original repository already cloned.")

if os.path.exists(remote_repo_path):
    print("[INFO] Remote repository already cloned locally, pulling latest changes...")
    remote_repo = git.Repo(remote_repo_path)
    remote_repo.remotes.origin.pull()
else:
    print("[INFO] Cloning remote repository (empty)...")
    remote_repo = git.Repo.clone_from(remote_repo_url, remote_repo_path)

original_repo = git.Repo(local_repo_path)
commits = list(original_repo.iter_commits('main', max_count=3))
commits.reverse()

workflows_dir = os.path.join(local_repo_path, ".github", "workflows")

for commit in commits:
    print(f"\n[INFO] Processing commit {commit.hexsha} - {commit.message.strip()}")

    original_repo.git.checkout(commit.hexsha)

    if os.path.exists(workflows_dir):
        for entry in os.listdir(workflows_dir):
            path_entry = os.path.join(workflows_dir, entry)
            if os.path.isfile(path_entry) or os.path.islink(path_entry):
                os.remove(path_entry)
            elif os.path.isdir(path_entry):
                rmtree(path_entry, onerror=handle_remove_error)
    else:
        os.makedirs(workflows_dir, exist_ok=True)

    with open(os.path.join(workflows_dir, "benchmark.yml"), "w") as f:
        f.write(new_content)

    for root, dirs, files in os.walk(local_repo_path):
        if ".git" in dirs:
            dirs.remove(".git")
        rel_path = os.path.relpath(root, local_repo_path)
        dest_path = os.path.join(remote_repo_path, rel_path)
        os.makedirs(dest_path, exist_ok=True)
        for file in files:
            src_file = os.path.join(root, file)
            dst_file = os.path.join(dest_path, file)
            shutil.copy2(src_file, dst_file)

    remote_repo.git.add(all=True)
    remote_repo.index.commit(f"commitrextractor for commit {commit.hexsha}")
    print(f"[INFO] Pushing changes to remote repository '{NEW_REPO_NAME}'...")
    remote_repo.git.push('origin', 'main')

original_repo.git.checkout('main')
