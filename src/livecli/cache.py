import json
import os
import shutil
import tempfile

from time import time
from .compat import is_win32

try:
    import xbmc
    import xbmcvfs
    is_kodi = True
except ImportError:
    is_kodi = False

if is_win32 and not is_kodi:
    xdg_cache = os.environ.get("APPDATA",
                               os.path.expanduser("~"))
elif is_kodi:
    xdg_cache = xbmc.translatePath("special://profile/addon_data/script.module.livecli").encode("utf-8")
    temp_dir = xbmc.translatePath("special://temp").encode("utf-8")
else:
    xdg_cache = os.environ.get("XDG_CACHE_HOME",
                               os.path.expanduser("~/.cache"))

cache_dir = os.path.join(xdg_cache, "livecli")

if is_kodi:
    # Kodi - script.module.livecli
    temp_livecli = os.path.join(temp_dir, "script.module.livecli")
    if not xbmcvfs.exists(cache_dir):
        xbmcvfs.mkdirs(cache_dir)
    if not xbmcvfs.exists(temp_livecli):
        xbmcvfs.mkdirs(temp_livecli)


class Cache(object):
    """Caches Python values as JSON and prunes expired entries."""

    def __init__(self, filename, key_prefix=""):
        self.key_prefix = key_prefix
        self.filename = os.path.join(cache_dir, filename)

        self._cache = {}

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as fd:
                    self._cache = json.load(fd)
            except Exception:
                self._cache = {}
        else:
            self._cache = {}

    def _prune(self):
        now = time()
        pruned = []

        for key, value in self._cache.items():
            expires = value.get("expires", time())
            if expires <= now:
                pruned.append(key)

        for key in pruned:
            self._cache.pop(key, None)

        return len(pruned) > 0

    def _save(self):
        if is_kodi:
            fd, tempname = tempfile.mkstemp(dir=temp_livecli)
        else:
            fd, tempname = tempfile.mkstemp()
        fd = os.fdopen(fd, "w")
        json.dump(self._cache, fd, indent=2, separators=(",", ": "))
        fd.close()

        # Silently ignore errors
        try:
            if not os.path.exists(os.path.dirname(self.filename)):
                os.makedirs(os.path.dirname(self.filename))

            shutil.move(tempname, self.filename)
        except (IOError, OSError):
            os.remove(tempname)

    def set(self, key, value, expires=60 * 60 * 24 * 7):
        self._load()
        self._prune()

        if self.key_prefix:
            key = "{0}:{1}".format(self.key_prefix, key)

        expires += time()

        self._cache[key] = dict(value=value, expires=expires)
        self._save()

    def get(self, key, default=None):
        self._load()

        if self._prune():
            self._save()

        if self.key_prefix:
            key = "{0}:{1}".format(self.key_prefix, key)

        if key in self._cache and "value" in self._cache[key]:
            return self._cache[key]["value"]
        else:
            return default


__all__ = ["Cache"]
