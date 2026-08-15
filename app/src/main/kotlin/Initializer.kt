package com.galaxia5987.app

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.usb_camera.UsbCamera
import com.galaxia5987.app.publish.PublishBroker
import com.galaxia5987.server.Server
import config.Config
import config.structs.RealsenseCameraConfig
import config.structs.UsbCameraConfig
import logging.configureLogger

object Initializer {

    val camera: CameraBase = when(Config.load().input) {
        is UsbCameraConfig -> UsbCamera()
        is RealsenseCameraConfig -> TODO("Not yet implemented")
    }

    fun init() {
        configureLogger()

        camera.start(Config.load().input)

        PublishBroker.startPublishing()
        Server.start()
    }
}