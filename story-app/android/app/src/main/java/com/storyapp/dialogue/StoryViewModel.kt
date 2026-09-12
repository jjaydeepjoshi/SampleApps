package com.storyapp.dialogue

import android.app.Application
import android.media.MediaPlayer
import android.util.Base64
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.storyapp.dialogue.api.AudioClip
import com.storyapp.dialogue.api.AudioRequest
import com.storyapp.dialogue.api.ParsedStoryWithVoices
import com.storyapp.dialogue.api.StoryApi
import com.storyapp.dialogue.api.StoryRequest
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
    data class Ready(
        val parsed: ParsedStoryWithVoices,
        val clips: List<AudioClip>,
    ) : UiState()
    data class Error(val message: String) : UiState()
}

class StoryViewModel(application: Application) : AndroidViewModel(application) {

    private val api = StoryApi.create()
    private var mediaPlayer: MediaPlayer? = null

    private val _uiState = MutableStateFlow<UiState>(UiState.Idle)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun submitStory(storyText: String) {
        if (storyText.isBlank()) return
        viewModelScope.launch {
            try {
                _uiState.value = UiState.Parsing
                val parsed = api.parseStory(StoryRequest(storyText))

                _uiState.value = UiState.GeneratingAudio
                val audio = api.generateAudio(AudioRequest(parsed))

                _uiState.value = UiState.Ready(parsed, audio.clips)
            } catch (t: Throwable) {
                _uiState.value = UiState.Error(t.message ?: "Something went wrong")
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
