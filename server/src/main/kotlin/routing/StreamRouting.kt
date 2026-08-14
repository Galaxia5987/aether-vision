package com.galaxia5987.server.routing

import com.galaxia5987.server.streaming.broker.StreamingBrokers
import com.galaxia5987.server.streaming.handleMjpegStream
import io.ktor.http.HttpStatusCode
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import io.ktor.server.util.getOrFail
import kotlinx.serialization.json.Json

private val jsonSerializer = Json.Default

fun Route.streamRouting() {
    get("/api/stream/{brokerName}") {
        val brokerName = call.parameters.getOrFail("brokerName")
        if(StreamingBrokers.hasBroker(brokerName)){
            handleMjpegStream(StreamingBrokers.getBroker(brokerName), call)
        }else {
            call.respondText(status = HttpStatusCode.NotFound, text = "Broker not found")
        }
    }

    get("/api/stream") {
        call.respondText(status = HttpStatusCode.OK, text = jsonSerializer.encodeToString(StreamingBrokers.brokerNames))
    }
}