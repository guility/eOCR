#!/usr/bin/env python3
"""Run MonkeyOCRv2's upstream Transformers parsing path on CUDA for diagnostics.

The upstream command-line Transformers backend is CPU-only. This runner reuses
its parsing/model implementation but directs the model and preprocessor to CUDA;
it is a local quality probe, not the officially supported vLLM deployment path.
"""

import argparse
import json
import os
import shutil
import time
from importlib.metadata import version
from pathlib import Path

import torch


MODEL_REVISION = "e8871a0057c98378219b369f924a25ba10f392bf"
SOURCE_REVISION = "6cc0c0bb4864f2541fa6bc3a8f976cffaac8f359"


def install_cache_position_compatibility(model):
    """Supply the cache cursor expected by the pinned model under Transformers 5."""
    original = model.model.prepare_inputs_for_generation

    def prepare(input_ids, **kwargs):
        cache_position = kwargs.get("cache_position")
        if cache_position is None:
            past = kwargs.get("past_key_values")
            start = 0
            if past is not None:
                get_length = getattr(past, "get_seq_length", None)
                if callable(get_length):
                    start = int(get_length())
            kwargs["cache_position"] = torch.arange(
                start, start + input_ids.shape[-1], device=input_ids.device
            )
        return original(input_ids, **kwargs)

    model.model.prepare_inputs_for_generation = prepare


def configure_cuda_backend(core, model_path: str):
    """Install a one-model CUDA backend in the upstream CPU parsing manager."""
    def get_cuda(self, config):
        key = ("transformers-cuda-probe", str(Path(model_path).resolve()))
        with self._lock:
            if key not in self._cache:
                self._close_cached_unlocked()
                model = core.MonkeyOCRv2_TransformersParsing(
                    model_path,
                    device="cuda",
                    dtype="bfloat16",
                    attn_implementation="sdpa",
                )
                install_cache_position_compatibility(model)
                preprocessor = None
                if not config.skip_preprocess:
                    preprocessor = core.Preprocessor(
                        model_path,
                        device="cuda",
                        batch_size=config.preprocess_batch_size,
                    )
                self._cache[key] = (preprocessor, model)
            return self._cache[key]

    core.BackendManager.get = get_cuda


