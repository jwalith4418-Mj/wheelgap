import pytest
from packaging.utils import parse_wheel_filename

from wheelgap.targets import (
    DEFAULT_PLATFORMS,
    PLATFORMS,
    Target,
    TargetError,
    build_targets,
    manylinux_platforms,
    parse_python,
    resolve_platform,
)


def accepts(target: Target, filename: str) -> bool:
    return target.accepts(parse_wheel_filename(filename)[3])


def t(platform: str, py: str = "3.13", **kw) -> Target:
    ma, mi, ft = parse_python(py)
    return Target(ma, mi, ft, platform, **kw)


@pytest.mark.parametrize(
    "spec,expected",
    [("3.13", (3, 13, False)), ("3.14t", (3, 14, True)), ("cp314t", (3, 14, True)), ("312", (3, 12, False))],
)
def test_parse_python(spec, expected):
    assert parse_python(spec) == expected


def test_parse_python_rejects_garbage():
    with pytest.raises(TargetError):
        parse_python("latest")


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("alpine", "musl-x86_64"),
        ("linux-arm64", "linux-aarch64"),
        ("linux/amd64", "linux-x86_64"),
        ("linux/arm64", "linux-aarch64"),
        ("linux/arm64/v8", "linux-aarch64"),
        (" LINUX/ARM64/V8 ", "linux-aarch64"),
        ("windows", "win-amd64"),
        ("MACOS_INTEL", "macos-x86_64"),
    ],
)
def test_aliases(alias, expected):
    assert resolve_platform(alias) == expected


def test_docker_platform_list():
    targets = build_targets(["3.13"], ["linux/amd64,linux/arm64,linux/arm64/v8"])
    assert [target.platform for target in targets] == ["linux-x86_64", "linux-aarch64"]


def test_unknown_platform():
    with pytest.raises(TargetError, match="unknown target"):
        resolve_platform("solaris")


def test_manylinux_includes_legacy_aliases():
    plats = manylinux_platforms("x86_64", (2, 28))
    assert plats[0] == "manylinux_2_28_x86_64"
    assert "manylinux2014_x86_64" in plats and "manylinux1_x86_64" in plats
    assert "manylinux1_aarch64" not in manylinux_platforms("aarch64", (2, 28))
    assert "manylinux2014_aarch64" in manylinux_platforms("aarch64", (2, 28))


def test_glibc_ceiling():
    assert accepts(t("linux-x86_64", glibc=(2, 36)), "x-1-cp313-cp313-manylinux_2_34_x86_64.whl")
    assert not accepts(t("linux-x86_64", glibc=(2, 31)), "x-1-cp313-cp313-manylinux_2_34_x86_64.whl")
    assert accepts(t("linux-x86_64"), "x-1-cp313-cp313-manylinux2014_x86_64.whl")


def test_glibc_and_musl_dont_mix():
    assert not accepts(t("musl-x86_64"), "x-1-cp313-cp313-manylinux_2_17_x86_64.whl")
    assert not accepts(t("linux-x86_64"), "x-1-cp313-cp313-musllinux_1_1_x86_64.whl")
    assert accepts(t("musl-x86_64"), "x-1-cp313-cp313-musllinux_1_1_x86_64.whl")


def test_arch_matters():
    assert not accepts(t("linux-aarch64"), "x-1-cp313-cp313-manylinux_2_17_x86_64.whl")
    assert not accepts(t("win-arm64"), "x-1-cp313-cp313-win_amd64.whl")
    assert accepts(t("win-arm64"), "x-1-cp313-cp313-win_arm64.whl")


def test_macos_universal2_and_minimum_version():
    assert accepts(t("macos-arm64"), "x-1-cp313-cp313-macosx_10_13_universal2.whl")
    assert accepts(t("macos-x86_64"), "x-1-cp313-cp313-macosx_10_9_x86_64.whl")
    assert not accepts(t("macos-arm64", macos=(14, 0)), "x-1-cp313-cp313-macosx_15_0_arm64.whl")
    assert accepts(t("macos-arm64", macos=(15, 0)), "x-1-cp313-cp313-macosx_15_0_arm64.whl")


def test_python_version_matters():
    assert not accepts(t("linux-x86_64", "3.14"), "x-1-cp313-cp313-manylinux_2_17_x86_64.whl")
    assert accepts(t("linux-x86_64", "3.14"), "x-1-cp310-abi3-manylinux_2_17_x86_64.whl")
    assert not accepts(t("linux-x86_64", "3.11"), "x-1-cp312-abi3-manylinux_2_17_x86_64.whl")


def test_free_threading():
    ft = t("linux-x86_64", "3.14t")
    assert accepts(ft, "x-1-cp314-cp314t-manylinux_2_17_x86_64.whl")
    assert not accepts(ft, "x-1-cp314-cp314-manylinux_2_17_x86_64.whl")
    assert not accepts(ft, "x-1-cp310-abi3-manylinux_2_17_x86_64.whl")
    assert not accepts(t("linux-x86_64", "3.14"), "x-1-cp314-cp314t-manylinux_2_17_x86_64.whl")


def test_pure_python_everywhere():
    for plat in PLATFORMS:
        assert accepts(t(plat, "3.14t"), "x-1-py3-none-any.whl"), plat
    assert not accepts(t("linux-x86_64"), "x-1-py2-none-any.whl")


def test_marker_env():
    env = t("win-arm64", "3.14").marker_env
    assert env["sys_platform"] == "win32" and env["platform_machine"] == "ARM64"
    assert env["python_version"] == "3.14"
    assert t("musl-aarch64").marker_env["platform_machine"] == "aarch64"


def test_build_targets_defaults_and_all():
    ts = build_targets(["3.13"], [])
    assert [x.platform for x in ts] == DEFAULT_PLATFORMS
    ts = build_targets(["3.13,3.14t"], ["all"])
    assert len(ts) == 2 * len(PLATFORMS)
    ts = build_targets(["3.13"], ["alpine,linux", "alpine"])
    assert [x.platform for x in ts] == ["musl-x86_64", "linux-x86_64"]


def test_build_targets_accepts_docker_platform_list():
    ts = build_targets(["3.13"], ["linux/amd64,linux/arm64,linux/arm64/v8"])
    assert [x.platform for x in ts] == ["linux-x86_64", "linux-aarch64"]


def test_build_targets_bad_glibc():
    with pytest.raises(TargetError):
        build_targets(["3.13"], [], glibc="new")
