package com.galaxia5987.app.pipeline

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.app.publish.Publishable
import com.galaxia5987.lib.Detection
import com.galaxia5987.lib.YoloDetector
import org.bytedeco.opencv.opencv_core.Mat

data class SamplePublishable(val detection: Detection) : Publishable {
    override fun copy(): Publishable = this.copy(detection = detection)
}

class EmptyPipeline(camera: CameraBase) :
    PipelineBase(camera, listOf(StreamType.COLOR)) {

    private var model: YoloDetector? = null

    override fun init() {
        logger.info("Init")

        model = YoloDetector("model.onnx", false)
    }

    override fun periodic(frameset: Map<StreamType, Mat>) {
        logger.info("Periodic")
        val image: Mat = frameset[StreamType.COLOR]!!
        val detections = model!!.detect(image, 0.25F, 0.45F).toList()

        publishable = SamplePublishable(detection = detections.maxBy { it.confidence })
    }

    override fun publish(toPublish: Publishable) {
        if(toPublish !is SamplePublishable) {
            require(false)
            return
        }
        logger.info("${toPublish.detection}")
        logger.info("Publish")
    }

    override fun end() {
        logger.info("End")
    }
}
