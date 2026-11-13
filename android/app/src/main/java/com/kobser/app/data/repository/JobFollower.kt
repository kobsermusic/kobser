package com.kobser.app.data.repository

/** Server-side states of a download job that mean it has finished, whether it succeeded or not. */
val FINISHED_JOB_STATUSES = setOf("done", "error", "cancelled")

/** How a followed job ended. `status` is the last server status seen. */
data class JobOutcome(val status: String, val error: String?) {
    val succeeded: Boolean get() = status == "done"
}

/**
 * Polls a download job until it finishes, reporting every status change.
 *
 * It uses no Android or Retrofit types, so it can be unit-tested. [fetch]
 * returns the job's (status, error), or null after a transient failure such as a
 * brief network error or a server restart, in which case the call is repeated.
 * Following stops after [timeoutMs] with the status "timeout".
 */
suspend fun followJob(
    fetch: suspend () -> Pair<String, String?>?,
    onStatus: (String) -> Unit,
    pollMs: Long = 1_200,
    timeoutMs: Long = 15 * 60_000,
    sleep: suspend (Long) -> Unit,
): JobOutcome {
    var waited = 0L
    var last: String? = null
    while (waited < timeoutMs) {
        val result = runCatching { fetch() }.getOrNull()
        if (result != null) {
            val (status, error) = result
            if (status != last) {
                last = status
                onStatus(status)
            }
            if (status in FINISHED_JOB_STATUSES) return JobOutcome(status, error)
        }
        sleep(pollMs)
        waited += pollMs
    }
    return JobOutcome("timeout", "Timed out waiting for the server")
}
