package config

import config.structs.AppConfig
import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.client.request.*
import io.ktor.http.*
import io.ktor.serialization.kotlinx.json.*
import kotlinx.serialization.json.Json
import kotlin.js.JsExport

@OptIn(ExperimentalJsExport::class)
@JsExport
class ConfigClient(
    private val baseUrl: String
) {
    private val endpoint: String = "/api/config"
    private val client = HttpClient {
        install(ContentNegotiation) {
            json(Json {
                prettyPrint = true
                ignoreUnknownKeys = true
                encodeDefaults = true
            })
        }
    }

    suspend fun fetchConfig(): AppConfig =
        client.get("$baseUrl$endpoint").body()


    suspend fun updateConfig(config: AppConfig) {
        client.put("$baseUrl$endpoint") {
            contentType(ContentType.Application.Json)
            setBody(config)
        }
    }


    fun close() =
        client.close()

}