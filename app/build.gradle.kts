plugins {
    kotlin("jvm")
    application
}

dependencies {
    implementation(project(":utils"))
}

application {
    mainClass = "com.galaxia5987.app.AppKt"
}