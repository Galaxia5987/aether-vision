dependencyResolutionManagement {
    @Suppress("UnstableApiUsage")
    repositories {
        mavenCentral()
    }
}

rootProject.name = "aether-vision"

include(":app")
include(":utils")
include(":lib")
include(":server")