plugins {
    kotlin("multiplatform")
    kotlin("plugin.serialization") version "1.9.22"
}

repositories {
    mavenCentral()
}

kotlin {
    jvm()

    js {
        browser()
        binaries.library()
        generateTypeScriptDefinitions()
    }

    sourceSets {
        val commonMain by getting {
            dependencies {
                implementation("org.jetbrains.kotlinx:kotlinx-serialization-core:1.6.3")
                implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
            }
        }

        val jvmMain by getting {
            dependencies {
                api("ch.qos.logback:logback-classic:1.5.38")
            }
        }
    }
}