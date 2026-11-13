package com.kobser.app.playback

import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import com.kobser.app.data.repository.LibraryRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Reports plays to Navidrome. It sends "now playing" when a track starts and a
 * scrobble once [ScrobbleTracker] says the track counts. Navidrome needs these for
 * play counts, recently played, and any Last.fm / ListenBrainz forwarding set up there.
 * It runs in the playback service so Android Auto plays count too.
 */
class Scrobbler(
    private val player: Player,
    private val repository: LibraryRepository,
    private val scope: CoroutineScope,
) : Player.Listener {
    private val tracker = ScrobbleTracker()
    private var ticker: Job? = null

    fun attach() {
        player.addListener(this)
        onMediaItemTransition(player.currentMediaItem, Player.MEDIA_ITEM_TRANSITION_REASON_PLAYLIST_CHANGED)
    }

    override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
        val id = mediaItem?.mediaId?.takeUnless { isPreviewMediaId(it) }?.let { realTrackId(it) }
        tracker.onTrackStarted(id)?.let { report(it, submission = false) }
    }

    override fun onIsPlayingChanged(isPlaying: Boolean) {
        ticker?.cancel()
        ticker = if (isPlaying) scope.launch { tick() } else null
    }

    private suspend fun tick() {
        while (currentCoroutineContext().isActive) {
            tracker.onProgress(player.currentPosition, player.duration.coerceAtLeast(0L))
                ?.let { report(it, submission = true) }
            delay(5_000)
        }
    }

    private fun report(id: String, submission: Boolean) {
        scope.launch {
            // A failed scrobble must never affect playback, so errors are ignored.
            runCatching { repository.scrobble(id, submission) }
        }
    }
}
