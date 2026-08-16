package config.structs.pipeline

import config.structs.DefaultValue
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@OptIn(ExperimentalJsExport::class)
@JsExport
@SerialName("EmptyPipeline")
@Serializable
class EmptyPipelineConfig : PipelineConfig() {
    companion object : DefaultValue<EmptyPipelineConfig> {
        override fun defaultInstance(): EmptyPipelineConfig =
            EmptyPipelineConfig()
    }
}
