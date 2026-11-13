package com.kobser.app.offline

/** Copies of the Media3 Download.STATE_* values we use, kept here so the maths can be tested on the JVM. */
object DownloadStates {
    const val QUEUED = 0
    const val STOPPED = 1
    const val DOWNLOADING = 2
    const val COMPLETED = 3
    const val FAILED = 4
    const val REMOVING = 5
    const val RESTARTING = 7
}

/**
 * Progress of one collection. It is computed from the download index states of
 * its songs (by cache key) and the set of keys already complete in the cache.
 * Those keys were cached before the download framework existed, or downloaded
 * for another collection.
 */
fun collectionProgress(keys: List<String>, states: Map<String, Int>, cachedKeys: Set<String>): OfflineProgress {
    var done = 0
    var failed = 0
    var running = false
    for (key in keys) {
        when (states[key]) {
            DownloadStates.COMPLETED -> done++
            DownloadStates.FAILED -> failed++
            DownloadStates.QUEUED, DownloadStates.DOWNLOADING, DownloadStates.RESTARTING, DownloadStates.STOPPED -> running = true
            else -> if (key in cachedKeys) done++ else running = true
        }
    }
    return OfflineProgress(done = done, total = keys.size, failed = failed, running = running)
}
