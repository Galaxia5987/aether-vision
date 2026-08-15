package com.galaxia5987.app.pipeline

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.app.publish.PublishBroker
import com.galaxia5987.app.publish.Publishable
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow

abstract class PipelineBase(protected val camera: CameraBase<*>, val neededStreams: List<StreamType>) {

    abstract fun init()
    abstract fun periodic(frameset: Map<StreamType, ByteArray>)
    abstract fun publish(toPublish: Publishable)
    abstract fun end()
    protected val publishable: Publishable = object : Publishable {
        override fun copy(): Publishable = this
    }

    private var job: Job? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val publishFlow = MutableSharedFlow<Publishable>(extraBufferCapacity = 2)


    fun start() {
        if(job?.isActive == true) return

        require(
            neededStreams.all { camera.streamTypes.contains(it) }
        ) { "Camera of type ${camera::class.simpleName} cannot comply with this pipeline's stream requirements" }

        PublishBroker.addPublisher {
            publishFlow.collect {
                publish(it)
            }
        }

        job = scope.launch {
            init()
            while(isActive){
                camera.collectFrames {
                    periodic(it)
                }
                publishFlow.emit(publishable.copy())
            }
            end()
        }
    }

    fun stop() {
        job?.cancel()
    }

}