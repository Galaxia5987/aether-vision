package com.galaxia5987.app.camera

import com.galaxia5987.server.streaming.broker.StreamPusher
import com.galaxia5987.server.streaming.broker.StreamingBrokers
import config.structs.InputConfig
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.slf4j.Logger
import org.slf4j.LoggerFactory

private val ENUMERATION_DELAY: Duration = 100.milliseconds

abstract class CameraBase(val streamTypes: List<StreamType>) {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var job: Job? = null

    private val framesetFlow = MutableSharedFlow<Map<StreamType, ByteArray>>()

    protected val logger: Logger = LoggerFactory.getLogger(this::class.java)

    private var config: InputConfig? = null

    protected abstract fun startCamera(config: InputConfig)

    protected abstract fun stopCamera()

    protected abstract fun pollFrame(streamType: StreamType): ByteArray?

    protected abstract fun pollJpegFrame(streamType: StreamType): ByteArray?

    protected abstract fun enumerateDevice(): Boolean

    private suspend fun startEnumeration() {
        while (!enumerateDevice()) {
            delay(ENUMERATION_DELAY)
        }

        try {
            startCamera(config!!)
        } catch (e: Exception) {
            logger.error("Exception thrown while starting camera!", e)
        }
    }

    fun start(config: InputConfig) {
        if (job?.isActive == true) return
        this.config = config

        streamTypes.forEach {
            StreamingBrokers.addBroker(it.displayName, makeStreamPusher(it))
        }

        job = scope.launch {
            val frameset =
                LinkedHashMap<StreamType, ByteArray>(streamTypes.size)

            streamTypes.forEach { // populate the map first
                frameset[it] = ByteArray(0)
            }

            startEnumeration()

            loop@ while (isActive) {
                streamTypes.forEach {
                    pollFrame(it).run {
                        if (this == null) {
                            startEnumeration()
                            continue@loop
                        }

                        frameset[it] = this
                    }
                }

                framesetFlow.emit(frameset)
            }
            stopCamera()
        }
    }

    fun stop() {
        job?.cancel()
    }

    suspend fun collectFrames(
        collector: suspend (Map<StreamType, ByteArray>) -> Unit
    ) {
        framesetFlow.collectLatest(collector)
    }

    fun makeStreamPusher(streamType: StreamType): StreamPusher = StreamPusher {
        pollJpegFrame(streamType)
    }
}
