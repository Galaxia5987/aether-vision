plugins {
    kotlin("jvm")
    application
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.bytedeco:javacpp:1.5.10")
    testImplementation(kotlin("test"))
}

val cmakeConfigure = tasks.register<Exec>("cmakeConfigure") {
    description = "Configure native cmake project"
    workingDir = file("../native")
    commandLine = listOf("cmake", "-S", ".", "-B", "build")
}

val cmakeBuild  = tasks.register<Exec>("cmakeBuild") {
    description = "Build native cmake project"
    dependsOn(cmakeConfigure)
    workingDir = file("../native/build")
    commandLine = listOf("cmake", "--build", ".")
}

val javacppBuild = tasks.register<JavaExec>("javacppBuild") {
    description = "Generate and build JavaCPP JNI bindings"
    dependsOn(cmakeBuild, tasks.named("classes"))

    mainClass.set("org.bytedeco.javacpp.tools.Builder")
    classpath = sourceSets["main"].runtimeClasspath

    systemProperty("org.bytedeco.javacpp.platform.includepath", file("../native").absolutePath)
    systemProperty("org.bytedeco.javacpp.platform.linkpath", file("../native/build").absolutePath)

    args(
        "-d", file("build/classes/kotlin/main").absolutePath,
        "com.galaxia5987.NativeLibrary"
    )
}

application {
    mainClass = "com.galaxia5987.NativeLibraryKt"
}

tasks.named<JavaExec>("run") {
    val nativeLibPath = file("build/classes/kotlin/main").absolutePath

    jvmArgs("--enable-native-access=ALL-UNNAMED")
    systemProperty("java.library.path", nativeLibPath)
}

tasks.test {
    useJUnitPlatform()
}