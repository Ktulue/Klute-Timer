"""Static checks that the build files stay in step with the Python they depend on.

They catch drift (a hardcoded version, a renamed mutex) cheaply. They do not
replace building and installing: the installed exe is the arbiter.
"""
import os
import re

from src.paths import APP_FOLDER_NAME
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


def _section(text: str, name: str) -> str:
    match = re.search(
        rf"^\[{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert match, f"[{name}] section missing"
    return match.group(1)


def _entries(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.strip() and not line.startswith(";")]


def _pascal_block(code: str, start_pattern: str) -> str:
    """The text from start_pattern through the end matching the next begin."""
    match = re.search(start_pattern, code)
    assert match, f"{start_pattern!r} not found in [Code]"
    depth = 0
    for token in re.finditer(r"\b(begin|end)\b", code[match.end():], re.IGNORECASE):
        depth += 1 if token.group(1).lower() == "begin" else -1
        if depth == 0:
            return code[match.start():match.end() + token.end()]
    raise AssertionError(f"unbalanced begin/end after {start_pattern!r}")


class TestInstallerScript:
    ISS = ("installer", "KluteTimer.iss")

    def _code(self) -> str:
        parts = re.split(r"^\[Code\]\s*$", _read(*self.ISS), maxsplit=1, flags=re.MULTILINE)
        assert len(parts) == 2, "[Code] section missing from KluteTimer.iss"
        return parts[1]

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

    def test_every_mutex_name_in_the_file_matches(self):
        iss = _read(*self.ISS)
        names = re.findall(r"KluteTimer-\w+Mutex", iss)
        assert len(names) >= 2, "expected the mutex name to appear at least twice (Setup + Code)"
        for name in names:
            assert name == APP_MUTEX_NAME

    def test_blocks_install_while_the_app_is_running(self):
        iss = _read(*self.ISS)
        parts = re.split(r"^\[Code\]\s*$", iss, maxsplit=1, flags=re.MULTILINE)
        assert len(parts) == 2, "[Code] section missing from KluteTimer.iss"
        code = parts[1]
        assert "function PrepareToInstall" in code
        assert "CheckForMutexes(" in code
        assert APP_MUTEX_NAME in code

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

    def test_install_delete_only_runs_for_the_default_install_dir(self):
        match = re.search(
            r'^\[InstallDelete\]\s*^(Type: filesandordirs; Name: "\{app\}\\_internal".*)$',
            _read(*self.ISS),
            re.MULTILINE,
        )
        assert match, "[InstallDelete] entry missing"
        assert "Check: IsDefaultInstallDir" in match.group(1)

    def test_files_never_package_user_data_left_in_the_build_folder(self):
        entries = _entries(_section(_read(*self.ISS), "Files"))
        assert len(entries) == 1
        assert 'Excludes: "config.json,logs\\*,output\\*"' in entries[0]

    def test_refuses_to_compile_with_inno_older_than_six_seven(self):
        iss = _read(*self.ISS)
        guard = re.search(
            r"^#if Ver < EncodeVer\(6,7,0\)\s*^\s*#error .*$\s*^#endif", iss, re.MULTILINE
        )
        assert guard, "Inno Setup version guard missing"
        assert "winget upgrade JRSoftware.InnoSetup" in guard.group(0)
        assert iss.index("#ifndef AppVersion") < guard.start()

    def test_post_install_launch_is_skipped_when_setup_runs_elevated(self):
        entries = _entries(_section(_read(*self.ISS), "Run"))
        assert len(entries) == 1
        assert "postinstall" in entries[0]
        check = re.search(r"Check: ([^;]+?)\s*(;|$)", entries[0])
        assert check, "[Run] launch entry has no Check"
        assert check.group(1) in ("not IsAdmin", "IsNotAdmin")
        if check.group(1) == "IsNotAdmin":
            assert "function IsNotAdmin: Boolean" in self._code()

    def test_script_is_pure_ascii(self):
        with open(os.path.join(ROOT, *self.ISS), "rb") as f:
            f.read().decode("ascii")

    def test_uninstall_removes_the_whole_install_folder(self):
        assert re.search(
            r'^\[UninstallDelete\]\s*^Type: filesandordirs; Name: "\{app\}"',
            _read(*self.ISS),
            re.MULTILINE,
        )

    def test_uninstall_delete_only_runs_for_the_default_install_dir(self):
        iss = _read(*self.ISS)
        match = re.search(
            r'^\[UninstallDelete\]\s*^(Type: filesandordirs; Name: "\{app\}".*)$',
            iss,
            re.MULTILINE,
        )
        assert match, "[UninstallDelete] entry missing"
        assert "Check: IsDefaultInstallDir" in match.group(1)
        parts = re.split(r"^\[Code\]\s*$", iss, maxsplit=1, flags=re.MULTILINE)
        assert len(parts) == 2, "[Code] section missing from KluteTimer.iss"
        code = parts[1]
        assert "function IsDefaultInstallDir: Boolean" in code
        assert "{autopf}\\KluteTimer" in code

    def test_data_prompt_defaults_to_keep_and_skips_silent_uninstall(self):
        code = self._code()
        assert "not UninstallSilent" in code
        assert "MB_YESNO or MB_DEFBUTTON2" in code
        assert "{userappdata}\\" + APP_FOLDER_NAME in code
        assert "DirExists" in code
        assert "DelTree" in code
        assert "not DelTree" in code
        assert "= IDYES" in code

    def test_data_prompt_runs_before_the_app_mutex_check(self):
        code = self._code()
        prompt = _pascal_block(code, r"CurUninstallStep = usAppMutexCheck\b")
        assert "not UninstallSilent" in prompt
        assert "DirExists" in prompt
        assert "MsgBox(" in prompt
        assert "MB_YESNO or MB_DEFBUTTON2" in prompt
        assert "DelTree" not in prompt
        assert "usUninstall" not in code

    def test_data_is_deleted_only_after_the_program_is_removed(self):
        code = self._code()
        post = _pascal_block(code, r"CurUninstallStep = usPostUninstall\b")
        assert "not DelTree(" in post
        assert code.count("DelTree(") == 1

    def test_data_prompt_says_yes_removes_everything_in_the_folder(self):
        code = " ".join(self._code().split()).replace("' + '", "")
        assert "'Also delete your Klute Timer data folder?'" in code
        assert (
            "This removes your settings, presets, logs, timer text files, and anything "
            "else saved there, such as custom sounds. Choose No to keep it for a future "
            "reinstall. A custom output folder you chose somewhere else is never deleted."
        ) in code

    def test_icons_have_a_working_dir(self):
        iss = _read(*self.ISS)
        icons_match = re.search(r"^\[Icons\]\s*$(.*?)^\[", iss, re.MULTILINE | re.DOTALL)
        assert icons_match, "[Icons] section missing from KluteTimer.iss"
        icon_lines = [line for line in icons_match.group(1).splitlines() if line.strip()]
        assert len(icon_lines) == 2
        for line in icon_lines:
            assert 'WorkingDir: "{app}"' in line


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

    def test_volume_mixer_names_klute_timer(self):
        readme = " ".join(_read("README.md").split())
        assert "Find the **Klute Timer** entry" in readme
        assert "(or **Python** when running from source)" in readme
        assert "When running from source, this controls all Python processes" in readme

    def test_sound_override_note_points_at_appdata(self):
        readme = " ".join(_read("README.md").split())
        assert "%APPDATA%\\KluteTimer\\sounds\\" in readme
        assert "install folder is replaced on upgrade" in readme
        assert "then set `finished_sound` in `config.json` to point at the amplified copy" not in readme


class TestGitAttributes:
    def test_bat_files_use_crlf_line_endings(self):
        assert "*.bat text eol=crlf" in _read(".gitattributes").splitlines()
