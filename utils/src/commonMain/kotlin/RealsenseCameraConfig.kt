package config.structs

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@SerialName("RealsenseCamera")
@Serializable
data class RealsenseCameraConfig(
    var resolution: Resolution,
    var fps: Int,
    var colorStream: StreamConfig,
    var depthStream: StreamConfig,
) : InputConfig() {
    companion object : DefaultValue<RealsenseCameraConfig> {
        override fun defaultInstance(): RealsenseCameraConfig =
            RealsenseCameraConfig(
                Resolution(
                    640,
                    480,
                ),
                30,
                colorStream = StreamConfig(enabled = true),
                depthStream = StreamConfig(enabled = true),
            )
    }
}
