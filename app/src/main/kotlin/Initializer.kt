package com.galaxia5987.app

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.usb_camera.UsbCamera
import com.galaxia5987.app.pipeline.EmptyPipeline
import com.galaxia5987.app.pipeline.PipelineBase
import com.galaxia5987.app.publish.PublishBroker
import com.galaxia5987.server.Server
import config.Config
import config.structs.RealsenseCameraConfig
import config.structs.UsbCameraConfig
import config.structs.pipeline.EmptyPipelineConfig
import logging.configureLogger

object Initializer {

    val camera: CameraBase =
        when (Config.load().input) {
            is UsbCameraConfig -> UsbCamera()
            is RealsenseCameraConfig -> TODO("Not yet implemented")
        }

    val pipeline: PipelineBase = when(Config.load().pipeline) {
        is EmptyPipelineConfig -> EmptyPipeline(camera)
    }

    fun init() {
        configureLogger()

        camera.start(Config.load().input)
        pipeline.start()

        PublishBroker.startPublishing()
        Server.start()
    }
}
