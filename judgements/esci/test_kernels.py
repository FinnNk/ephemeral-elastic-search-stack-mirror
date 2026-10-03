"""Reject incomplete profiles, runtime overrides and changed kernel selections."""

import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from esci.kernels import configure_kernels, read_profile, verify_selected
from esci.runtime import INFERENCE_PROTOCOL


@pytest.fixture
def frozen(tmp_path):
    shutil.copy2(Path(__file__).with_name("kernel-profile.json"), tmp_path / "kernel-profile.json")
    profile = json.loads((tmp_path / "kernel-profile.json").read_text())
    (tmp_path / "kernel-configs").mkdir()
    for name, definition in profile["kernels"].items():
        (tmp_path / "kernel-configs" / (name + ".json")).write_text(json.dumps(definition))
    return tmp_path, profile


def test_missing_or_changed_kernel_cannot_retune(frozen):
    bundle, profile = frozen
    digest = INFERENCE_PROTOCOL["kernel_profile_sha256"]
    read_profile(bundle, digest)
    name = next(iter(profile["kernels"]))
    path = bundle / "kernel-configs" / (name + ".json")
    original = path.read_bytes()
    path.unlink()
    with pytest.raises(RuntimeError, match="Missing"):
        read_profile(bundle, digest)
    path.write_bytes(original)
    changed = json.loads(path.read_text())
    changed["default_config"]["num_warps"] = 1
    path.write_text(json.dumps(changed))
    with pytest.raises(RuntimeError, match="Changed"):
        read_profile(bundle, digest)
    path.write_bytes(original)
    (bundle / "kernel-profile.json").write_text("{}")
    with pytest.raises(RuntimeError, match="differs"):
        read_profile(bundle, digest)


def test_hardware_and_environment_are_checked(frozen, monkeypatch):
    bundle, profile = frozen
    for name in ("FLA_CACHE_MODE", "FLA_CONFIG_DIR", "FLA_GPU_NAME"):
        monkeypatch.delenv(name, raising=False)
    torch = SimpleNamespace(cuda=SimpleNamespace(
        get_device_name=lambda: profile["gpu"],
        get_device_capability=lambda: profile["capability"]),
        version=SimpleNamespace(cuda=profile["cuda"]), __version__=profile["torch"])
    digest = INFERENCE_PROTOCOL["kernel_profile_sha256"]
    configure_kernels(torch, bundle, digest)
    monkeypatch.setenv("FLA_CACHE_MODE", "disabled")
    with pytest.raises(RuntimeError, match="requires"):
        configure_kernels(torch, bundle, digest)
    monkeypatch.setenv("FLA_CACHE_MODE", "default")
    torch.cuda.get_device_name = lambda: "Other GPU"
    with pytest.raises(RuntimeError, match="outside"):
        configure_kernels(torch, bundle, digest)


def test_selected_settings_cannot_drift(frozen):
    _, profile = frozen
    selected = {name: [definition["default_config"]] for name, definition in profile["kernels"].items()}
    verify_selected(profile, selected, require_all=True)
    missing = dict(selected)
    missing.pop(next(iter(missing)))
    with pytest.raises(RuntimeError, match="Missing"):
        verify_selected(profile, missing, require_all=True)
    with pytest.raises(RuntimeError, match="unexpected"):
        verify_selected(profile, {**selected, "new_kernel": []})
    changed = dict(selected)
    name = next(iter(changed))
    changed[name] = [{**changed[name][0], "num_warps": 1}]
    with pytest.raises(RuntimeError, match="unexpected settings"):
        verify_selected(profile, changed)
