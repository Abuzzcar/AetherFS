# AetherFS

A lightweight, FUSE-based encrypted filesystem. AetherFS provides a "vault" system where your files are stored in an obfuscated, encrypted state and only accessible when mounted with the correct password.

## Features

- **Deterministic Name Obfuscation:** Filenames are mapped to encrypted strings consistently.
- **Strong Encryption:** Uses Fernet (AES-128 in CBC mode with HMAC) for file contents and AES-ECB for name obfuscation.
- **GUI Compatible:** Fully supports atomic saves used by editors like Gedit and LibreOffice.
- **Simplified Management:** Easy-to-use CLI for creating, mounting, and unmounting vaults.
- **No Password checking**: Only through using the correct password will vault contents display properly, otherwise vault contents will be blank.

## Installation

### Prerequisites

- Python 3.x
- FUSE (on Ubuntu/Debian: `sudo apt install fuse3 libfuse3-dev`)

**Warning**: I have **not** tested on Windows or MacOS

### Setup

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Create a New Vault
```bash
python3 aether.py create
```
Follow the prompts to set a vault name and password.

### Mount a Vault
```bash
python3 aether.py mount <vault_name>
```
Your files will appear in a folder named after your vault.

### Unmount a Vault
```bash
python3 aether.py unmount <vault_name>
```
This safely locks the vault and cleans up the mount point.

### List Vaults
```bash
python3 aether.py list
```

## Architecture

- `aether.py`: The management CLI for registry and FUSE process handling.
- `aether_fs.py`: The core FUSE driver implementing the encrypted filesystem logic.

## Security Note

This tool is designed for personal privacy. It uses memory buffering for open files to ensure compatibility with modern applications. Be aware that for very large files, memory usage will correspond to the file size while the file is open.
