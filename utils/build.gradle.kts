plugins {
    kotlin("jvm")
}

repositories {
    mavenCentral()
}

dependencies {
    api("ch.qos.logback:logback-classic:1.5.38")
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}