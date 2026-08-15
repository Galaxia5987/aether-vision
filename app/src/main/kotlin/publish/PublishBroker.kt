package com.galaxia5987.app.publish

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.CopyOnWriteArrayList

interface Publishable {
    fun copy(): Publishable
}

fun interface PublishEventListener {
    suspend fun publish()
}

object PublishBroker {

    private val publishers = CopyOnWriteArrayList<PublishEventListener>()

    private var job: Job? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun startPublishing() {
        if(job?.isActive == true) return

        job = scope.launch {
            while(isActive){
                publishers.forEach {
                    it.publish()
                }
            }
        }
    }

    fun stop(){
        job?.cancel()
    }

    fun addPublisher(publisher: PublishEventListener) {
        publishers += publisher
    }

    fun removePublisher(publisher: PublishEventListener) {
        publishers -= publisher
    }
}