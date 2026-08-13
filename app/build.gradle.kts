plugins {
    kotlin("jvm")
    application
}

dependencies {
    implementation(project(":lib"))
    implementation(project(":utils"))
}

application {
    mainClass = "com.galaxia5987.app.AppKt"
}

tasks.named<JavaExec>("run") {
    systemProperty("java.library.path", systemProperties.getOrElse("java.library.path", {":"}) as String +project(":lib").buildDir.absolutePath + "/classes/kotlin/main/")
    jvmArgs("--enable-native-access=ALL-UNNAMED")
}