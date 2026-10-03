"""Enforce the declared numerical protocol before loading model weights."""

import inspect

from .kernels import configure_kernels

INFERENCE_PROTOCOL = {
    "name": "singleton-fla-frozen-v1",
    "kernel_profile_sha256": "76f650c990a23ee0eaf62e089ce5010058e2912ed48b2619d8c32881c4e7287b",
    "internal_batch_size": 1,
    "max_context_tokens": 1536,
    "truncation": "decider-1.4.0-context-budget",
    "padding": "right-to-multiple-of-64",
    "dtype": "bfloat16",
    "temperature": 1.0,
    "use_graphs": False,
    "attention": "sdpa",
    "gated_delta": "fla",
    "convolution": "transformers-pytorch-reference",
    "float32_matmul_precision": "highest",
    "tf32_matmul": False,
    "tf32_cudnn": True,
    "cudnn_benchmark": False,
    "cudnn_deterministic": False,
    "bf16_reduced_precision_reduction": True,
}


def configure_runtime(torch, settings, bundle):
    if settings.get("protocol") != INFERENCE_PROTOCOL:
        raise RuntimeError("The model must declare the singleton-fla-frozen-v1 inference protocol.")
    configure_kernels(torch, bundle, INFERENCE_PROTOCOL["kernel_profile_sha256"])
    torch.set_float32_matmul_precision("highest")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = False


def selected_implementation(function):
    """Inspect the pinned Transformers wrapper without replacing its dispatch."""
    seen = set()
    while callable(function) and id(function) not in seen:
        seen.add(id(function))
        if inspect.isfunction(function):
            selected = inspect.getclosurevars(function).nonlocals.get("implementation")
            if selected is not None:
                return selected
        function = getattr(function, "__wrapped__", None)
    raise RuntimeError("Cannot verify the pinned Transformers kernel selection.")


def verify_backend():
    try:
        from fla.ops.gated_delta_rule import (
            chunk_gated_delta_rule,
            fused_recurrent_gated_delta_rule,
        )
    except Exception as error:
        raise RuntimeError(
            "FLA could not initialise; check the CUDA driver, C compiler and headers. "
            "A PyTorch gated-delta fallback is not permitted."
        ) from error
    from transformers.models.qwen3_next import modeling_qwen3_next as qwen

    expected = {
        "torch_chunk_gated_delta_rule": chunk_gated_delta_rule,
        "torch_recurrent_gated_delta_rule": fused_recurrent_gated_delta_rule,
    }
    selected = {}
    for name, implementation in expected.items():
        actual = selected_implementation(getattr(qwen, name))
        if actual is not implementation:
            raise RuntimeError(f"{name} selected an undeclared implementation.")
        selected[name] = f"{actual.__module__}.{actual.__name__}"
    for name in ("causal_conv1d_fn", "causal_conv1d_update"):
        actual = selected_implementation(getattr(qwen, name))
        if actual.__module__ != qwen.__name__ or actual.__name__ != name:
            raise RuntimeError(f"{name} must use the declared PyTorch convolution.")
        selected[name] = f"{actual.__module__}.{actual.__name__}"
    return selected
