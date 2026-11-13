package com.kobser.app.ui.main

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kobser.app.data.api.KobserApi
import com.kobser.app.data.repository.PreferencesRepository
import com.kobser.app.playback.MusicPlayer
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    val musicPlayer: MusicPlayer,
    private val prefs: PreferencesRepository,
    private val api: KobserApi,
    val downloadTracker: com.kobser.app.data.repository.DownloadTracker,
    val libraryRepository: com.kobser.app.data.repository.LibraryRepository,
) : ViewModel() {

    init {
        // Check the stored session once on launch. If the server answers 401, the auth
        // interceptor clears the session and MainActivity switches to the login screen,
        // so the tabs don't stay empty with an expired session.
        viewModelScope.launch {
            try { api.me() } catch (_: Exception) { /* offline, so keep the session */ }
        }
    }

    fun logout(onSuccess: () -> Unit) {
        viewModelScope.launch {
            prefs.clearSession()
            onSuccess()
        }
    }
}
