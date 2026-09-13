package com.storyapp.dialogue.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

interface StoryApi {
    @POST("parse-story")
    suspend fun parseStory(@Body request: StoryRequest): ParsedStoryWithVoices

    @POST("generate-audio")
    suspend fun generateAudio(@Body request: AudioRequest): AudioResponse

    @POST("generate-video")
    suspend fun generateVideo(@Body request: VideoRequest): VideoResponse

    @POST("generate-scene-video")
    suspend fun generateSceneVideo(@Body request: SceneVideoRequest): VideoClip

    @POST("assemble-final-video")
    suspend fun assembleFinalVideo(@Body request: FinalVideoRequest): FinalVideoResponse

    companion object {
        fun create(baseUrl: String): StoryApi {
            val logging = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BASIC
            }
            val client = OkHttpClient.Builder()
                .addInterceptor(logging)
                .connectTimeout(30, TimeUnit.SECONDS)
                // Video generation polls a slow third-party API server-side before
                // responding, so this needs much more headroom than the audio calls.
                .readTimeout(10, TimeUnit.MINUTES)
                .build()

            // Retrofit requires a trailing slash on the base URL.
            val normalizedUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"

            return Retrofit.Builder()
                .baseUrl(normalizedUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(StoryApi::class.java)
        }
    }
}
