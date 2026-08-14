package logging

import ch.qos.logback.classic.encoder.PatternLayoutEncoder
import ch.qos.logback.classic.spi.ILoggingEvent
import ch.qos.logback.core.AppenderBase

class StreamingAppender : AppenderBase<ILoggingEvent>() {
    var encoder: PatternLayoutEncoder? = null

    override fun append(eventObject: ILoggingEvent) {
        val logMessage = encoder?.layout?.doLayout(eventObject) ?: eventObject.formattedMessage
        LogBroker.emitLog(logMessage)
    }
}