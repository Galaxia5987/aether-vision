plugins {
    kotlin("multiplatform")
    kotlin("plugin.serialization") version "1.9.22"
}

repositories {
    mavenCentral()
}

val ktorVersion = "2.3.11"

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
                implementation("io.ktor:ktor-client-core:${ktorVersion}")
                implementation("io.ktor:ktor-client-content-negotiation:${ktorVersion}")
                implementation("io.ktor:ktor-serialization-kotlinx-json:${ktorVersion}")
            }
        }

        val jvmMain by getting {
            dependencies {
                api("ch.qos.logback:logback-classic:1.5.38")
            }
        }
        val jsMain by getting {
            dependencies {
                implementation("io.ktor:ktor-client-js:${ktorVersion}")
            }
        }
    }
}