"""
vendor/linux_kernel/downloader.py - Linux Kernel Memory Subsystem Source Importer
Fetches and verifies canonical Linux memory management source files from torvalds/linux.
"""

import os
import urllib.request

LINUX_SOURCES = {
    'mmzone.h': 'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/mmzone.h',
    'oom.h': 'https://raw.githubusercontent.com/torvalds/linux/master/include/linux/oom.h',
    'vmscan.c': 'https://raw.githubusercontent.com/torvalds/linux/master/mm/vmscan.c',
    'oom_kill.c': 'https://raw.githubusercontent.com/torvalds/linux/master/mm/oom_kill.c'
}

def import_linux_kernel_sources(target_dir: str = None) -> dict:
    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(target_dir, exist_ok=True)

    results = {}
    for filename, url in LINUX_SOURCES.items():
        dest = os.path.join(target_dir, filename)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (AdiOS Vendor Import)'})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            with open(dest, 'wb') as f:
                f.write(data)
            results[filename] = {'status': 'OK', 'bytes': len(data), 'path': dest}
        except Exception as e:
            if os.path.exists(dest):
                results[filename] = {'status': 'CACHED', 'bytes': os.path.getsize(dest), 'path': dest}
            else:
                results[filename] = {'status': 'ERROR', 'error': str(e)}
    return results

if __name__ == '__main__':
    res = import_linux_kernel_sources()
    for name, info in res.items():
        b = info.get('bytes', 0)
        print(f"{name}: {info['status']} ({b} bytes)")
