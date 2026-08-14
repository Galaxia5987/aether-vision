package com.galaxia5987.server.routing

import io.ktor.server.routing.Route
import io.ktor.server.sse.sse
import io.ktor.sse.ServerSentEvent
import kotlinx.serialization.json.Json
import logging.LogBroker

fun Route.loggingRoute(){
    sse("/logs") {
        LogBroker.logFlow.collect { logList ->
            val payload = Json.encodeToString(logList)
            send(ServerSentEvent(data = payload))
        }
    }
}