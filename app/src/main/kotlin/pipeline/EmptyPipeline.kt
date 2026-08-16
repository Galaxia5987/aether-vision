package com.galaxia5987.app.pipeline

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.app.publish.Publishable

data class SamplePublishable(val someValue: Int) : Publishable {
    override fun copy(): Publishable = this.copy(someValue = someValue)
}

class EmptyPipeline(camera: CameraBase) :
    PipelineBase(camera, listOf(StreamType.COLOR)) {

    override fun init() {
        logger.info("Init")
        publishable = SamplePublishable(2)
    }

    override fun periodic(frameset: Map<StreamType, ByteArray>) {
        logger.info("Periodic")
        publishable = SamplePublishable(1)
    }

    override fun publish(toPublish: Publishable) {
        if(toPublish !is SamplePublishable) {
            require(false)
            return
        }
        logger.info("${toPublish.someValue}")
        logger.info("Publish")
    }

    override fun end() {
        logger.info("End")
    }
}
