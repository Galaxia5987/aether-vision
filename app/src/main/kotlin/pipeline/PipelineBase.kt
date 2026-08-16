package com.galaxia5987.app.pipeline

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.app.publish.PublishBroker
import com.galaxia5987.app.publish.PublishEventListener
import com.galaxia5987.app.publish.Publishable
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.collectLatest
import org.slf4j.Logger
import org.slf4j.LoggerFactory

abstract class PipelineBase(
    protected val camera: CameraBase,
    val neededStreams: List<StreamType>,
) {

    abstract fun init()

    abstract fun periodic(frameset: Map<StreamType, ByteArray>)

    abstract fun publish(toPublish: Publishable)

    abstract fun end()

    protected var publishable: Publishable =
        object : Publishable {
            override fun copy(): Publishable = this
        }

    protected val logger: Logger = LoggerFactory.getLogger(this::class.java)

    private var job: Job? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val publishFlow =
        MutableSharedFlow<Publishable>(extraBufferCapacity = 2)

    private val publishListener = PublishEventListener {
        publishFlow.collectLatest {
            publish(it)
        }
    }

    fun start() {
        if (job?.isActive == true) return

        require(neededStreams.all { camera.streamTypes.contains(it) }) {
            "Camera of type ${camera::class.simpleName} cannot comply with this pipeline's stream requirements"
        }

        PublishBroker.addPublisher(publishListener)

        job = scope.launch {
            try {
                init()
                while (isActive) {
                    camera.collectFrames {
                        periodic(it)
                        publishFlow.emit(publishable.copy())
                    }
                }
            } finally {
                end()
            }
        }
    }

    fun stop() {
        job?.cancel()
        PublishBroker.removePublisher(publishListener)
    }
}
