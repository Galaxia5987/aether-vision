package com.galaxia5987.app.pipeline

import aether.vision.proto.VisionPipeline
import config.Config
import config.structs.AppConfig
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.EOFException
import java.io.File
import java.io.InputStream
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import org.slf4j.Logger
import org.slf4j.LoggerFactory

object PipelineManager {

    const val MAX_MESSAGE_SIZE = 64 * 1024 * 1024 // 64 MB protection limit

    private val logger: Logger =
        LoggerFactory.getLogger(PipelineManager::class.java)

    private val isRunningState = AtomicBoolean(false)
    private val stopRequested = AtomicBoolean(false)
    private val writeLock = Any()

    private var process: Process? = null
    private var dataOut: DataOutputStream? = null
    private var scope: CoroutineScope? = null

    var currentExecutablePath: String? = null
        private set

    val isRunning: Boolean
        get() = isRunningState.get() && process?.isAlive == true

    val pid: Long?
        get() = process?.pid()

    private val _messages =
        MutableSharedFlow<VisionPipeline.PipelineMessage>(
            extraBufferCapacity = 64,
            onBufferOverflow = BufferOverflow.DROP_OLDEST,
        )

    val messages: SharedFlow<VisionPipeline.PipelineMessage> =
        _messages.asSharedFlow()

    val results: Flow<VisionPipeline.ProcessingResult> =
        _messages
            .filter {
                it.payloadCase ==
                    VisionPipeline.PipelineMessage.PayloadCase.RESULT
            }
            .map { it.result }

    val telemetry: Flow<VisionPipeline.SystemTelemetry> =
        _messages
            .filter {
                it.payloadCase ==
                    VisionPipeline.PipelineMessage.PayloadCase.TELEMETRY
            }
            .map { it.telemetry }

    val acks: Flow<VisionPipeline.CommandAck> =
        _messages
            .filter {
                it.payloadCase == VisionPipeline.PipelineMessage.PayloadCase.ACK
            }
            .map { it.ack }

    val status: Flow<VisionPipeline.PipelineStatus> =
        _messages
            .filter {
                it.payloadCase ==
                    VisionPipeline.PipelineMessage.PayloadCase.STATUS
            }
            .map { it.status }

    val errors: Flow<VisionPipeline.ErrorMessage> =
        _messages
            .filter {
                it.payloadCase ==
                    VisionPipeline.PipelineMessage.PayloadCase.ERROR
            }
            .map { it.error }

    @Volatile
    var latestStatus: VisionPipeline.PipelineStatus? = null
        private set

    @Volatile
    var latestTelemetry: VisionPipeline.SystemTelemetry? = null
        private set

    init {
        Config.addListener { newConfig -> onConfigUpdated(newConfig) }
    }

    fun resolveExecutableFile(path: String): File? {
        val direct = File(path)
        if (direct.exists() && direct.isFile) {
            return direct.canonicalFile
        }

        val parentRelative = File("..", path)
        if (parentRelative.exists() && parentRelative.isFile) {
            return parentRelative.canonicalFile
        }

        if (path.isBlank()) {
            val defaults =
                listOf(
                    File("pipeline/build/pipeline"),
                    File("../pipeline/build/pipeline"),
                    File("pipeline/cmake-build-debug/pipeline"),
                    File("../pipeline/cmake-build-debug/pipeline"),
                )
            return defaults
                .firstOrNull { it.exists() && it.isFile }
                ?.canonicalFile
        }

        return null
    }

    @Synchronized
    fun start(executablePath: String? = null): Boolean {
        if (isRunning) {
            logger.warn(
                "Pipeline executable is already running (PID: ${process?.pid()})"
            )
            return true
        }

        val configuredPath =
            executablePath ?: Config.load().pipeline.executablePath
        val executableFile = resolveExecutableFile(configuredPath)

        if (executableFile == null || !executableFile.exists()) {
            logger.error(
                "Cannot start pipeline: executable not found at path '$configuredPath'"
            )
            return false
        }

        if (!executableFile.canExecute()) {
            executableFile.setExecutable(true)
        }

        currentExecutablePath = configuredPath
        stopRequested.set(false)

        try {
            val processBuilder = ProcessBuilder(executableFile.absolutePath)
            val workingDir = executableFile.parentFile?.parentFile ?: File(".")
            if (workingDir.exists()) {
                processBuilder.directory(workingDir)
            }

            val proc = processBuilder.start()
            process = proc
            isRunningState.set(true)
            dataOut = DataOutputStream(BufferedOutputStream(proc.outputStream))

            val coroutineScope =
                CoroutineScope(SupervisorJob() + Dispatchers.IO)
            scope = coroutineScope

            // Forward all stderr to the logger
            coroutineScope.launch { readStderrLoop(proc.errorStream) }

            // Read Protobuf messages from stdout
            coroutineScope.launch { readStdoutLoop(proc.inputStream) }

            // Monitor process exit
            proc.onExit().thenAccept { p -> handleProcessExit(p.exitValue()) }

            logger.info(
                "Pipeline executable started successfully: ${executableFile.absolutePath} (PID: ${proc.pid()})"
            )
            return true
        } catch (e: Exception) {
            logger.error("Failed to start pipeline executable: ${e.message}", e)
            cleanUp()
            return false
        }
    }

