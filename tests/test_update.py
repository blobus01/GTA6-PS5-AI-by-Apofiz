"""Tests for apofiz_update.py (auto-update). All HTTP is mocked; no network needed.

Run from the repo root: python -m unittest discover -s tests -v
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import apofiz_update as up  # noqa: E402

PAYLOAD = b"fake installer bytes" * 100
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


def asset(name, size=len(PAYLOAD)):
    return {
        "name": name,
        "size": size,
        "browser_download_url": f"https://github.com/dl/{name}",
        "url": f"https://api.github.com/assets/{name}",
    }


def release(tag, prerelease=False, extra_assets=()):
    v = tag.lstrip("v")
    names = [
        f"ApofizPlay-GTA6-{v}-mac-arm64.dmg",
        f"ApofizPlay-GTA6-{v}-mac-arm64.dmg.sha256",
        f"ApofizPlay-GTA6-{v}-win-x64-Setup.exe",
        f"ApofizPlay-GTA6-{v}-win-x64-Setup.exe.sha256",
        "ps5bridge.dll",
        *extra_assets,
    ]
    return {
        "tag_name": tag,
        "body": f"Notes for {tag}",
        "prerelease": prerelease,
        "draft": False,
        "html_url": f"https://github.com/r/releases/{tag}",
        "assets": [asset(n) for n in names],
    }


class FakeResp:
    def __init__(self, status=200, data=None, text="", content=b""):
        self.status_code = status
        self._data = data
        self.text = text
        self._content = content
        self.headers = {"Content-Length": str(len(content))} if content else {}

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def router(releases_latest=None, releases_list=None, sha=PAYLOAD_SHA, content=PAYLOAD, status=200):
    calls = []

    def get(url, **kw):
        calls.append(url)
        if url.endswith("/releases/latest"):
            return FakeResp(status, releases_latest)
        if url.endswith("/releases"):
            return FakeResp(status, releases_list)
        if url.endswith(".sha256"):
            name = url.rsplit("/", 1)[-1][:-7]
            return FakeResp(200, text=f"{sha}  {name}\n")
        return FakeResp(200, content=content)

    get.calls = calls
    return get


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"PS5_REMOTE_HOME": self.tmp.name}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        os.environ.pop("APOFIZ_UPDATE_TOKEN", None)
        os.environ.pop("GITHUB_TOKEN", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class VersionTests(unittest.TestCase):
    def test_ordering(self):
        ordered = ["0.1.0-alpha", "0.1.0-alpha.1", "0.1.0-alpha.beta", "0.1.0-beta.2",
                   "0.1.0-beta.11", "0.1.0-rc.1", "0.1.0", "0.1.1", "0.2.0", "0.10.0", "1.0.0"]
        for a, b in zip(ordered, ordered[1:]):
            self.assertEqual(up.compare_versions(a, b), -1, (a, b))
            self.assertEqual(up.compare_versions(b, a), 1, (b, a))

    def test_prefix_build_and_short(self):
        self.assertEqual(up.compare_versions("v1.2.3", "1.2.3"), 0)
        self.assertEqual(up.compare_versions("1.2.3+abc", "1.2.3"), 0)
        self.assertEqual(up.compare_versions("1.2", "1.2.0"), 0)

    def test_is_newer_handles_garbage(self):
        self.assertTrue(up.is_newer("v0.2.0", "0.1.9"))
        self.assertFalse(up.is_newer("nightly", "0.1.0"))
        self.assertFalse(up.is_newer("0.1.0", "0.1.0"))
        with self.assertRaises(ValueError):
            up.parse_version("abc")


class AssetTests(unittest.TestCase):
    def test_platform_key(self):
        self.assertEqual(up.platform_key("Darwin", "arm64"), "mac-arm64")
        self.assertIsNone(up.platform_key("Darwin", "x86_64"))
        self.assertEqual(up.platform_key("Windows", "AMD64"), "win-x64")
        self.assertEqual(up.platform_key("Windows", "ARM64"), "win-x64")
        self.assertIsNone(up.platform_key("Linux", "x86_64"))

    def test_select_per_os(self):
        assets = release("v0.2.0")["assets"]
        a, s = up.select_asset(assets, "mac-arm64")
        self.assertEqual(a["name"], "ApofizPlay-GTA6-0.2.0-mac-arm64.dmg")
        self.assertEqual(s["name"], a["name"] + ".sha256")
        a, s = up.select_asset(assets, "win-x64")
        self.assertEqual(a["name"], "ApofizPlay-GTA6-0.2.0-win-x64-Setup.exe")
        self.assertEqual(up.select_asset(assets, None), (None, None))
        self.assertEqual(up.select_asset([asset("ps5bridge.dll")], "win-x64"), (None, None))


class CheckTests(Base):
    def test_finds_update_for_mac(self):
        get = router(releases_latest=release("v0.2.0"))
        with mock.patch.object(up.requests, "get", side_effect=get):
            info = up.check_for_update("0.1.0", system="Darwin", machine="arm64")
        self.assertEqual(info["version"], "0.2.0")
        self.assertTrue(info["url"].endswith("-mac-arm64.dmg"))
        self.assertEqual(info["sha256"], PAYLOAD_SHA)
        self.assertEqual(info["size"], len(PAYLOAD))
        self.assertEqual(info["notes"], "Notes for v0.2.0")

    def test_finds_update_for_windows(self):
        get = router(releases_latest=release("v0.2.0"))
        with mock.patch.object(up.requests, "get", side_effect=get):
            info = up.check_for_update("0.1.0", system="Windows", machine="AMD64")
        self.assertTrue(info["url"].endswith("-win-x64-Setup.exe"))

    def test_up_to_date_and_unsupported(self):
        get = router(releases_latest=release("v0.1.0"))
        with mock.patch.object(up.requests, "get", side_effect=get):
            self.assertIsNone(up.check_for_update("0.1.0", system="Darwin", machine="arm64"))
            self.assertIsNone(up.check_for_update("0.0.1", system="Linux", machine="x86_64"))

    def test_beta_channel_sees_prereleases_stable_does_not(self):
        rels = [release("v0.3.0-beta.1", prerelease=True), release("v0.2.0")]
        get = router(releases_latest=rels[1], releases_list=rels)
        with mock.patch.object(up.requests, "get", side_effect=get):
            self.assertEqual(up.check_for_update("0.1.0", "beta", system="Darwin", machine="arm64")["version"],
                             "0.3.0-beta.1")
            self.assertEqual(up.check_for_update("0.1.0", system="Darwin", machine="arm64")["version"], "0.2.0")

    def test_offline_returns_none(self):
        with mock.patch.object(up.requests, "get", side_effect=requests.ConnectionError("down")):
            self.assertIsNone(up.check_for_update("0.1.0", system="Darwin", machine="arm64"))

    def test_private_or_rate_limited(self):
        for status in (404, 403):
            with mock.patch.object(up.requests, "get", side_effect=router(status=status)):
                self.assertIsNone(up.check_for_update("0.1.0", force=True, system="Darwin", machine="arm64"))

    def test_cache_used_within_ttl_and_stale_cache_when_offline(self):
        get = router(releases_latest=release("v0.2.0"))
        with mock.patch.object(up.requests, "get", side_effect=get):
            up.check_for_update("0.1.0", system="Darwin", machine="arm64")
        cache = json.loads((Path(self.tmp.name) / "update.json").read_text())
        self.assertIn(up.REPO, cache)
        with mock.patch.object(up.requests, "get", side_effect=AssertionError("network used")):
            info = up.check_for_update("0.1.0", system="Darwin", machine="arm64")
        self.assertEqual(info["sha256"], PAYLOAD_SHA)  # sha remembered in cache
        # Expire the cache, go offline: stale data still answers.
        cache[up.REPO]["stable"]["checked_at"] = time.time() - up.CACHE_TTL - 1
        (Path(self.tmp.name) / "update.json").write_text(json.dumps(cache))
        with mock.patch.object(up.requests, "get", side_effect=requests.Timeout("slow")):
            self.assertEqual(up.check_for_update("0.1.0", system="Darwin", machine="arm64")["version"], "0.2.0")

    def test_timeout_passed(self):
        get = mock.Mock(side_effect=router(releases_latest=release("v0.2.0")))
        with mock.patch.object(up.requests, "get", get):
            up.check_for_update("0.1.0", system="Darwin", machine="arm64")
        self.assertEqual(get.call_args_list[0].kwargs["timeout"], 5)


class ApplyTests(Base):
    def info(self, sha=PAYLOAD_SHA, name="ApofizPlay-GTA6-0.2.0-mac-arm64.dmg"):
        return {"version": "0.2.0", "url": f"https://github.com/dl/{name}", "name": name,
                "size": len(PAYLOAD), "sha256": sha, "notes": ""}

    def test_mac_opens_dmg_after_verify(self):
        progress = []
        with mock.patch.object(up.requests, "get", side_effect=router()), \
                mock.patch.object(up.subprocess, "Popen") as popen:
            res = up.apply_update(self.info(), lambda d, t: progress.append((d, t)), system="Darwin")
        self.assertEqual(res["action"], "opened_dmg")
        self.assertEqual(Path(res["path"]).read_bytes(), PAYLOAD)
        self.assertEqual(popen.call_args.args[0][0], "open")
        self.assertEqual(progress[-1], (len(PAYLOAD), len(PAYLOAD)))

    def test_windows_schedules_silent_installer(self):
        name = "ApofizPlay-GTA6-0.2.0-win-x64-Setup.exe"
        with mock.patch.object(up.requests, "get", side_effect=router()), \
                mock.patch.object(up.subprocess, "Popen") as popen:
            res = up.apply_update(self.info(name=name), system="Windows", pid=4242)
        self.assertEqual(res["action"], "installer_scheduled")
        self.assertTrue(res["quit_required"])
        cmd = " ".join(popen.call_args.args[0])
        self.assertIn("Wait-Process -Id 4242", cmd)
        self.assertIn("/SILENT", cmd)

    def test_sha_mismatch_raises_and_cleans_up(self):
        with mock.patch.object(up.requests, "get", side_effect=router()), \
                mock.patch.object(up.subprocess, "Popen") as popen, \
                mock.patch.object(up.tempfile, "mkdtemp", return_value=self.tmp.name):
            with self.assertRaises(up.UpdateError) as ctx:
                up.apply_update(self.info(sha="0" * 64), system="Darwin")
        self.assertIn("SHA-256 mismatch", str(ctx.exception))
        popen.assert_not_called()
        self.assertFalse([p for p in Path(self.tmp.name).iterdir() if p.suffix in (".dmg", ".part")])

    def test_missing_sha_refused_unless_allowed(self):
        with self.assertRaises(up.UpdateError):
            up.apply_update(self.info(sha=None), system="Darwin")
        with mock.patch.object(up.requests, "get", side_effect=router()), \
                mock.patch.object(up.subprocess, "Popen"):
            res = up.apply_update(self.info(sha=None), allow_unverified=True, system="Linux")
        self.assertEqual(res["action"], "downloaded")

    def test_offline_download_raises_update_error(self):
        with mock.patch.object(up.requests, "get", side_effect=requests.ConnectionError("down")):
            with self.assertRaises(up.UpdateError):
                up.apply_update(self.info(), system="Darwin")

    def test_truncated_download(self):
        def get(url, **kw):
            r = FakeResp(200, content=PAYLOAD[:10])
            r.headers = {"Content-Length": str(len(PAYLOAD))}
            return r
        with mock.patch.object(up.requests, "get", side_effect=get):
            with self.assertRaises(up.UpdateError):
                up.apply_update(self.info(), system="Darwin")


if __name__ == "__main__":
    unittest.main()
