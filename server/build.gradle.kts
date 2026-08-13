import org.gradle.internal.os.OperatingSystem

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

val frontendDir = file("$rootDir/frontend")

val npmCommand = if (OperatingSystem.current().isWindows) "npm.cmd" else "npm"

val installFrontend = tasks.register<Exec>("installFrontend") {
    description = "Install frontend npm dependencies"
    workingDir = frontendDir
    commandLine(npmCommand, "install")
}

val buildFrontend = tasks.register<Exec>("buildFrontend") {
    description = "Build frontend using npm"
    dependsOn(installFrontend)
    workingDir = frontendDir
    commandLine(npmCommand, "run", "build")
}

tasks.named<ProcessResources>("processResources") {
    dependsOn(buildFrontend)

    from("$frontendDir/dist") {
        into("dashboard")
    }
}