    @Synchronized
    fun stop() {
        if (!isRunningState.get() && process == null) return

        logger.info("Stopping pipeline process...")
        stopRequested.set(true)
        val proc = process

        if (proc != null && proc.isAlive) {
            try {
                sendCommand(
                    VisionPipeline.PipelineCommand.newBuilder()
                        .setCommandId(UUID.randomUUID().toString())
                        .setType(VisionPipeline.CommandType.CMD_SHUTDOWN)
                        .build()
                )
            } catch (e: Exception) {
                logger.debug("Failed to send CMD_SHUTDOWN: ${e.message}")
            }

            try {
                dataOut?.close()
            } catch (e: Exception) {
                // Ignore stream close exception
            }
            dataOut = null

            try {
                val exited = proc.waitFor(2, TimeUnit.SECONDS)
                if (!exited && proc.isAlive) {
                    logger.warn(
                        "Pipeline process did not terminate within timeout; terminating..."
                    )
                    proc.destroy()
                    if (!proc.waitFor(1, TimeUnit.SECONDS) && proc.isAlive) {
                        logger.warn(
                            "Pipeline process still alive; killing forcibly..."
                        )
                        proc.destroyForcibly()
                    }
                }
            } catch (e: Exception) {
                logger.error("Error waiting for pipeline process to exit", e)
            }
        }

        cleanUp()
        logger.info("Pipeline process stopped.")
    }

    @Synchronized
    fun restart(executablePath: String? = null): Boolean {
        stop()
        return start(executablePath ?: currentExecutablePath)
    }

    fun sendCommand(command: VisionPipeline.PipelineCommand): Boolean {
        val proc = process ?: return false
        if (!proc.isAlive) return false

        val bytes = command.toByteArray()
        synchronized(writeLock) {
            return try {
                val out = dataOut ?: return false
                out.writeInt(bytes.size)
                out.write(bytes)
                out.flush()
                true
            } catch (e: Exception) {
                logger.error(
                    "Failed to write command to pipeline stdin: ${e.message}"
                )
                false
            }
        }
    }

    fun sendCommand(
        type: VisionPipeline.CommandType,
        commandId: String = UUID.randomUUID().toString(),
        cameraConfig: VisionPipeline.CameraConfig? = null,
        processingConfig: VisionPipeline.ProcessingConfig? = null,
    ): Boolean {
        val builder =
            VisionPipeline.PipelineCommand.newBuilder()
                .setCommandId(commandId)
                .setType(type)
        if (cameraConfig != null) builder.setCameraConfig(cameraConfig)
        if (processingConfig != null)
            builder.setProcessingConfig(processingConfig)
        return sendCommand(builder.build())
    }

    fun startPipeline(
        commandId: String = UUID.randomUUID().toString()
    ): Boolean = sendCommand(VisionPipeline.CommandType.CMD_START, commandId)

    fun stopPipeline(
        commandId: String = UUID.randomUUID().toString()
    ): Boolean = sendCommand(VisionPipeline.CommandType.CMD_STOP, commandId)

    fun pausePipeline(
        commandId: String = UUID.randomUUID().toString()
    ): Boolean = sendCommand(VisionPipeline.CommandType.CMD_PAUSE, commandId)

    fun resumePipeline(
        commandId: String = UUID.randomUUID().toString()
    ): Boolean = sendCommand(VisionPipeline.CommandType.CMD_RESUME, commandId)

    fun requestStatus(
        commandId: String = UUID.randomUUID().toString()
    ): Boolean =
        sendCommand(VisionPipeline.CommandType.CMD_GET_STATUS, commandId)

