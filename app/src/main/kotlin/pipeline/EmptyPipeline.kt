package com.galaxia5987.app.pipeline

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.app.publish.Publishable

class EmptyPipeline(camera: CameraBase) :
    PipelineBase(camera, listOf(StreamType.COLOR)) {
    override fun init() {}

    override fun periodic(frameset: Map<StreamType, ByteArray>) {}

    override fun publish(toPublish: Publishable) {}

    override fun end() {}
}
