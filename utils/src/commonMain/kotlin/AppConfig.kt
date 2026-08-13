package config.structs

import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class AppConfig(
    val input: InputConfig,
    val networkTable: NetworkTableConfig
)
