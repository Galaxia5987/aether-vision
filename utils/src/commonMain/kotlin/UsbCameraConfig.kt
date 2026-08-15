package config.structs

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@SerialName("UsbCamera")
@Serializable
data class UsbCameraConfig(
    var resolution: Resolution,
    var colorStream: StreamConfig,
) : InputConfig() {
    companion object : DefaultValue<UsbCameraConfig> {
        override fun defaultInstance(): UsbCameraConfig =
            UsbCameraConfig(
                Resolution(
                    640,
                    480,
                ),
                colorStream = StreamConfig(enabled = true),
            )
    }
}
