package com.galaxia5987.server.routing

import io.ktor.server.application.Application
import io.ktor.server.http.content.staticResources
import io.ktor.server.routing.routing

fun Application.configureRouting() {
    routing {
        staticResources("/", "dashboard")
    }
}