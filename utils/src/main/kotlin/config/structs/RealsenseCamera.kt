package config.structs

import kotlinx.serialization.Serializable

@Serializable
data class RealsenseCamera(
    val resolution: Resolution,
    val fps: Int,
    val colorStream: StreamConfig,
    val depthStream: StreamConfig,
) : InputConfig()