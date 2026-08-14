package config.structs

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@SerialName("UsbCamera")
@Serializable
data class UsbCamera(
    val resolution: Resolution,
    val colorStream: StreamConfig
) : InputConfig(){
    companion object : DefaultValue<UsbCamera> {
        override fun defaultInstance(): UsbCamera =
            UsbCamera(
                Resolution(
                    640,
                    480
                ),
                colorStream = StreamConfig(enabled = true),
            )
    }
}