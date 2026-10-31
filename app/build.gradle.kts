plugins {
    kotlin("jvm")
    application
}

dependencies {
    implementation(project(":server"))
    implementation(project(":utils"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
}

application {
    mainClass = "com.galaxia5987.app.AppKt"
}