package config.structs.pipeline

import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport
import kotlinx.serialization.Serializable

val pipelineOptions =
    mutableMapOf<String, PipelineConfig>().apply {
        put("EmptyPipeline", EmptyPipelineConfig.defaultInstance())
    }

@OptIn(ExperimentalJsExport::class)
@JsExport
@Serializable
sealed class PipelineConfig {
    companion object {
        fun getOptions(): Map<String, PipelineConfig> = pipelineOptions
    }
}
