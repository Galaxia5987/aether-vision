package com.galaxia5987.server.streaming.broker

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.*
import kotlin.time.Duration.Companion.milliseconds

private val emptyFramePusher = EmptyFramePusher()

class StreamBroker(
    private val loopTime: Long,
    private val streamPusher: StreamPusher
) {
    private val mutFrames = MutableSharedFlow<ByteArray>(replay = 1) // cache one frame for new subscribers. might reduce if it creates notable overhead.
    val frames: SharedFlow<ByteArray> = mutFrames

    private val brokerScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var pollingJob: Job? = null

    fun startStream() {
        if (pollingJob?.isActive == true) return

        pollingJob = brokerScope.launch {
            while (isActive) {
                pushFrame(streamPusher.acceptFrame() ?: emptyFramePusher.acceptFrame())
                delay(loopTime.milliseconds)
            }
        }
    }

    fun stopStream() {
        pollingJob?.cancel()
    }

    fun destroy() {
        stopStream()
        brokerScope.cancel()
    }

    suspend fun pushFrame(data: ByteArray) {
        mutFrames.emit(data)
    }
}