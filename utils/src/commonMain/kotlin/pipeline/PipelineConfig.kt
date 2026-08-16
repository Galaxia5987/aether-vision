package config.structs.pipeline

import kotlinx.serialization.Serializable
import kotlin.js.ExperimentalJsExport
import kotlin.js.JsExport

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