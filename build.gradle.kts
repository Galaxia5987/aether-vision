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
        format("misc"){
            target("*gradle*", ".gitattributes", ".gitignore")
            trimTrailingWhitespace()
            leadingTabsToSpaces(4)
            endWithNewline()
        }
        java {
            target("**/*.java")
            googleJavaFormat().aosp()
            trimTrailingWhitespace()
            endWithNewline()
        }
        kotlin {
            target("**/*.kt")
            ktfmt().googleStyle().configure {
                it.setBlockIndent(4)
                it.setContinuationIndent(4)
                it.setMaxWidth(80)
                it.setRemoveUnusedImports(true)
            }
        }
    }

    plugins.withId("org.jetbrains.kotlin.jvm") {
        configure<KotlinJvmExtension> {
            jvmToolchain(25)
        }
    }
}