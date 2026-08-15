package com.galaxia5987.app

import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.app.camera.usb_camera.UsbCamera
import com.galaxia5987.server.Server
import com.galaxia5987.server.streaming.broker.StreamingBrokers
import config.Config
import config.structs.UsbCameraConfig
import logging.configureLogger

fun main() {
    configureLogger()
    val cam = UsbCamera()
    cam.start(Config.load().input as UsbCameraConfig)
    StreamingBrokers.addBroker("color", cam.makeStreamPusher(StreamType.COLOR))
    Server.start()
}
