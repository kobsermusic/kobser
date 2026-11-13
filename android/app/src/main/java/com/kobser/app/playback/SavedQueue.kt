package com.kobser.app.playback

import com.google.gson.Gson
import com.kobser.app.data.api.Song

/**
 * The play queue saved across app runs. [MusicPlayer] writes it whenever the current
 * track changes and reads it back on the next launch.
 * [LibrarySessionCallback.onPlaybackResumption] also reads it when Android Auto,
 * Bluetooth or the system media-resumption UI asks to resume while the phone UI isn't open.
 */
data class SavedQueue(
    val songs: List<Song>,
    val currentIndex: Int,
    val positionMs: Long,
) {
    fun toJson(gson: Gson): String =
        gson.toJson(Payload(songs = songs, currentIndex = currentIndex, positionMs = positionMs))

    // Format of the stored JSON. Older builds saved a single `song`, and parse() still reads it.
    private data class Payload(
        val song: Song? = null,
        val songs: List<Song>? = null,
        val currentIndex: Int = 0,
        val positionMs: Long = 0,
    )

    companion object {
        /** Returns null when there's nothing usable to restore. */
        fun parse(json: String?, gson: Gson): SavedQueue? {
            if (json.isNullOrBlank()) return null
            val payload = try {
                gson.fromJson(json, Payload::class.java)
            } catch (_: Exception) {
                null
            } ?: return null
            val songs = payload.songs?.takeIf { it.isNotEmpty() }
                ?: payload.song?.let { listOf(it) }
                ?: return null
            return SavedQueue(
                songs = songs,
                currentIndex = payload.currentIndex.coerceIn(0, songs.size - 1),
                positionMs = payload.positionMs.coerceAtLeast(0L),
            )
        }
    }
}