    fun requestConfig(
        commandId: String = UUID.randomUUID().toString()
    ): Boolean =
        sendCommand(VisionPipeline.CommandType.CMD_GET_CONFIG, commandId)

    fun resetCamera(commandId: String = UUID.randomUUID().toString()): Boolean =
        sendCommand(VisionPipeline.CommandType.CMD_RESET_CAMERA, commandId)

    fun configureCamera(
        cameraConfig: VisionPipeline.CameraConfig,
        commandId: String = UUID.randomUUID().toString(),
    ): Boolean =
        sendCommand(
            type = VisionPipeline.CommandType.CMD_CONFIGURE_CAMERA,
            commandId = commandId,
            cameraConfig = cameraConfig,
        )

    fun configureProcessing(
        processingConfig: VisionPipeline.ProcessingConfig,
        commandId: String = UUID.randomUUID().toString(),
    ): Boolean =
        sendCommand(
            type = VisionPipeline.CommandType.CMD_CONFIGURE_PROCESSING,
            commandId = commandId,
            processingConfig = processingConfig,
        )

    fun onConfigUpdated(newConfig: AppConfig) {
        val newPath = newConfig.pipeline.executablePath
        if (newPath != currentExecutablePath && isRunning) {
            logger.info(
                "Pipeline executable path changed from '$currentExecutablePath' to '$newPath'. Restarting..."
            )
            restart(newPath)
        }
    }

    private fun readStderrLoop(errorStream: InputStream) {
        try {
            errorStream.bufferedReader().useLines { lines ->
                for (line in lines) {
                    when {
                        line.contains("[ERROR]") -> logger.error(line)
                        line.contains("[WARN]") -> logger.warn(line)
                        line.contains("[DEBUG]") -> logger.debug(line)
                        else -> logger.info(line)
                    }
                }
            }
        } catch (e: Exception) {
            if (!stopRequested.get() && isRunningState.get()) {
                logger.warn("Pipeline stderr stream closed: ${e.message}")
            }
        }
    }

    private fun readStdoutLoop(inputStream: InputStream) {
        val dataIn = DataInputStream(BufferedInputStream(inputStream))
        try {
            while (isRunningState.get() && !stopRequested.get()) {
                val length =
                    try {
                        dataIn.readInt()
                    } catch (e: EOFException) {
                        logger.info("Pipeline stdout reached EOF")
                        break
                    }

                if (length <= 0 || length > MAX_MESSAGE_SIZE) {
                    logger.error(
                        "Invalid message length received from pipeline: $length"
                    )
                    break
                }

                val buffer = ByteArray(length)
                dataIn.readFully(buffer)
                val message = VisionPipeline.PipelineMessage.parseFrom(buffer)
                handleIncomingMessage(message)
            }
        } catch (e: Exception) {
            if (!stopRequested.get() && isRunningState.get()) {
                logger.error(
                    "Error reading message from pipeline stdout: ${e.message}"
                )
            }
        }
    }

    private fun handleIncomingMessage(message: VisionPipeline.PipelineMessage) {
        when (message.payloadCase) {
            VisionPipeline.PipelineMessage.PayloadCase.STATUS ->
                latestStatus = message.status
            VisionPipeline.PipelineMessage.PayloadCase.TELEMETRY ->
                latestTelemetry = message.telemetry
            VisionPipeline.PipelineMessage.PayloadCase.ERROR ->
                logger.error(
                    "Pipeline error message: ${message.error.errorMessage}"
                )
            VisionPipeline.PipelineMessage.PayloadCase.ACK -> {
                val ack = message.ack
                if (!ack.success) {
                    logger.warn(
                        "Pipeline command ${ack.commandId} rejected: ${ack.message}"
                    )
                } else {
                    logger.debug(
                        "Pipeline command ${ack.commandId} acknowledged: ${ack.message}"
                    )
                }
            }
            else -> {}
        }
        _messages.tryEmit(message)
    }

    private fun handleProcessExit(exitCode: Int) {
        isRunningState.set(false)
        if (stopRequested.get() || exitCode == 0) {
            logger.info("Pipeline process exited with code $exitCode")
        } else {
            logger.error(
                "Pipeline process exited unexpectedly with code $exitCode"
            )
        }
        cleanUp()
    }

    private fun cleanUp() {
        isRunningState.set(false)
        process = null
        synchronized(writeLock) {
            try {
                dataOut?.close()
            } catch (e: Exception) {
                // Ignore
            }
            dataOut = null
        }
        scope?.cancel()
        scope = null
    }
}
