package com.storyapp.dialogue

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Stores each user's own free Groq / Hugging Face API keys locally on-device,
 * encrypted at rest. The backend has no keys of its own — every request
 * carries the caller's key, so each install can be tied to its own free-tier
 * account.
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

    var huggingFaceApiToken: String
        get() = prefs.getString(KEY_HUGGINGFACE, "") ?: ""
        set(value) = prefs.edit().putString(KEY_HUGGINGFACE, value).apply()

    val hasRequiredKeys: Boolean
        get() = groqApiKey.isNotBlank()

    companion object {
        private const val KEY_GROQ = "groq_api_key"
        private const val KEY_HUGGINGFACE = "huggingface_api_token"
    }
}
