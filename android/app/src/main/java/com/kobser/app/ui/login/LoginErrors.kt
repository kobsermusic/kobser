package com.kobser.app.ui.login

/** Maps a login HTTP status to a message the user can act on. */
fun loginErrorMessage(code: Int): String = when (code) {
    401 -> "Wrong username or password"
    429 -> "Too many failed attempts. Try again in a few minutes."
    502, 503, 504 -> "Kobser can't reach the music server. Check that Navidrome is running."
    404 -> "That URL isn't a Kobser server"
    else -> "Login failed (HTTP $code)"
}
