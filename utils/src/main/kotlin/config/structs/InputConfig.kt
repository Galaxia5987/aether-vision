package config.structs

import kotlinx.serialization.Serializable

@Serializable
data class Resolution(
    val width: Int,
    val height: Int
)

@Serializable
sealed class InputConfig