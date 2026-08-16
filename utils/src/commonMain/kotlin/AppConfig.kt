package config.structs

import config.structs.pipeline.EmptyPipelineConfig
import config.structs.pipeline.PipelineConfig
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class AppConfig(
    var input: InputConfig,
    var pipeline: PipelineConfig,
    var networkTable: NetworkTableConfig,
)

@OptIn(ExperimentalJsExport::class)
@JsExport
fun defaultInstance(): AppConfig =
    AppConfig(
        UsbCameraConfig(
            Resolution(640, 480),
            StreamConfig(enabled = true),
        ),
        EmptyPipelineConfig(),
        NetworkTableConfig(
            "10.59.87.2",
            "AetherVision",
        ),
    )
