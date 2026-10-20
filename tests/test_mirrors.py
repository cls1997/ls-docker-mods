"""Offline functional tests: run the real Bash/awk transformer on staged roots."""

from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CONFIGURE = REPO / "root/usr/local/lib/certnet-mirror/configure"
API = "mirror+https://mirrors.cernet.edu.cn/api/apt/mirrorlist/"


class Mirrors(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def run_mod(self, distro, arch="x86_64", version="44"):
        self.put("etc/os-release", f'ID={distro}\nVERSION_ID="{version}"\n')
        return subprocess.run(
            ["bash", str(CONFIGURE), str(self.root), arch],
            check=True, text=True, capture_output=True,
        ).stdout

    def assert_repeatable(self, distro, arch="x86_64", version="44"):
        snapshot = {p.relative_to(self.root): p.read_bytes()
                    for p in self.root.rglob("*") if p.is_file()}
        timestamps = {p: (self.root / p).stat().st_mtime_ns for p in snapshot}
        self.run_mod(distro, arch, version)
        self.assertEqual(snapshot, {p.relative_to(self.root): p.read_bytes()
                                   for p in self.root.rglob("*") if p.is_file()})
        for name in snapshot:
            if str(name) != "etc/os-release":
                self.assertEqual(timestamps[name], (self.root / name).stat().st_mtime_ns)

    def test_ubuntu_legacy_options_backups_and_third_party(self):
        original = (
            "deb [arch=amd64 signed-by=/keys/ubuntu.gpg] http://archive.ubuntu.com/ubuntu/ noble main\n"
            "deb-src https://hk.archive.ubuntu.com/ubuntu noble-updates universe\n"
            "deb http://security.ubuntu.com/ubuntu noble-security main\n"
            "# deb http://archive.ubuntu.com/ubuntu noble-proposed main\n"
            "deb https://ppa.launchpadcontent.net/example/ubuntu noble main\n"
            "deb https://archive.ubuntu.com.evil.invalid/ubuntu noble main\n"
        )
        path = self.put("etc/apt/sources.list", original)
        path.chmod(0o640)
        self.run_mod("ubuntu")
        result = path.read_text()
        self.assertIn(f"deb [arch=amd64 signed-by=/keys/ubuntu.gpg] {API}ubuntu noble main", result)
        self.assertIn(f"{API}ubuntu?official_index=1 noble-security", result)
        self.assertIn("ppa.launchpadcontent.net", result)
        self.assertIn("https://archive.ubuntu.com.evil.invalid/ubuntu", result)
        self.assertIn("# deb http://archive.ubuntu.com/ubuntu noble-proposed main", result)
        self.assertEqual(path.with_name(path.name + ".certnet-mirror.bak").read_text(), original)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assert_repeatable("ubuntu")

    def test_ubuntu_arm_uses_ports_even_with_archive_url(self):
        path = self.put("etc/apt/sources.list", "deb http://archive.ubuntu.com/ubuntu noble main\ndeb http://ports.ubuntu.com/ubuntu-ports noble-security main\n")
        self.run_mod("ubuntu", "aarch64")
        self.assertIn(f"{API}ubuntu-ports noble main", path.read_text())
        self.assertIn(f"{API}ubuntu-ports?official_index=1 noble-security", path.read_text())
        self.assert_repeatable("ubuntu", "aarch64")

    def test_ubuntu_deb822_splits_mixed_security_and_keeps_signed_by(self):
        path = self.put("etc/apt/sources.list.d/ubuntu.sources", "Types: deb deb-src\nURIs: http://archive.ubuntu.com/ubuntu/\nSuites: noble noble-updates\n noble-security\nComponents: main universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\nEnabled: no\n")
        self.run_mod("ubuntu")
        result = path.read_text()
        self.assertIn("Suites: noble noble-updates\n", result)
        self.assertIn("Suites: noble-security\n", result)
        self.assertEqual(result.count("Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg"), 2)
        self.assertEqual(result.count("Enabled: no"), 2)
        self.assertIn(f"URIs: {API}ubuntu?official_index=1", result)
        self.assert_repeatable("ubuntu")

    def test_deb822_folded_uris_and_inline_signing_key(self):
        path = self.put("etc/apt/sources.list.d/debian.sources", "Types: deb\nURIs:\n https://deb.debian.org/debian\nSuites: trixie\nComponents: main\nSigned-By:\n -----BEGIN PGP PUBLIC KEY BLOCK-----\n .\n abcde\n -----END PGP PUBLIC KEY BLOCK-----\n")
        self.run_mod("debian")
        self.assertIn(f"\n {API}debian\n", path.read_text())
        self.assertIn(" .\n abcde\n -----END PGP PUBLIC KEY BLOCK-----", path.read_text())
        self.assert_repeatable("debian")

    def test_debian_security_and_backports(self):
        path = self.put("etc/apt/sources.list", "deb http://deb.debian.org/debian trixie main non-free-firmware\ndeb http://deb.debian.org/debian trixie-backports main\ndeb http://security.debian.org/debian-security/ trixie-security main\n")
        self.run_mod("debian")
        self.assertIn(f"{API}debian trixie-backports main", path.read_text())
        self.assertIn(f"{API}debian-security?official_index=1 trixie-security", path.read_text())
        self.assert_repeatable("debian")

    def test_debian_deb822_third_party_stanza_unchanged(self):
        third = "Types: deb\nURIs: https://vendor.invalid/apt\nSuites: stable\nSigned-By: /keys/vendor.gpg\n"
        path = self.put("etc/apt/sources.list.d/debian.sources", f"Types: deb\nURIs: http://deb.debian.org/debian-security\nSuites: trixie-security\nSigned-By: /keys/debian.gpg\n\n{third}")
        self.run_mod("debian", "aarch64")
        self.assertIn(third, path.read_text())
        self.assertIn(f"{API}debian-security?official_index=1", path.read_text())
        self.assert_repeatable("debian", "aarch64")

    def test_kali(self):
        path = self.put("etc/apt/sources.list", "deb http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware\n")
        self.run_mod("kali", "aarch64")
        self.assertEqual(path.read_text(), "deb https://mirrors.cernet.edu.cn/kali kali-rolling main contrib non-free non-free-firmware\n")
        self.assert_repeatable("kali", "aarch64")

    def test_alpine_release_tag_and_new_repository_directory(self):
        path = self.put("etc/apk/repositories", "https://dl-cdn.alpinelinux.org/alpine/v3.24/main\n@edge https://dl-2.alpinelinux.org/alpine/edge/testing\nhttps://vendor.invalid/alpine/repo\n# https://dl-cdn.alpinelinux.org/alpine/edge/community\n")
        extra = self.put("etc/apk/repositories.d/community.list", "https://dl-cdn.alpinelinux.org/alpine/v3.24/community\n")
        self.run_mod("alpine")
        self.assertIn("https://mirrors.cernet.edu.cn/alpine/v3.24/main", path.read_text())
        self.assertIn("@edge https://mirrors.cernet.edu.cn/alpine/edge/testing", path.read_text())
        self.assertIn("vendor.invalid", path.read_text())
        self.assertIn("# https://dl-cdn.alpinelinux.org", path.read_text())
        self.assertIn("https://mirrors.cernet.edu.cn/alpine/v3.24/community", extra.read_text())
        self.assert_repeatable("alpine")

    def test_arch_x86_fallback_and_signature_policy(self):
        path = self.put("etc/pacman.d/mirrorlist", "Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch\n")
        signature = self.put("etc/pacman.conf", "SigLevel = Required DatabaseOptional\n")
        self.run_mod("arch")
        self.assertTrue(path.read_text().startswith("Server = https://mirrors.cernet.edu.cn/archlinux/$repo/os/$arch\n"))
        self.assertIn("geo.mirror.pkgbuild.com", path.read_text())
        self.assertEqual(signature.read_text(), "SigLevel = Required DatabaseOptional\n")
        self.assert_repeatable("arch")

    def test_arch_arm_distinct_repository_layout(self):
        path = self.put("etc/pacman.d/mirrorlist", "Server = http://mirror.archlinuxarm.org/$arch/$repo\n")
        self.run_mod("arch", "aarch64")
        self.assertTrue(path.read_text().startswith("Server = https://mirrors.cernet.edu.cn/archlinuxarm/$arch/$repo\n"))
        self.assert_repeatable("arch", "aarch64")

    def test_fedora_legacy_only_base_and_updates(self):
        path = self.put("etc/yum.repos.d/fedora.repo", "[fedora]\nmetalink=https://mirrors.fedoraproject.org/metalink?repo=fedora-$releasever&arch=$basearch\ngpgcheck=1\ngpgkey=file:///etc/key\nenabled=1\n\n[fedora-debuginfo]\nenabled=0\nmetalink=https://original.invalid/debug\n")
        updates = self.put("etc/yum.repos.d/fedora-updates.repo", "[updates]\nbaseurl=https://original.invalid/updates\ngpgcheck=1\n")
        third = self.put("etc/yum.repos.d/vendor.repo", "[vendor]\nbaseurl=https://vendor.invalid/repo\ngpgcheck=1\n")
        self.run_mod("fedora", version="43")
        self.assertIn("gpgcheck=1\ngpgkey=file:///etc/key", path.read_text())
        self.assertIn("mirrorlist=https://mirrors.cernet.edu.cn/api/rpm/mirrorlist/fedora/releases/$releasever/Everything/$basearch/os/", path.read_text())
        self.assertIn("[fedora-debuginfo]\nenabled=0\nmetalink=https://original.invalid/debug", path.read_text())
        self.assertIn("mirrorlist=https://mirrors.cernet.edu.cn/api/rpm/mirrorlist/fedora/updates/$releasever", updates.read_text())
        self.assertEqual(third.read_text(), "[vendor]\nbaseurl=https://vendor.invalid/repo\ngpgcheck=1\n")
        self.assertFalse(third.with_name(third.name + ".certnet-mirror.bak").exists())
        self.assert_repeatable("fedora", version="43")

    def test_fedora_44_and_45_override_preserves_vendor_repos(self):
        for version in ["44", "45"]:
            with self.subTest(version=version):
                vendor = self.put("usr/share/dnf5/repos.d/fedora.repo", "[fedora]\ngpgcheck=1\nmetalink=original\n")
                self.run_mod("fedora", version=version)
                override = self.root / "etc/dnf/repos.override.d/99-certnet-mirror.repo"
                self.assertIn("baseurl=\nmetalink=\nmirrorlist=", override.read_text())
                self.assertNotIn("gpgcheck", override.read_text())
                self.assertIn("metalink=original", vendor.read_text())
                self.assert_repeatable("fedora", version=version)

    def test_redhat_ubi_and_unknown_are_explicit_noops(self):
        path = self.put("etc/yum.repos.d/ubi.repo", "[ubi-9-baseos-rpms]\nbaseurl=https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi9/9/$basearch/baseos/os\ngpgcheck=1\n")
        original = path.read_bytes()
        self.assertIn("no CERNET equivalent", self.run_mod("rhel"))
        self.assertEqual(path.read_bytes(), original)
        self.assertIn("Unsupported distribution", self.run_mod("unknown"))
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(path.with_name(path.name + ".certnet-mirror.bak").exists())

    def test_missing_configuration_is_not_synthesized(self):
        self.run_mod("ubuntu")
        self.assertFalse((self.root / "etc/apt/sources.list").exists())
        self.assertIn("No pacman mirrorlist", self.run_mod("arch"))

    def test_arch_vendor_os_release_fallback(self):
        self.put("usr/lib/os-release", 'ID=arch\n')
        path = self.put("etc/pacman.d/mirrorlist", "Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch\n")
        subprocess.run(["bash", str(CONFIGURE), str(self.root), "x86_64"], check=True, capture_output=True)
        self.assertTrue(path.read_text().startswith("Server = https://mirrors.cernet.edu.cn/archlinux/"))


if __name__ == "__main__":
    unittest.main()
