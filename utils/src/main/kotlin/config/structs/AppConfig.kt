package config.structs

import kotlinx.serialization.Serializable

@Serializable
data class AppConfig(
    val input: InputConfig,
    val networkTable: NetworkTableConfig
)
