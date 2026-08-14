package com.galaxia5987.server.streaming.broker

object StreamingBrokers {
    private val brokers = hashMapOf<String, StreamBroker>()

    val brokerNames: List<String>
        get() = brokers.keys.toList()

    fun addBroker(streamType: String, streamPusher: StreamPusher) {
        require(!hasBroker(streamType))
        brokers[streamType] = StreamBroker(
            16L, streamPusher
        ).also {
            it.startStream()
        }
    }

    fun getBroker(streamType: String): StreamBroker = brokers.getOrElse(streamType) { error("Broker named $streamType is not registered!") }

    fun hasBroker(streamType: String): Boolean = brokers.containsKey(streamType)
}