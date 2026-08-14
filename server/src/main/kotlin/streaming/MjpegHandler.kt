package com.galaxia5987.server.streaming

import com.galaxia5987.server.streaming.broker.StreamBroker
import io.ktor.http.ContentType
import io.ktor.server.application.ApplicationCall
import io.ktor.server.response.respondBytesWriter
import io.ktor.utils.io.writeFully
import io.ktor.utils.io.writeStringUtf8
import org.slf4j.LoggerFactory

private val logger = LoggerFactory.getLogger("MjpegHandler")

suspend fun handleMjpegStream(broker: StreamBroker, call: ApplicationCall) {
    logger.info("Client connected to mjpeg stream")
    val boundary = "mjpeg_frame_boundary"
    val contentType = ContentType("multipart", "x-mixed-replace")
        .withParameter("boundary", boundary)

    call.respondBytesWriter(contentType = contentType) {
        try {
            broker.frames.collect { jpegBytes ->
                val header = buildString {
                    append("--$boundary\r\n")
                    append("Content-Type: image/jpeg\r\n")
                    append("Content-Length: ${jpegBytes.size}\r\n\r\n")
                }.toByteArray(Charsets.UTF_8)

                writeFully(header)
                writeFully(jpegBytes)
                writeStringUtf8("\r\n")
                flush()
            }
        } catch (e: Exception) {
            logger.info("Client disconnected from mjpeg stream")
        }
    }
}