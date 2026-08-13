plugins {
    kotlin("jvm")
    kotlin("plugin.serialization") version "1.9.22"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    api("ch.qos.logback:logback-classic:1.5.38")
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}