package logging

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

object LogBroker {
    private const val MAX_BUFFER = 50

    private val _logFlow = MutableStateFlow<List<String>>(emptyList())
    val logFlow: StateFlow<List<String>> = _logFlow

    fun emitLog(message: String) {
        _logFlow.update { currentLogs ->
            val newLogs = currentLogs + message.trim()
            if (newLogs.size > MAX_BUFFER) {
                newLogs.drop(newLogs.size - MAX_BUFFER)
            } else {
                newLogs
            }
        }
    }
}
