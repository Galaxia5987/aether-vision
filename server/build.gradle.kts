plugins {
    kotlin("jvm")
    alias(ktorLibs.plugins.ktor)
}

repositories {
    mavenCentral()
}

dependencies {
    implementation(project(":utils"))
    implementation(ktorLibs.server.core)
    implementation(ktorLibs.server.netty)
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}