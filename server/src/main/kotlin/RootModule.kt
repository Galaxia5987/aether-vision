package com.galaxia5987.server

import com.galaxia5987.server.routing.configureRouting
import io.ktor.server.application.Application

fun Application.rootModule() {
    configureRouting()
}