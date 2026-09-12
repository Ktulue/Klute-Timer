"""Static checks that the build files stay in step with the Python they depend on.

They catch drift (a hardcoded version, a renamed mutex) cheaply. They do not
replace building and installing: the installed exe is the arbiter.
"""
import os
import re

from src.single_instance import APP_MUTEX_NAME
from src.version import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TestSpec:
    def test_reads_version_from_src_version(self):
        spec = _read("KluteTimer.spec")
        assert "from src.version import __version__, version_tuple" in spec

    def test_passes_version_resource_to_exe(self):
        spec = _read("KluteTimer.spec")
        assert re.search(r"version\s*=\s*version_info", spec)

    def test_has_no_version_literal(self):
        spec = _read("KluteTimer.spec")
        assert not re.search(r"['\"]\d+\.\d+\.\d+['\"]", spec)


class TestInstallerScript:
    ISS = ("installer", "KluteTimer.iss")

    def _directive(self, name: str) -> str:
        match = re.search(rf"^\s*{name}=(.*)$", _read(*self.ISS), re.MULTILINE)
        assert match, f"{name}= missing from KluteTimer.iss"
        return match.group(1).strip()

    def test_installs_per_user_without_uac(self):
        assert self._directive("PrivilegesRequired") == "lowest"
        assert self._directive("DefaultDirName") == r"{autopf}\KluteTimer"
        assert self._directive("DisableDirPage") == "yes"

    def test_app_id_is_fixed(self):
        assert self._directive("AppId") == "{{32085ADC-A6C1-4CF4-A9CE-7DAD72791E68}"

    def test_detects_running_app_by_the_same_mutex_name(self):
        assert self._directive("AppMutex") == APP_MUTEX_NAME
        assert self._directive("CloseApplications") == "no"

    def test_identity_matches_the_spec(self):
        assert self._directive("AppName") == "Klute Timer"
        assert self._directive("AppPublisher") == "Ktulue"
        assert self._directive("UninstallDisplayName") == "Klute Timer"

    def test_version_comes_only_from_the_command_line(self):
        iss = _read(*self.ISS)
        assert self._directive("AppVersion") == "{#AppVersion}"
        assert "#ifndef AppVersion" in iss
        assert __version__ not in iss
        assert not re.search(r"\d+\.\d+\.\d+", iss)

    def test_upgrade_clears_old_bundled_libraries(self):
        assert re.search(
            r'^\[InstallDelete\]\s*^Type: filesandordirs; Name: "\{app\}\\_internal"',
            _read(*self.ISS),
            re.MULTILINE,
        )

    def test_uninstall_removes_the_whole_install_folder(self):
        assert re.search(
            r'^\[UninstallDelete\]\s*^Type: filesandordirs; Name: "\{app\}"',
            _read(*self.ISS),
            re.MULTILINE,
        )

    def test_data_prompt_defaults_to_keep_and_skips_silent_uninstall(self):
        iss = _read(*self.ISS)
        parts = re.split(r"^\[Code\]\s*$", iss, maxsplit=1, flags=re.MULTILINE)
        assert len(parts) == 2, "[Code] section missing from KluteTimer.iss"
        code = parts[1]
        assert "not UninstallSilent" in code
        assert "MB_YESNO or MB_DEFBUTTON2" in code
        assert r"{userappdata}\KluteTimer" in code
        assert "DirExists" in code
        assert "DelTree" in code
        assert "= IDYES" in code


class TestBuildScript:
    def test_reads_version_from_src_version(self):
        assert "from src.version import __version__" in _read("build.bat")

    def test_passes_version_to_inno(self):
        bat = _read("build.bat")
        assert "/DAppVersion=%KT_VERSION%" in bat
        assert r"installer\KluteTimer.iss" in bat

    def test_explains_how_to_get_inno_when_missing(self):
        assert "winget install JRSoftware.InnoSetup" in _read("build.bat")

    def test_has_no_version_literal(self):
        assert not re.search(r"\d+\.\d+\.\d+", _read("build.bat"))

    def test_shortcut_script_is_retired(self):
        assert not os.path.exists(os.path.join(ROOT, "scripts", "create_shortcut.ps1"))
        assert "create_shortcut" not in _read("build.bat")


class TestReadme:
    def test_no_longer_mentions_the_shortcut_script(self):
        assert "create_shortcut" not in _read("README.md")

    def test_documents_installed_apps_uninstall_and_smartscreen(self):
        readme = _read("README.md")
        assert "Installed apps" in readme
        assert "Run anyway" in readme
        assert "winget install JRSoftware.InnoSetup" in readme

    def test_keeps_the_support_section(self):
        assert "ko-fi.com/ktulue" in _read("README.md")
