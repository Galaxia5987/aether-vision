package config.structs

import kotlinx.serialization.Serializable

@Serializable
data class StreamConfig(
    val enabled: Boolean
)