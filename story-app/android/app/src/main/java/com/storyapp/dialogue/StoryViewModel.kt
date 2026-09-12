package com.storyapp.dialogue

import android.app.Application
import android.media.MediaPlayer
import android.util.Base64
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.storyapp.dialogue.api.AudioClip
import com.storyapp.dialogue.api.AudioRequest
import com.storyapp.dialogue.api.FinalVideoRequest
import com.storyapp.dialogue.api.ParsedStoryWithVoices
import com.storyapp.dialogue.api.StoryApi
import com.storyapp.dialogue.api.StoryRequest
import com.storyapp.dialogue.api.VideoRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream

sealed class UiState {
    data object Idle : UiState()
    data object Parsing : UiState()
    data object GeneratingAudio : UiState()
    data class DialogueReady(
        val parsed: ParsedStoryWithVoices,
        val clips: List<AudioClip>,
    ) : UiState()
    data class GeneratingVideo(
        val parsed: ParsedStoryWithVoices,
        val clips: List<AudioClip>,
    ) : UiState()
    data class AssemblingVideo(
        val parsed: ParsedStoryWithVoices,
        val clips: List<AudioClip>,
    ) : UiState()
    data class VideoReady(
        val parsed: ParsedStoryWithVoices,
        val clips: List<AudioClip>,
        val videoFile: File,
    ) : UiState()
    data class Error(val message: String) : UiState()
}

class StoryViewModel(application: Application) : AndroidViewModel(application) {

    private val api = StoryApi.create()
    private val apiKeyStore = ApiKeyStore(application)
    private var mediaPlayer: MediaPlayer? = null

    private val _uiState = MutableStateFlow<UiState>(UiState.Idle)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun hasGroqKey(): Boolean = apiKeyStore.groqApiKey.isNotBlank()

    fun getGroqKey(): String = apiKeyStore.groqApiKey

    fun getHuggingFaceToken(): String = apiKeyStore.huggingFaceApiToken

    fun saveApiKeys(groqKey: String, huggingFaceToken: String) {
        apiKeyStore.groqApiKey = groqKey.trim()
        apiKeyStore.huggingFaceApiToken = huggingFaceToken.trim()
    }

    fun submitStory(storyText: String) {
        if (storyText.isBlank()) return
        val groqKey = apiKeyStore.groqApiKey
        if (groqKey.isBlank()) {
            _uiState.value = UiState.Error("Add your Groq API key in Settings first")
            return
        }

        viewModelScope.launch {
            try {
                _uiState.value = UiState.Parsing
                val parsed = api.parseStory(StoryRequest(storyText, groqKey))

                _uiState.value = UiState.GeneratingAudio
                val audio = api.generateAudio(AudioRequest(parsed))

                _uiState.value = UiState.DialogueReady(parsed, audio.clips)
            } catch (t: Throwable) {
                _uiState.value = UiState.Error(t.message ?: "Something went wrong")
            }
        }
    }

    fun generateVideo() {
        val current = _uiState.value
        if (current !is UiState.DialogueReady) return

        val hfToken = apiKeyStore.huggingFaceApiToken
        if (hfToken.isBlank()) {
            _uiState.value = UiState.Error("Add your Hugging Face API token in Settings first")
            return
        }

        viewModelScope.launch {
            try {
                _uiState.value = UiState.GeneratingVideo(current.parsed, current.clips)
                val video = api.generateVideo(VideoRequest(current.parsed, current.clips, hfToken))

                _uiState.value = UiState.AssemblingVideo(current.parsed, current.clips)
                val finalVideo = api.assembleFinalVideo(
                    FinalVideoRequest(video_clips = video.clips, audio_clips = current.clips)
                )

                val bytes = Base64.decode(finalVideo.video_base64, Base64.DEFAULT)
                val file = File.createTempFile(
                    "final_video_", ".mp4", getApplication<Application>().cacheDir
                )
                FileOutputStream(file).use { it.write(bytes) }

                _uiState.value = UiState.VideoReady(current.parsed, current.clips, file)
            } catch (t: Throwable) {
                _uiState.value = UiState.Error(t.message ?: "Video generation failed")
            }
        }
    }

    fun playClip(clip: AudioClip) {
        mediaPlayer?.release()
        val bytes = Base64.decode(clip.audio_base64, Base64.DEFAULT)
        val file = File.createTempFile("clip_${clip.scene_id}_", ".mp3", getApplication<Application>().cacheDir)
        FileOutputStream(file).use { it.write(bytes) }

        mediaPlayer = MediaPlayer().apply {
            setDataSource(file.absolutePath)
            prepare()
            start()
        }
    }

    override fun onCleared() {
        super.onCleared()
        mediaPlayer?.release()
        mediaPlayer = null
    }
}
