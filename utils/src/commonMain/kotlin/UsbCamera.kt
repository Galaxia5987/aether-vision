package config.structs

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@SerialName("UsbCamera")
@Serializable
data class UsbCamera(
    var resolution: Resolution,
    var colorStream: StreamConfig,
) : InputConfig() {
    companion object : DefaultValue<UsbCamera> {
        override fun defaultInstance(): UsbCamera =
            UsbCamera(
                Resolution(
                    640,
                    480,
                ),
                colorStream = StreamConfig(enabled = true),
            )
    }
}
