"""find_data_dir 五分支（口径 K11：显式 > 环境变量 > 打包 > exe 同侧 > CWD 上溯）。"""

import os
import sys

import pytest

from sdc import paths


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """隔离三个外部输入：环境变量、_MEIPASS、解释器路径与工作目录。"""
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", os.path.join(str(tmp_path), "noexe", "python.exe"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _touch_data_dir(base):
    os.makedirs(os.path.join(base, "clauses"), exist_ok=True)
    return os.path.abspath(base)


def test_explicit_argument_wins(clean_env):
    target = os.path.join(str(clean_env), "pointed")
    assert paths.find_data_dir(target) == os.path.abspath(target)


def test_explicit_does_not_need_to_exist(clean_env):
    """显式分支原样返回，缺失由调用方报错（selfcheck 里是退出码 2）。"""
    missing = os.path.join(str(clean_env), "missing")
    assert paths.find_data_dir(missing) == os.path.abspath(missing)


def test_env_var_second(clean_env, monkeypatch):
    value = _touch_data_dir(os.path.join(str(clean_env), "envdata"))
    monkeypatch.setenv(paths.ENV_VAR, value)
    assert paths.find_data_dir() == value


def test_meipass_third(clean_env, monkeypatch):
    meipass = os.path.join(str(clean_env), "bundle")
    inner = _touch_data_dir(os.path.join(meipass, "data"))
    monkeypatch.setattr(sys, "_MEIPASS", meipass, raising=False)
    assert paths.find_data_dir() == inner


def test_internal_before_sibling_data(clean_env, monkeypatch):
    exe_dir = os.path.join(str(clean_env), "dist")
    internal = _touch_data_dir(os.path.join(exe_dir, "_internal", "data"))
    _touch_data_dir(os.path.join(exe_dir, "data"))
    monkeypatch.setattr(sys, "executable", os.path.join(exe_dir, "sdc.exe"))
    assert paths.find_data_dir() == internal


def test_sibling_data_when_no_internal(clean_env, monkeypatch):
    exe_dir = os.path.join(str(clean_env), "dist2")
    sibling = _touch_data_dir(os.path.join(exe_dir, "data"))
    monkeypatch.setattr(sys, "executable", os.path.join(exe_dir, "sdc.exe"))
    assert paths.find_data_dir() == sibling


def test_cwd_walk_up(clean_env, monkeypatch):
    root = os.path.join(str(clean_env), "proj")
    found = _touch_data_dir(os.path.join(root, "data"))
    deep = os.path.join(root, "src", "nested")
    os.makedirs(deep, exist_ok=True)
    monkeypatch.chdir(deep)
    assert paths.find_data_dir() == found


def test_raises_when_nothing_found(clean_env):
    with pytest.raises(paths.DataDirNotFound):
        paths.find_data_dir()
