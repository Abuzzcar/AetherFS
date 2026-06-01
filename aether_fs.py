#!/usr/bin/env python3

import os
import sys
import errno
import base64
import logging
from fuse import FUSE, FuseOSError, Operations
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logging.basicConfig(filename='/tmp/aether.log', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class AetherShield(Operations):
    def __init__(self, root, password):
        self.root = os.path.abspath(root)
        
        # Core Keys
        salt = b'aether_salt_v1' 
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        self.key = kdf.derive(password.encode())
        self.cipher = Fernet(base64.urlsafe_b64encode(self.key))
        
        # Name Obfuscation
        name_kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'aether_name_salt_v1',
            iterations=1000,
        )
        self.name_key = name_kdf.derive(password.encode())
        
        self.buffers = {} 
        self.handles = {} 
        self.next_fh = 0
        self.dirty = set() 

    def _encrypt(self, name):
        if not name or name in ('.', '..'):
            return name
        padder = padding.PKCS7(128).padder()
        padded = padder.update(name.encode()) + padder.finalize()
        encryptor = Cipher(algorithms.AES(self.name_key), modes.ECB()).encryptor()
        res = encryptor.update(padded) + encryptor.finalize()
        return base64.urlsafe_b64encode(res).decode().replace('=', '')

    def _decrypt(self, name):
        if not name or name in ('.', '..'):
            return name
        try:
            rem = len(name) % 4
            if rem > 0: name += "=" * (4 - rem)
            data = base64.urlsafe_b64decode(name)
            decryptor = Cipher(algorithms.AES(self.name_key), modes.ECB()).decryptor()
            raw = decryptor.update(data) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            return (unpadder.update(raw) + unpadder.finalize()).decode()
        except:
            return name

    def _path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        parts = [self._encrypt(p) for p in partial.split('/') if p]
        return os.path.join(self.root, *parts)

    def getattr(self, path, fh=None):
        real_path = self._path(path)
        if not os.path.exists(real_path):
            raise FuseOSError(errno.ENOENT)

        st = os.lstat(real_path)
        attrs = {
            'st_atime': st.st_atime, 'st_ctime': st.st_ctime, 'st_mtime': st.st_mtime,
            'st_gid': st.st_gid, 'st_uid': st.st_uid, 'st_mode': st.st_mode,
            'st_nlink': st.st_nlink, 'st_size': st.st_size
        }

        if os.path.isfile(real_path):
            if path in self.buffers:
                attrs['st_size'] = len(self.buffers[path])
            else:
                try:
                    with open(real_path, 'rb') as f:
                        data = f.read()
                        attrs['st_size'] = len(self.cipher.decrypt(data)) if data else 0
                except:
                    attrs['st_size'] = 0
        return attrs

    def access(self, path, mode):
        if not os.access(self._path(path), mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        return os.chmod(self._path(path), mode)

    def chown(self, path, uid, gid):
        return os.chown(self._path(path), uid, gid)

    def utimens(self, path, times=None):
        return os.utime(self._path(path), times)

    def readdir(self, path, fh):
        real_path = self._path(path)
        dirents = ['.', '..']
        if os.path.isdir(real_path):
            dirents.extend([self._decrypt(e) for e in os.listdir(real_path)])
        return dirents

    def mkdir(self, path, mode):
        return os.mkdir(self._path(path), mode)

    def rmdir(self, path):
        return os.rmdir(self._path(path))

    def unlink(self, path):
        if path in self.buffers: del self.buffers[path]
        if path in self.dirty: self.dirty.remove(path)
        return os.unlink(self._path(path))

    def rename(self, old, new):
        if new in self.buffers: del self.buffers[new]
        if new in self.dirty: self.dirty.remove(new)
        if old in self.buffers: self.buffers[new] = self.buffers.pop(old)
        if old in self.dirty:
            self.dirty.add(new)
            self.dirty.remove(old)

        for fh in self.handles:
            if self.handles[fh] == old: self.handles[fh] = new

        dest = self._path(new)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        return os.rename(self._path(old), dest)

    def open(self, path, flags):
        if path not in self.buffers:
            real_path = self._path(path)
            if os.path.exists(real_path):
                with open(real_path, 'rb') as f:
                    raw = f.read()
                    try:
                        self.buffers[path] = bytearray(self.cipher.decrypt(raw)) if raw else bytearray()
                    except:
                        self.buffers[path] = bytearray(raw)
            else:
                self.buffers[path] = bytearray()

        self.next_fh += 1
        self.handles[self.next_fh] = path
        return self.next_fh

    def create(self, path, mode, fi=None):
        real_path = self._path(path)
        os.makedirs(os.path.dirname(real_path), exist_ok=True)
        with open(real_path, 'wb') as f:
            f.write(self.cipher.encrypt(b""))
            
        self.buffers[path] = bytearray()
        self.dirty.add(path)
        self.next_fh += 1
        self.handles[self.next_fh] = path
        return self.next_fh

    def read(self, path, length, offset, fh):
        p = self.handles[fh]
        return bytes(self.buffers[p][offset:offset + length])

    def write(self, path, buf, offset, fh):
        p = self.handles[fh]
        data = self.buffers[p]
        if offset + len(buf) > len(data):
            data.extend(b'\x00' * (offset + len(buf) - len(data)))
        data[offset:offset + len(buf)] = buf
        self.dirty.add(p)
        return len(buf)

    def truncate(self, path, length, fh=None):
        if path not in self.buffers: self.open(path, 0)
        self.buffers[path] = self.buffers[path][:length]
        self.dirty.add(path)

    def flush(self, path, fh):
        p = self.handles.get(fh)
        if p and p in self.dirty: self._sync(p)
        return 0

    def release(self, path, fh):
        p = self.handles.get(fh)
        if p:
            if p in self.dirty: self._sync(p)
            if list(self.handles.values()).count(p) <= 1:
                if p in self.buffers: del self.buffers[p]
            del self.handles[fh]
        return 0

    def _sync(self, path):
        real_path = self._path(path)
        with open(real_path, 'wb') as f:
            f.write(self.cipher.encrypt(bytes(self.buffers[path])))
        if path in self.dirty: self.dirty.remove(path)

    def symlink(self, name, target):
        return os.symlink(target, self._path(name))

    def mknod(self, path, mode, dev):
        return os.mknod(self._path(path), mode, dev)

    def fsync(self, path, datasync, fh):
        p = self.handles.get(fh)
        if p and p in self.dirty: self._sync(p)
        return 0

def main(mountpoint, root, password):
    FUSE(AetherShield(root, password), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
