package logging

import ch.qos.logback.classic.Level
import ch.qos.logback.classic.LoggerContext
import ch.qos.logback.classic.encoder.PatternLayoutEncoder
import ch.qos.logback.classic.spi.ILoggingEvent
import ch.qos.logback.core.ConsoleAppender
import ch.qos.logback.core.rolling.RollingFileAppender
import ch.qos.logback.core.rolling.TimeBasedRollingPolicy
import org.slf4j.Logger
import org.slf4j.LoggerFactory

fun configureLogger() {
    val context =
        (LoggerFactory.getILoggerFactory() as LoggerContext).apply {
            reset()
        }

    val encoder =
        PatternLayoutEncoder().apply {
            setContext(context)
            pattern =
                "%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n"
            start()
        }

    val consoleAppender =
        ConsoleAppender<ILoggingEvent>().apply {
            setContext(context)
            name = "CONSOLE"
            setEncoder(encoder)
            start()
        }

    val fileAppender =
        RollingFileAppender<ILoggingEvent>().apply {
            setContext(context)
            name = "FILE"
            file = "logs/app.log"
            setEncoder(encoder)
        }

    fileAppender.rollingPolicy =
        TimeBasedRollingPolicy<ILoggingEvent>().apply {
            setContext(context)
            setParent(fileAppender)
            fileNamePattern = "logs/app-%d{yyyy-MM-dd}.log"
            maxHistory = 30
            start()
        }

    fileAppender.start()

    // Configure Root Logger
    context.getLogger(Logger.ROOT_LOGGER_NAME).apply {
        level = Level.INFO
        addAppender(consoleAppender)
        addAppender(fileAppender)
    }
}
