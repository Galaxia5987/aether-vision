dependencyResolutionManagement {
    @Suppress("UnstableApiUsage")
    repositories {
        mavenCentral()
    }
    versionCatalogs {
        create("ktorLibs").from("io.ktor:ktor-version-catalog:3.5.2")
    }
}

rootProject.name = "aether-vision"

include(":app")
include(":utils")
include(":lib")
include(":server")