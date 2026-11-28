"""Inference backend configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from aether_vision.config.base import ConfigModel


class OnnxRuntimeConfig(ConfigModel):
    """ONNX Runtime. ``CPUExecutionProvider`` works everywhere.

    For QCS6490 with an ONNX Runtime build that includes the QNN execution
    provider, use ``providers=["QNNExecutionProvider", "CPUExecutionProvider"]``.
    """

    kind: Literal["onnxruntime"] = "onnxruntime"
    providers: tuple[str, ...] = ("CPUExecutionProvider",)
    intra_op_threads: int = Field(0, ge=0, le=64, description="0 lets ONNX Runtime decide")
    qnn_backend_path: str = Field("libQnnHtp.so", description="Used with QNNExecutionProvider")


class LiteRtConfig(ConfigModel):
    """LiteRT (TFLite). On QCS6490 the Qualcomm QNN delegate runs the model on the Hexagon NPU.

    The delegate library (``libQnnTFLiteDelegate.so``) ships with Qualcomm's AI
    packages (``scripts/install.sh`` installs them on a QCS6490). The NPU only runs
    uint8/int8 quantized models; unsupported layers run on the CPU. Use a fully
    integer-quantized TFLite model (e.g. Ultralytics ``format=tflite, int8=True``
    or a pre-quantized ``w8a8`` model from Qualcomm AI Hub).
    """

    kind: Literal["litert"] = "litert"
    delegate: Literal["none", "qnn"] = "qnn"
    delegate_path: str = "libQnnTFLiteDelegate.so"
    cpu_fallback: bool = Field(
        True, description="Run on the CPU if the QNN delegate cannot be loaded"
    )
    qnn_backend: Literal["htp", "gpu", "dsp"] = "htp"
    htp_performance_mode: Literal[
        "default", "sustained_high_performance", "burst", "high_performance", "power_saver"
    ] = "burst"
    num_threads: int = Field(4, ge=1, le=16, description="CPU threads for non-delegated ops")
    extra_delegate_options: dict[str, str] = Field(
        default_factory=dict, description="Passed verbatim to the delegate"
    )


BackendConfig = Annotated[OnnxRuntimeConfig | LiteRtConfig, Field(discriminator="kind")]