def configure_transformers_5_compatibility(core):
    """Drop a processor key absent from the pinned model's forward signature."""
    def generate_one(self, image, question, min_pixels=None, max_tokens=None,
                     temperature=None, top_p=None):
        prepared = core.load_image(
            image,
            max_pixels=int(os.getenv("MOCR2_MAX_PIXELS"))
            if os.getenv("MOCR2_MAX_PIXELS") else None,
            min_pixels=min_pixels,
        )
        messages = [{"role": "user", "content": [
            {"type": "image", "image": prepared},
            {"type": "text", "text": question},
        ]}]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text], images=[prepared], padding=True, return_tensors="pt"
        )
        # Transformers 5.19 adds this field; the pinned MonkeyOCRv2 forward
        # signature has no corresponding argument and does not consume it.
        inputs.pop("mm_token_type_ids", None)
        inputs = {
            key: (
                value.to(device=self.model.device, dtype=torch.float32)
                if torch.is_tensor(value) and value.is_floating_point()
                else value.to(self.model.device)
                if torch.is_tensor(value)
                else value
            )
            for key, value in inputs.items()
        }
        generation_kwargs = {
            "max_new_tokens": int(max_tokens or 10000),
            "do_sample": bool(temperature and temperature > 0),
        }
        if generation_kwargs["do_sample"]:
            generation_kwargs["temperature"] = temperature
            if top_p is not None:
                generation_kwargs["top_p"] = top_p
        with torch.inference_mode():
            outputs = self.model.generate(**inputs, **generation_kwargs)
        generated = outputs[:, inputs["input_ids"].shape[1]:]
        return self.processor.batch_decode(generated, skip_special_tokens=True)[0]

    core.MonkeyOCRv2_TransformersParsing._generate_one = generate_one


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--upstream-parsing-root", type=Path, required=True)
    parser.add_argument("--diagnose-prompts", action="store_true")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this diagnostic run")
    import sys
    if os.getenv("EOC_DISABLE_HF_KERNELS") == "1":
        # The SGLang image's optional `kernels` package requires newer Hub
        # dataclasses than the model-declared Transformers 4.57.1 supports.
        sys.modules["kernels"] = None
    sys.path.insert(0, str(args.upstream_parsing_root))
    from cpu import core_runner as core

    manifest = json.loads((args.dataset_root / "manifest.json").read_text(encoding="utf-8"))
    pages = manifest["synthetic_pages"]
    args.output.mkdir(parents=True, exist_ok=True)
    input_dir = args.output / "inputs"
    input_dir.mkdir(exist_ok=True)
    for page in pages:
        source = args.dataset_root / page["page_image"]
        shutil.copyfile(source, input_dir / f"{page['id']}.png")

    if int(version("transformers").split(".", 1)[0]) >= 5:
        configure_transformers_5_compatibility(core)
    configure_cuda_backend(core, str(args.model_path))
    manager = core.BackendManager()
    backend = core.BackendConfig(
        model_path=str(args.model_path),
        backend="transformers",
        device="cuda",
        dtype="bfloat16",
        attn_implementation="sdpa",
        max_pixels=1003520,
        preprocess_batch_size=1,
        skip_preprocess=False,
    )
    try:
        # Load weights before timing; use one page as an unmeasured warmup.
        preprocessor, model = manager.get(backend)
        if args.diagnose_prompts:
            from PIL import Image
            page_image = core.load_image(
                args.dataset_root / pages[0]["page_image"],
                max_pixels=backend.max_pixels,
            )
            prompts = ["LAYOUT", "END2END"]
            for prompt_name in prompts:
                output = model.batch_inference(
                    [page_image], [core.ALL_PROMPT[prompt_name]],
                    min_pixels=backend.max_pixels, max_tokens=4096, temperature=0,
                )[0]
                print(json.dumps({"prompt": prompt_name, "output": output}, ensure_ascii=False))
            return
        warm_dir = args.output / "warmup-input"
        warm_dir.mkdir(exist_ok=True)
        warm_page = pages[0]
        shutil.copyfile(
            args.dataset_root / warm_page["page_image"],
            warm_dir / f"{warm_page['id']}.png",
        )
        core.run_pipeline(core.PipelineConfig(
            input_path=str(warm_dir),
            output_path=str(args.output / "warmup-output"),
            backend=backend,
            page_max_inflight=1,
            draw_layout=False,
            keep_header_footer=True,
            show_progress_bar=False,
            verbose=False,
        ), backend_manager=manager)

        rows = []
        for page in pages:
            page_id = page["id"]
            page_input = input_dir / f"{page_id}.png"
            page_output = args.output / "pages" / page_id
            started = time.perf_counter()
            core.run_pipeline(core.PipelineConfig(
                input_path=str(page_input),
                output_path=str(page_output),
                backend=backend,
                page_max_inflight=1,
                draw_layout=False,
                keep_header_footer=True,
                show_progress_bar=False,
                verbose=False,
            ), backend_manager=manager)
            elapsed = time.perf_counter() - started
            raw_result = page_output / "jsons" / f"{page_id}.json"
            if not raw_result.is_file():
                raise RuntimeError(f"Expected parser result at {raw_result}")
            result_path = args.output / "results" / f"{page_id}.json"
            result_path.parent.mkdir(exist_ok=True)
            shutil.copyfile(raw_result, result_path)
            rows.append({
                "page_id": page_id,
                "seconds": elapsed,
                "result": str(result_path.relative_to(args.output)),
            })

        run = {
            "model": "MonkeyOCRv2-B-Parsing",
            "model_revision": MODEL_REVISION,
            "revision": MODEL_REVISION,
            "upstream_source_revision": SOURCE_REVISION,
            "runtime": (
                "upstream Transformers parser forced to CUDA; diagnostic, not supported vLLM server"
                + (" with Transformers 5 compatibility shims"
                   if int(version("transformers").split(".", 1)[0]) >= 5 else "")
            ),
            "torch_version": torch.__version__,
            "transformers_version": version("transformers"),
            "device": torch.cuda.get_device_name(0),
            "dtype": "bfloat16",
            "attention": "sdpa",
            "max_pixels": backend.max_pixels,
            "preprocess_batch_size": backend.preprocess_batch_size,
            "warmup_pages": 1,
            "mean_seconds": sum(row["seconds"] for row in rows) / len(rows),
            "pages": rows,
        }
        (args.output / "run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({
            "pages": len(rows),
            "mean_seconds": run["mean_seconds"],
            "output": str(args.output),
        }, ensure_ascii=False))
    finally:
        manager.close()


if __name__ == "__main__":
    main()
