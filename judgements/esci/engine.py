"""Load the unmerged v3 adapter once, with an explicitly pinned CUDA runtime."""

from importlib.metadata import version
from pathlib import Path

from .contract import OPTIONS, probabilities


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
        from decider.infer import Decider
        from peft import LoraConfig, inject_adapter_in_model, set_peft_model_state_dict
        from safetensors.torch import load_file

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

    def predict(self, states: list[str]) -> list[list[float]]:
        question = {"question": self.settings["question"], "options": list(OPTIONS)}
        output = []
        size = self.settings["microbatch_size"]
        for start in range(0, len(states), size):
            answers = self.decider.decide_batch(
                [(s, [question]) for s in states[start : start + size]]
            )
            if len(answers) != len(states[start : start + size]):
                raise RuntimeError("Decider returned an unexpected result count.")
            for answer in answers:
                if len(answer) != 1:
                    raise RuntimeError("Expected exactly one ESCI answer.")
                output.append(
                    probabilities([float(answer[0]["probs"][name]) for name in OPTIONS])
                )
        return output
