package com.galaxia5987.server

import io.ktor.server.application.Application
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty

object Server {

    fun start() {
        embeddedServer(
            factory = Netty,
            port = EnvironmentConfig.HTTP_PORT,
            host = EnvironmentConfig.HTTP_BIND_ADDRESS,
            module = Application::rootModule
        ).start(wait = true) // blocks the current thread
    }
}