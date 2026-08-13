enum class Environment {
    DEV,
    PROD,
}

object EnvironmentConfig {
    val CURRENT_ENVIRONMENT: Environment =
        when (System.getenv("DEV")) {
            null -> Environment.PROD
            else -> Environment.DEV
        }

    val HTTP_PORT: Int = (System.getenv("HTTP_PORT") ?: "5803").toInt()
    val HTTP_BIND_ADDRESS: String =
        when (CURRENT_ENVIRONMENT) {
            Environment.DEV -> "127.0.0.1"
            Environment.PROD -> "0.0.0.0"
        }
}
