package com.kobser.app.auto

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Records which apps connected to Kobser's media service, and when. It helps diagnose
 * "Android Auto sometimes doesn't show Kobser". If a car session left no entry here,
 * Android Auto never asked to connect, and it makes that choice before Kobser runs.
 * If the session did connect, the problem is on Kobser's side. The log is kept in a
 * small file because the car usually starts the process fresh and it may be killed
 * afterwards.
 */
@Singleton
class AutoConnectionLog @Inject constructor(
    @ApplicationContext context: Context,
    private val gson: Gson,
) {
    private val file = File(context.filesDir, "media_connections.json")
    // Only one writer runs at a time. A connection records two events back to back,
    // and concurrent read-modify-write cycles would lose one of them.
    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO.limitedParallelism(1))
    private val type = object : TypeToken<List<ConnectionEntry>>() {}.type

    private val _entries = MutableStateFlow<List<ConnectionEntry>>(emptyList())
    val entries: StateFlow<List<ConnectionEntry>> = _entries.asStateFlow()

    init {
        scope.launch {
            _entries.value = runCatching { gson.fromJson<List<ConnectionEntry>>(file.readText(), type) }.getOrNull() ?: emptyList()
        }
    }

    fun record(packageName: String, event: String) {
        scope.launch {
            val updated = appendCapped(_entries.value, ConnectionEntry(System.currentTimeMillis(), packageName, event))
            _entries.value = updated
            runCatching { file.writeText(gson.toJson(updated)) }
        }
    }
}
