package com.galaxia5987.server.routing

import config.Config
import io.ktor.http.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.configRouting() {
    put("/api/config") {
        Config.save(call.receive())
        call.respondText(status = HttpStatusCode.Accepted, text = "OK")
    }

    get("/api/config") {
        call.respond(HttpStatusCode.OK, Config.load())
    }
}
