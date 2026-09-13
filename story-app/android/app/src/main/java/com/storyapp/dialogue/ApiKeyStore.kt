package com.storyapp.dialogue

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Stores each user's own free Groq API key locally on-device, encrypted at
 * rest. The backend has no key of its own — every request carries the
 * caller's key, so each install can be tied to its own free-tier account.
 */
class ApiKeyStore(context: Context) {
    private val prefs: SharedPreferences = run {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "api_keys",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var groqApiKey: String
        get() = prefs.getString(KEY_GROQ, "") ?: ""
        set(value) = prefs.edit().putString(KEY_GROQ, value).apply()

    // Defaults to the emulator-only loopback alias. A real device has no
    // "10.0.2.2" — it needs the backend host's actual LAN IP (or a public
    // URL), so this is user-editable instead of a build-time constant.
    var backendUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, DEFAULT_BACKEND_URL) ?: DEFAULT_BACKEND_URL
        set(value) = prefs.edit().putString(KEY_BACKEND_URL, value).apply()

    val hasRequiredKeys: Boolean
        get() = groqApiKey.isNotBlank()

    companion object {
        private const val KEY_GROQ = "groq_api_key"
        private const val KEY_BACKEND_URL = "backend_url"
        const val DEFAULT_BACKEND_URL = "http://10.0.2.2:8000/"
    }
}
