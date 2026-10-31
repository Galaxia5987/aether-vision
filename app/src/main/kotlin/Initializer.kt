package com.galaxia5987.app

import com.galaxia5987.app.pipeline.PipelineManager
import com.galaxia5987.server.Server
import logging.configureLogger

object Initializer {

    fun init() {
        configureLogger()

        PipelineManager.start()
        Server.start()
    }

    fun teardown() {
        PipelineManager.stop()
        Server.stop()
    }
}
