package com.galaxia5987.app.pipeline

import aether.vision.proto.VisionPipeline
import config.Config
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull

class PipelineManagerTest {

    @BeforeTest
    fun setUp() {
        PipelineManager.stop()
    }

    @AfterTest
    fun tearDown() {
        PipelineManager.stop()
    }

    @Test
    fun testResolveExecutable() {
        val resolved =
            PipelineManager.resolveExecutableFile("pipeline/build/pipeline")
        assertNotNull(resolved, "Should resolve existing pipeline executable")
        assertTrue(resolved.exists(), "Resolved executable must exist on disk")
    }

    @Test
    fun testInvalidExecutablePath() {
        val started =
            PipelineManager.start("non_existent_path_to_pipeline_binary")
        assertFalse(
            started,
            "Starting with a non-existent binary path should return false",
        )
        assertFalse(
            PipelineManager.isRunning,
            "Pipeline should not be running after failed start",
        )
    }

    @Test
    fun testLifecycleAndProtobufCommunication() = runBlocking {
        val started = PipelineManager.start("pipeline/build/pipeline")
        assertTrue(started, "PipelineManager should start the executable")
        assertTrue(
            PipelineManager.isRunning,
            "PipelineManager.isRunning should be true",
        )
        assertNotNull(
            PipelineManager.pid,
            "PID should be available when running",
        )

        // Send a status request command
        val cmdSent = PipelineManager.requestStatus("test-cmd-status-1")
        assertTrue(cmdSent, "Should successfully write command to STDIN")

        // Wait for a message over STDOUT
        val receivedMessage =
            withTimeoutOrNull(3000) {
                PipelineManager.messages.first()
            }
        assertNotNull(
            receivedMessage,
            "Should receive protobuf message on STDOUT",
        )

        // Send camera configure command
        val camCfg =
            VisionPipeline.CameraConfig.newBuilder()
                .setWidth(640)
                .setHeight(480)
                .setFps(30)
                .build()
        val camSent = PipelineManager.configureCamera(camCfg, "test-cmd-cam-1")
        assertTrue(camSent, "Should successfully send camera config command")

        // Send processing configure command
        val procCfg =
            VisionPipeline.ProcessingConfig.newBuilder()
                .setMinDepthM(0.5f)
                .setMaxDepthM(4.0f)
                .build()
        val procSent =
            PipelineManager.configureProcessing(procCfg, "test-cmd-proc-1")
        assertTrue(
            procSent,
            "Should successfully send processing config command",
        )

        // Stop the pipeline process
        PipelineManager.stop()
        assertFalse(
            PipelineManager.isRunning,
            "PipelineManager.isRunning should be false after stop()",
        )
    }

    @Test
    fun testRestart() {
        val started = PipelineManager.start("pipeline/build/pipeline")
        assertTrue(started)
        assertTrue(PipelineManager.isRunning)

        val restarted = PipelineManager.restart("pipeline/build/pipeline")
        assertTrue(restarted)
        assertTrue(PipelineManager.isRunning)

        PipelineManager.stop()
        assertFalse(PipelineManager.isRunning)
    }

    @Test
    fun testConfigUpdate() {
        val initialConfig = Config.load()
        val originalPath = initialConfig.pipeline.executablePath

        PipelineManager.start(originalPath)
        assertTrue(PipelineManager.isRunning)

        assertEquals(originalPath, PipelineManager.currentExecutablePath)

        // Stopping before finishing test
        PipelineManager.stop()
        assertFalse(PipelineManager.isRunning)
    }
}
