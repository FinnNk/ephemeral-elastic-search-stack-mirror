"""Load the unmerged v3 adapter once, with an explicitly pinned CUDA runtime."""

from importlib.metadata import version
from pathlib import Path

from .contract import OPTIONS, probabilities
from .runtime import configure_runtime, verify_backend
from .kernels import read_profile, verify_selections


class Engine:
    def __init__(self, bundle: Path, settings: dict):
        for package, expected in settings["runtime"].items():
            actual = version(package).split("+")[0]
            if actual != expected:
                raise RuntimeError(f"{package}: expected {expected}, found {actual}.")
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "The v3 serving image requires an available NVIDIA CUDA GPU."
            )
        configure_runtime(torch, settings, bundle)
        self.backend = verify_backend()
        verify_selections(bundle, settings["protocol"]["kernel_profile_sha256"])
        from decider.infer import Decider
        from peft import LoraConfig, inject_adapter_in_model, set_peft_model_state_dict
        from safetensors.torch import load_file

        self.bundle = bundle
        self.settings = settings
        self.decider = Decider(
            str(bundle / "base"),
            device="cuda",
            dtype=torch.bfloat16,
            use_graphs=False,
            temperature=1.0,
        )
        backbone = self.decider.m.lm.model
        inject_adapter_in_model(
            LoraConfig.from_pretrained(str(bundle / "adapter")), backbone
        )
        state = load_file(str(bundle / "adapter/adapter.safetensors"), device="cpu")
        loaded = set_peft_model_state_dict(backbone, state)
        if loaded.unexpected_keys or any("lora_" in k for k in loaded.missing_keys):
            raise RuntimeError(
                "Adapter weights did not load completely into the backbone."
            )
        self.decider.m.eval()
        if self.decider.m.lm.config._attn_implementation != "sdpa":
            raise RuntimeError("The frozen inference protocol requires SDPA attention.")

    def predict(self, states: list[str]) -> list[list[float]]:
        if states:
            read_profile(self.bundle, self.settings["protocol"]["kernel_profile_sha256"])
        question = {"question": self.settings["question"], "options": list(OPTIONS)}
        output = []
        # Each pair keeps the same tensor shape regardless of HTTP companions.
        for state in states:
            answers = self.decider.decide_batch(
                [(state, [question])],
                max_ctx_tokens=self.settings["protocol"]["max_context_tokens"],
            )
            if len(answers) != 1:
                raise RuntimeError("Decider returned an unexpected result count.")
            for answer in answers:
                if len(answer) != 1:
                    raise RuntimeError("Expected exactly one ESCI answer.")
                output.append(
                    probabilities([float(answer[0]["probs"][name]) for name in OPTIONS])
                )
        if states:
            self.kernel_selections = verify_selections(
                self.bundle, self.settings["protocol"]["kernel_profile_sha256"], require_all=True)
        return output
