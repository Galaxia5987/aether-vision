package config

import config.structs.AppConfig
import config.structs.NetworkTableConfig
import config.structs.Resolution
import config.structs.StreamConfig
import config.structs.UsbCamera
import config.structs.defaultInstance
import kotlinx.serialization.json.Json
import org.slf4j.LoggerFactory
import java.io.File

private val configFile = File("config/config.json")
private val serializer = AppConfig.serializer()

object Config {

    private val logger = LoggerFactory.getLogger(this::class.simpleName)
    private var cachedConfig: AppConfig? = null

    private val jsonFormat = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun load(forceReload: Boolean = false): AppConfig {
        if (!forceReload && cachedConfig != null) {
            return cachedConfig!!
        }

        val config = if (configFile.exists()) {
            val fileContent = configFile.readText()
            try {
                jsonFormat.decodeFromString(serializer, fileContent)
            } catch (e: Exception) {
                logger.error("Failed to parse configuration. Falling back to defaults. Error: ${e.message}")
                defaultInstance()
            }
        } else {
            val defaultConfig = defaultInstance()
            save(defaultConfig)
            return defaultConfig
        }

        cachedConfig = config
        return config
    }

    fun save(config: AppConfig) {
        val jsonContent = jsonFormat.encodeToString(serializer, config)

        configFile.parentFile?.mkdirs()
        configFile.writeText(jsonContent)

        cachedConfig = config
    }
}