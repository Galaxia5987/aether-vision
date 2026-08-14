package config.structs

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.descriptors.elementNames
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
sealed class InputConfig {
    companion object {
        @OptIn(ExperimentalSerializationApi::class)
        fun getOptions(): List<String> {
            val descriptor = serializer().descriptor

            val valueDescriptor: SerialDescriptor = descriptor.getElementDescriptor(1)

            return valueDescriptor.elementNames.toList()
        }
    }
}