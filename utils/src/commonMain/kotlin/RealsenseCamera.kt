package config.structs

import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class RealsenseCamera(
    val resolution: Resolution,
    val fps: Int,
    val colorStream: StreamConfig,
    val depthStream: StreamConfig,
) : InputConfig()