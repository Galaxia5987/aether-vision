package config.structs

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
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
        Pair("RealsenseCamera", RealsenseCameraConfig.defaultInstance()),
        Pair("UsbCamera", UsbCameraConfig.defaultInstance()),
    )

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
sealed class InputConfig {
    companion object {
        fun getOptions(): Map<String, InputConfig> = options
    }
}
