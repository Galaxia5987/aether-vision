package com.galaxia5987.app.camera

import com.galaxia5987.server.streaming.broker.StreamPusher
import com.galaxia5987.server.streaming.broker.StreamingBrokers
import config.structs.InputConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch


abstract class CameraBase(val streamTypes: List<StreamType>) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null

    private val framesetFlow = MutableSharedFlow<Map<StreamType, ByteArray>>()

    protected abstract fun startCamera(config: InputConfig)
    protected abstract fun stopCamera()
    protected abstract fun pollFrame(streamType: StreamType): ByteArray
    protected abstract fun pollJpegFrame(streamType: StreamType): ByteArray?

    fun start(config: InputConfig) {
        if (job?.isActive == true) return
        startCamera(config)

        job = scope.launch {
            val frameset = LinkedHashMap<StreamType, ByteArray>(streamTypes.size)

            streamTypes.forEach { // populate the map first
                frameset[it] = ByteArray(0)
            }

            while (isActive) {
                streamTypes.forEach {
                    frameset[it] = pollFrame(it)
                }

                framesetFlow.emit(frameset)
            }
            stopCamera()
        }
        streamTypes.forEach {
            StreamingBrokers.addBroker(it.displayName, makeStreamPusher(it))
        }
    }

    fun stop() {
        job?.cancel()
    }

    suspend fun collectFrames(collector: FlowCollector<Map<StreamType, ByteArray>>) {
        framesetFlow.collect(collector)
    }

    fun makeStreamPusher(streamType: StreamType): StreamPusher = StreamPusher { pollJpegFrame(streamType) }
}