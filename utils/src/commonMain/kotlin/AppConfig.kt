package config.structs

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class AppConfig(
    var input: InputConfig,
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
        NetworkTableConfig(
            "10.59.87.2",
            "AetherVision",
        ),
    )
