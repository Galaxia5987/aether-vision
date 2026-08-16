package com.galaxia5987.app

fun main() {
    Runtime.getRuntime().addShutdownHook(Thread {
        Initializer.teardown()
    })
    Initializer.init()
}
