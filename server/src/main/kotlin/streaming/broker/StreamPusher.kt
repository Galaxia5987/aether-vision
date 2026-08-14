package com.galaxia5987.server.streaming.broker

fun interface StreamPusher {
    fun acceptFrame(): ByteArray?
}