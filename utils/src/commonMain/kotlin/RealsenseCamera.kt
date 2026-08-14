package config.structs

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@SerialName("RealsenseCamera")
@Serializable
data class RealsenseCamera(
    val resolution: Resolution,
    val fps: Int,
    val colorStream: StreamConfig,
    val depthStream: StreamConfig,
) : InputConfig(), DefaultValue<RealsenseCamera> {
    override fun defaultInstance(): RealsenseCamera =
        RealsenseCamera(
            Resolution(
                640,
                480
            ),
            30,
            colorStream = StreamConfig(enabled = true),
            depthStream = StreamConfig(enabled = true)
        )
}