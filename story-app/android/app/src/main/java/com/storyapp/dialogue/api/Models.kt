package com.storyapp.dialogue.api

data class StoryRequest(val story: String)

data class Character(
    val name: String,
    val description: String,
    val personality: String,
    val voice_gender: String,
    val voice_age: String,
    val voice_tone: String,
)

data class DialogueLine(
    val speaker: String,
    val line: String,
    val emotion: String,
)

data class Scene(
    val id: Int,
    val setting: String,
    val description: String,
    val dialogue: List<DialogueLine>,
)

data class VoiceAssignment(
    val character: String,
    val voice_id: String,
)

data class ParsedStoryWithVoices(
    val characters: List<Character>,
    val scenes: List<Scene>,
    val voice_assignments: List<VoiceAssignment>,
)

data class AudioRequest(val parsed_story: ParsedStoryWithVoices)

data class AudioClip(
    val scene_id: Int,
    val speaker: String,
    val line: String,
    val audio_base64: String,
    val duration_seconds: Double,
)

data class AudioResponse(val clips: List<AudioClip>)

data class VideoRequest(
    val parsed_story: ParsedStoryWithVoices,
    val audio_clips: List<AudioClip>,
)

data class VideoClip(
    val scene_id: Int,
    val prompt: String,
    val video_base64: String,
)

data class VideoResponse(val clips: List<VideoClip>)

data class FinalVideoRequest(
    val video_clips: List<VideoClip>,
    val audio_clips: List<AudioClip>,
)

data class FinalVideoResponse(val video_base64: String)
