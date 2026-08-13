import org.slf4j.LoggerFactory

enum class Environment {
    DEV,
    PROD,
}

object EnvironmentConfig {
    private val logger = LoggerFactory.getLogger(this::class.simpleName)

    val CURRENT_ENVIRONMENT: Environment =
        when (System.getenv("DEV")) {
            null -> Environment.PROD
            else -> Environment.DEV
        }.also {
            if(it == Environment.DEV){
                logger.info("Development mode enabled!")
            }
        }

    val HTTP_PORT: Int = (System.getenv("HTTP_PORT") ?: "5803").toInt()
    val HTTP_BIND_ADDRESS: String =
        when (CURRENT_ENVIRONMENT) {
            Environment.DEV -> "127.0.0.1"
            Environment.PROD -> "0.0.0.0"
        }
}
