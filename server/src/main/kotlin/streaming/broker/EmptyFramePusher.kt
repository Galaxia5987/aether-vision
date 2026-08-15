@file:Suppress("SameParameterValue")

package com.galaxia5987.server.streaming.broker

private object ResourceHelper {
    private fun loadJpegFromResources(fileName: String): ByteArray {
        val inputStream =
            javaClass.getResourceAsStream("/$fileName")
                ?: error("Resource file not found: $fileName")

        return inputStream.use { it.readBytes() }
    }

    val emptyFrameImage = loadJpegFromResources("emptyFrame.jpeg")
}

class EmptyFramePusher : StreamPusher {
    override fun acceptFrame(): ByteArray = ResourceHelper.emptyFrameImage
}
