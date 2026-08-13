package config.structs

import kotlinx.serialization.Serializable

@Serializable
data class UsbCamera(
    val resolution: Resolution,
    val colorStream: StreamConfig
) : InputConfig()