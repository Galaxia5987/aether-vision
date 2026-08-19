package com.galaxia5987.lib

import kotlin.collections.get
import kotlin.text.toInt
import org.bytedeco.javacpp.BytePointer
import org.bytedeco.javacpp.Loader
import org.bytedeco.javacpp.Pointer
import org.bytedeco.javacpp.annotation.ByRef
import org.bytedeco.javacpp.annotation.ByVal
import org.bytedeco.javacpp.annotation.Cast
import org.bytedeco.javacpp.annotation.Index
import org.bytedeco.javacpp.annotation.Name
import org.bytedeco.javacpp.annotation.Namespace
import org.bytedeco.javacpp.annotation.Platform
import org.bytedeco.opencv.opencv_core.Mat

@Platform(include = ["usb/UsbCamera.hpp"], link = ["aether-vision-lib", "opencv_core"])
@Name("UsbCamera")
@Namespace("aethervision")
class UsbCameraWrapper : Pointer {

    constructor(p: Pointer) : super(p)

    constructor(deviceId: Int = 0) {
        allocate(deviceId)
    }

    private external fun allocate(deviceId: Int)

    @Cast("bool") external fun open(deviceId: Int): Boolean

    @Name("close") external fun closeCamera()

    @Cast("bool") external fun isOpened(): Boolean

    @ByVal external fun readFrame(): Mat

    external fun getWidth(): Int

    external fun getHeight(): Int

    external fun getChannels(): Int

    companion object {
        init {
            // Loads the JNI library built by JavaCPP
            Loader.load()
        }

        @JvmStatic
        @ByVal
        external fun encodeToJpeg(
            @ByRef rawData: Mat,
            quality: Int = 95,
        ): ByteVector
    }
}

@Platform(include = ["usb/UsbCamera.hpp"], link = ["aether-vision-lib"])
@Name("std::vector<uint8_t>")
class ByteVector : Pointer {

    companion object {
        init {
            Loader.load(ByteVector::class.java)
        }
    }

    constructor() {
        allocate()
    }

    constructor(size: Long) {
        allocate(size)
    }

    constructor(p: Pointer) : super(p)

    private external fun allocate()

    private external fun allocate(n: Long)

    external fun size(): Long

    external fun resize(n: Long)

    @Index external fun get(i: Long): Byte

    @Index external fun put(i: Long, value: Byte): ByteVector

    @Cast("signed char*") external fun data(): BytePointer

    fun toByteArray(): ByteArray {
        val size = this.size().toInt()
        if (size == 0) return ByteArray(0)

        val byteArray = ByteArray(size)

        val pointer = this.data()

        pointer.capacity(this.size())

        pointer.get(byteArray)

        return byteArray
    }
}
