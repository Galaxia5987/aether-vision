import com.diffplug.gradle.spotless.SpotlessExtension
import org.jetbrains.kotlin.gradle.dsl.KotlinJvmExtension

plugins {
    kotlin("jvm") version "2.4.10" apply false
    id("com.diffplug.spotless") version "8.9.0" apply false
    id("java")
    id("idea")
}

subprojects {
    apply(plugin = "com.diffplug.spotless")

    configure<SpotlessExtension> {
        java {
            target("**/*.java")
            googleJavaFormat()
            trimTrailingWhitespace()
            endWithNewline()
        }

        kotlin {
            target("**/*.kt")
            ktlint()
            trimTrailingWhitespace()
            endWithNewline()
        }
    }

    plugins.withId("org.jetbrains.kotlin.jvm") {
        configure<KotlinJvmExtension> {
            jvmToolchain(25)
        }
    }
}