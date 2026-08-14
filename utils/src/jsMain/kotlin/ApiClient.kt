package config

import config.structs.AppConfig
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.plugins.sse.*
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import kotlin.js.JsExport
import kotlinx.serialization.json.Json

@OptIn(ExperimentalJsExport::class)
@JsExport
class ConfigClient(private val baseUrl: String) {
    private val configEndpoint: String = "/api/config"
    private val logsEndpoint: String = "/logs"

    private val jsonSerializer = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    private val client = HttpClient {
        install(ContentNegotiation) {
            json(jsonSerializer)
        }
        install(SSE)
    }

    suspend fun fetchConfig(): AppConfig =
        client.get("$baseUrl$configEndpoint").body()

    suspend fun updateConfig(config: AppConfig) {
        client.put("$baseUrl$configEndpoint") {
            contentType(ContentType.Application.Json)
            setBody(config)
        }
    }

    suspend fun subscribeToLogs(onLogsReceived: (Array<String>) -> Unit) {
        client.sse("$baseUrl$logsEndpoint") {
            incoming.collect { event ->
                event.data?.let { dataString ->
                    val logsList = jsonSerializer.decodeFromString<List<String>>(dataString)
                    onLogsReceived(logsList.toTypedArray())
                }
            }
        }
    }

    fun close() = client.close()
}