package com.galaxia5987.app

import com.galaxia5987.NativeLibrary
import com.galaxia5987.server.Server
import logging.configureLogger

fun main() {
    NativeLibrary().use {
        println(it.add(200, 2))
    }
    configureLogger()
    Server.start()
}
