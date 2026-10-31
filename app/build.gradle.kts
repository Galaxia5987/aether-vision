plugins {
    kotlin("jvm")
    application
}

val generateProto = tasks.register<Exec>("generateProto") {
    val protoDir = file("$rootDir/pipeline/proto")
    val outDir = layout.buildDirectory.dir("generated/source/proto/main/java").get().asFile
    inputs.dir(protoDir)
    outputs.dir(outDir)
    doFirst {
        outDir.mkdirs()
    }
    commandLine("protoc", "--proto_path=$protoDir", "--java_out=${outDir.absolutePath}", "$protoDir/vision_pipeline.proto")
}

sourceSets {
    main {
        java {
            srcDir(generateProto)
        }
    }
}

tasks.named("compileKotlin") {
    dependsOn(generateProto)
}

dependencies {
    implementation(project(":server"))
    implementation(project(":utils"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    implementation("com.google.protobuf:protobuf-java:3.25.5")
    testImplementation(kotlin("test"))
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
}

tasks.test {
    useJUnitPlatform()
}

application {
    mainClass = "com.galaxia5987.app.AppKt"
}
