package config.structs

import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class Resolution(
    val width: Int,
    val height: Int
)

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
sealed class InputConfig