package com.galaxia5987.server.routing

import com.galaxia5987.server.streaming.broker.StreamingBrokers
import com.galaxia5987.server.streaming.handleMjpegStream
import io.ktor.http.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import io.ktor.server.util.*

fun Route.streamRouting() {
    get("/api/stream/{brokerName}") {
        val brokerName = call.parameters.getOrFail("brokerName")
        if (StreamingBrokers.hasBroker(brokerName)) {
            handleMjpegStream(StreamingBrokers.getBroker(brokerName), call)
        } else {
            call.respondText(
                status = HttpStatusCode.NotFound,
                text = "Broker not found",
            )
        }
    }

    get("/api/stream") {
        call.respond(StreamingBrokers.brokerNames)
    }
}
