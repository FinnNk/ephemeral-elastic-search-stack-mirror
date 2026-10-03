"""Validate and select the immutable FLA profile before importing its kernels."""

import hashlib
import json
import os
from pathlib import Path
import sys


def read_profile(bundle, expected_sha):
    path = Path(bundle) / "kernel-profile.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise RuntimeError("Kernel profile differs from the inference protocol.")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("format") != "esci-kernel-profile-v1" or len(profile["kernels"]) != 6:
        raise RuntimeError("Incomplete kernel profile.")
    folder = Path(bundle) / "kernel-configs"
    expected_files = {name + ".json" for name in profile["kernels"]}
    if not folder.is_dir() or {p.name for p in folder.iterdir()} != expected_files:
        raise RuntimeError("Missing or unexpected kernel configuration files.")
    for name, expected in profile["kernels"].items():
        if json.loads((folder / (name + ".json")).read_text(encoding="utf-8")) != expected:
            raise RuntimeError(f"Changed kernel configuration: {name}.")
    return profile, folder.resolve()


def configure_kernels(torch, bundle, expected_sha):
    profile, folder = read_profile(bundle, expected_sha)
    if (torch.cuda.get_device_name() != profile["gpu"]
            or list(torch.cuda.get_device_capability()) != profile["capability"]
            or torch.version.cuda != profile["cuda"]
            or torch.__version__.split("+")[0] != profile["torch"]):
        raise RuntimeError("GPU or CUDA runtime is outside the frozen kernel profile.")
    if "FLA_GPU_NAME" in os.environ:
        raise RuntimeError("A GPU name override is not permitted.")
    if os.environ.get("FLA_CACHE_MODE", "default") != "default":
        raise RuntimeError("The frozen profile requires FLA_CACHE_MODE=default.")
    configured = os.environ.get("FLA_CONFIG_DIR")
    if configured is not None and Path(configured).resolve() != folder:
        raise RuntimeError("FLA_CONFIG_DIR must select the immutable bundle.")
    if any(name == "fla" or name.startswith("fla.") for name in sys.modules):
        if configured is None or os.environ.get("FLA_CACHE_MODE") != "default":
            raise RuntimeError("FLA was imported before the frozen profile was selected.")
    os.environ["FLA_CACHE_MODE"] = "default"
    os.environ["FLA_CONFIG_DIR"] = str(folder)
    return profile


def selected_configurations():
    from triton.runtime.autotuner import Autotuner

    found = {}
    seen = set()
    for name, module in list(sys.modules.items()):
        if not name.startswith("fla.") or module is None:
            continue
        for value in list(vars(module).values()):
            current = value
            while current is not None and id(current) not in seen:
                seen.add(id(current))
                if isinstance(current, Autotuner) and current.cache:
                    kernel = getattr(current, "kernel_name", None)
                    if kernel is None:
                        raise RuntimeError("An FLA kernel bypassed its configuration loader.")
                    found.setdefault(kernel, []).extend(
                        {"kwargs": config.kwargs, "num_warps": config.num_warps,
                         "num_stages": config.num_stages}
                        for config in current.cache.values())
                current = getattr(current, "fn", None)
    return found


def verify_selections(bundle, expected_sha, require_all=False):
    profile, folder = read_profile(bundle, expected_sha)
    from fla.ops.utils import cache

    if (cache.FLA_CACHE_MODE.value != "default"
            or cache.get_fla_config_dir().resolve() != folder):
        raise RuntimeError("FLA is using an undeclared cache mode or directory.")
    for name, definition in profile["kernels"].items():
        if cache.load_cached_config(name) != definition["default_config"]:
            raise RuntimeError(f"FLA did not load the frozen configuration: {name}.")
    selected = selected_configurations()
    verify_selected(profile, selected, require_all)
    return selected


def verify_selected(profile, selected, require_all=False):
    expected = profile["kernels"]
    if set(selected) - set(expected) or (require_all and set(selected) != set(expected)):
        raise RuntimeError("Missing or unexpected selected FLA kernels.")
    for name, configurations in selected.items():
        if not configurations or any(c != expected[name]["default_config"] for c in configurations):
            raise RuntimeError(f"An FLA kernel selected unexpected settings: {name}.")
