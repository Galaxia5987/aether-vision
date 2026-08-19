package com.galaxia5987.app.camera.usb_camera

import com.galaxia5987.app.camera.CameraBase
import com.galaxia5987.app.camera.StreamType
import com.galaxia5987.lib.ByteVector
import com.galaxia5987.lib.UsbCameraWrapper
import config.structs.InputConfig
import org.bytedeco.opencv.opencv_core.Mat

private const val DEVICE_ID = 0

class UsbCamera : CameraBase(listOf(StreamType.COLOR)) {

    private var camera: UsbCameraWrapper? = null
    var width: Int = 0
        private set

    var height: Int = 0
        private set

    var channels: Int = 0
        private set

    private var latestByteVector: Mat? = null

    override fun startCamera(config: InputConfig) {
        camera = UsbCameraWrapper(DEVICE_ID)
    }

    override fun stopCamera() {
        camera?.close()
    }

    private fun pollLatestFrame(): Mat? {
        if (camera == null) {
            throw IllegalStateException(
                "UsbCamera native object cannot be null!"
            )
        }
        if (!camera!!.isOpened()) {
            return null
        }

        height = camera!!.getHeight()
        width = camera!!.getWidth()
        channels = camera!!.getChannels()

        return camera!!.readFrame()
    }

    override fun pollFrame(streamType: StreamType): Mat? {
        require(streamType == StreamType.COLOR)
        latestByteVector = pollLatestFrame()
        return latestByteVector
    }

    override fun pollJpegFrame(streamType: StreamType): ByteArray? {
        require(streamType == StreamType.COLOR)
        if (latestByteVector == null) return null
        return UsbCameraWrapper.encodeToJpeg(
                latestByteVector!!,
            )
            .toByteArray()
    }

    override fun enumerateDevice(): Boolean {
        var cam: UsbCameraWrapper? = null
        try {
            cam = UsbCameraWrapper(DEVICE_ID)
            return true
        } catch (e: Exception) {
            return false
        } finally {
            cam?.close()
        }
    }
}
