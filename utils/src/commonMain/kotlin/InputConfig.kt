package config.structs

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.InternalSerializationApi
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.descriptors.elementNames
import kotlinx.serialization.serializerOrNull
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
data class Resolution(
    val width: Int,
    val height: Int
)

val options = mapOf<String, InputConfig>(
    Pair("RealsenseCamera", RealsenseCamera.defaultInstance()),
    Pair("UsbCamera", UsbCamera.defaultInstance())
)

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
sealed class InputConfig {
    companion object {
        @OptIn(ExperimentalSerializationApi::class, InternalSerializationApi::class)
        fun getOptions(): Map<String, InputConfig> = options
    }
}