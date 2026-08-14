package config.structs

import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class AppConfig(
    var input: InputConfig,
    var networkTable: NetworkTableConfig
)

@OptIn(ExperimentalJsExport::class)
@JsExport
fun defaultInstance(): AppConfig =
    AppConfig(
        UsbCamera(
            Resolution(640, 480),
            StreamConfig(
                enabled = true
            )
        ),
        NetworkTableConfig(
            "10.59.87.2",
            "AetherVision"
        )
    )
