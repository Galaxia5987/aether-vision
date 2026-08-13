package config.structs

import kotlinx.serialization.Serializable

@Serializable
data class NetworkTableConfig(
    val server: String,
    val table: String
)
