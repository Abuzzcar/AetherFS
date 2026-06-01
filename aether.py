#!/usr/bin/env python3

import os
import sys
import subprocess
import getpass
import time
import json

# Prefer the local virtual environment if it exists, otherwise fall back to the current interpreter
if os.path.exists("./.venv/bin/python3"):
    PYTHON_BIN = "./.venv/bin/python3"
else:
    PYTHON_BIN = sys.executable

FS_SCRIPT = "aether_fs.py"
REGISTRY_FILE = ".aether_registry.json"

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_registry(registry):
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=4)

# Creating mount points and directories for vaults
def create():
    print("\n[ AetherFS - Vault Creation ]")
    vault_id = input("Vault Name: ").strip()
    if not vault_id:
        print("[!] Error: Name required.")
        return

    registry = load_registry()
    if vault_id in registry:
        print(f"[!] Error: '{vault_id}' already exists.")
        return

    storage = f"vault_{vault_id}"
    mount_pt = vault_id

    if os.path.exists(storage) and os.listdir(storage):
        print(f"? Warning: '{storage}' is not empty.")
    
    while True:
        pw1 = getpass.getpass("Enter Password: ")
        pw2 = getpass.getpass("Verify Password: ")
        
        if pw1 == pw2:
            break
        print("[!] Error: Passwords mismatch. Try again.")

    os.makedirs(storage, exist_ok=True)
    os.makedirs(mount_pt, exist_ok=True)

    registry[vault_id] = {
        "storage": storage,
        "mount": mount_pt
    }
    save_registry(registry)

    print(f"\n[+] Vault '{vault_id}' initialized.")
    print(f"    Storage: {storage}")
    print(f"    Mount:   {mount_pt}")
    print(f"\nMount with: python3 aether.py mount {vault_id}")

def mount(vault_id=None):
    registry = load_registry()
    if not vault_id:
        if not registry:
            print("No vaults found. Run 'create' first.")
            return
        print("Vaults:", ", ".join(registry.keys()))
        vault_id = input("Mount Vault: ").strip()

    if vault_id not in registry:
        print(f"[!] Error: '{vault_id}' not found.")
        return

    config = registry[vault_id]
    storage = config["storage"]
    mount_pt = config["mount"]

    if os.path.ismount(mount_pt):
        print(f"[!] Error: {mount_pt} is already active.")
        return

    if not os.path.exists(mount_pt):
        os.makedirs(mount_pt)

    if os.listdir(mount_pt):
        print(f"[!] Error: Mount point '{mount_pt}' is not empty!")
        return

    password = getpass.getpass(f"Password for '{vault_id}': ")
    
    print(f"[*] Unlocking '{vault_id}'...")
    cmd = [PYTHON_BIN, FS_SCRIPT, mount_pt, storage, password]
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    time.sleep(2)
    if process.poll() is None:
        print(f"[+] Shield Active: '{mount_pt}' is now accessible.")
    else:
        print("[!] Error: Failed. Check FUSE status")

def unmount(vault_id=None):
    registry = load_registry()
    if not vault_id:
        active = [v for v, cfg in registry.items() if os.path.ismount(cfg["mount"])]
        if not active:
            print("No active vaults.")
            return
        print("Active:", ", ".join(active))
        vault_id = input("Unmount Vault: ").strip()

    if vault_id not in registry:
        print(f"[!] Error: '{vault_id}' unknown.")
        return

    mount_pt = registry[vault_id]["mount"]
    print(f"[*] Locking '{vault_id}'...")
    
    success = False
    try:
        subprocess.run(["fusermount", "-u", mount_pt], check=True, stderr=subprocess.DEVNULL)
        success = True
    except:
        try:
            subprocess.run(["umount", mount_pt], check=True)
            success = True
        except:
            print(f"[!] Error: Could not unmount {mount_pt} (Busy).")

    if success:
        try:
            if os.path.exists(mount_pt) and not os.listdir(mount_pt):
                os.rmdir(mount_pt)
            print("[+] Vault Secured.")
        except:
            pass

def list_vaults():
    registry = load_registry()
    if not registry:
        print("Aether is empty.")
        return

    print(f"{'VAULT':<15} {'MOUNT':<15} {'STATUS'}")
    print("-" * 45)
    for vid, cfg in registry.items():
        status = "[ACTIVE]" if os.path.ismount(cfg["mount"]) else "[LOCKED]"
        print(f"{vid:<15} {cfg['mount']:<15} {status}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 aether.py [create|mount|unmount|list]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "create":
        create()
    elif cmd == "mount":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        mount(name)
    elif cmd == "unmount":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        unmount(name)
    elif cmd == "list":
        list_vaults()
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
