package com.kobser.app.data.api

/**
 * True when an HTTP response means the session we hold is no longer valid. It may have
 * expired or been dropped server-side (e.g. the v1.1.0 backend migration re-created the
 * sessions table). A 401 from the login endpoint means a wrong password, so it doesn't count.
 */
fun isSessionInvalidResponse(path: String, code: Int): Boolean =
    code == 401 && path.trimEnd('/') != "/api/login"
