package com.galaxia5987.server

import io.ktor.server.application.Application
import io.ktor.server.engine.EmbeddedServer
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty

object Server {

    private val server = embeddedServer(
        factory = Netty,
        port = EnvironmentConfig.HTTP_PORT,
        host = EnvironmentConfig.HTTP_BIND_ADDRESS,
        module = Application::rootModule,
    )

    fun start() {
        server.start(wait = true) // blocks the current thread
    }

    fun stop() {
        server.stop()
    }
}
