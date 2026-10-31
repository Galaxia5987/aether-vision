package com.galaxia5987.app

import com.galaxia5987.server.Server
import logging.configureLogger

object Initializer {

    fun init() {
        configureLogger()

        Server.start()
    }

    fun teardown() {
        Server.stop()
    }
}
