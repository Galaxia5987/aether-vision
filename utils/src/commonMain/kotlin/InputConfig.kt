package config.structs

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.InternalSerializationApi
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class Resolution(
    var width: Int,
    var height: Int,
)

val options =
    mapOf<String, InputConfig>(
        Pair("RealsenseCamera", RealsenseCamera.defaultInstance()),
        Pair("UsbCamera", UsbCamera.defaultInstance()),
    )

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
sealed class InputConfig {
    companion object {
        @OptIn(
            ExperimentalSerializationApi::class,
            InternalSerializationApi::class,
        )
        fun getOptions(): Map<String, InputConfig> = options
    }
}
