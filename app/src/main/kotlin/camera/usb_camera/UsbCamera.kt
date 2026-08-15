package com.galaxia5987.app.camera.usb_camera

import com.galaxia5987.lib.ByteVector
import com.galaxia5987.lib.UsbCameraWrapper
import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import config.structs.InputConfig
import config.structs.UsbCameraConfig

class UsbCamera : CameraBase(listOf(StreamType.COLOR)) {

    private var camera: UsbCameraWrapper? = null
    var width: Int = 0
        private set
    var height: Int = 0
        private set
    var channels: Int = 0
        private set

    private var latestByteVector: ByteVector? = null

    override fun startCamera(config: InputConfig) {
        camera = UsbCameraWrapper(0)
    }

    override fun stopCamera() {
        camera?.close()
    }

    private fun pollLatestFrame(): ByteVector {
        if(camera == null){
            throw IllegalStateException("UsbCamera native object cannot be null!")
        }
        require(camera!!.isOpened())

        height = camera!!.getHeight()
        width = camera!!.getWidth()
        channels = camera!!.getChannels()

        return camera!!.readFrame()
    }

    override fun pollFrame(streamType: StreamType): ByteArray {
        require(streamType == StreamType.COLOR)
        latestByteVector = pollLatestFrame()
        return latestByteVector!!.toByteArray()
    }

    override fun pollJpegFrame(streamType: StreamType): ByteArray? {
        require(streamType == StreamType.COLOR)
        if(latestByteVector == null) return null
        return UsbCameraWrapper.encodeToJpeg(latestByteVector!!, width, height, channels).toByteArray()
    }
}