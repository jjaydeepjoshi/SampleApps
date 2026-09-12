package com.storyapp.dialogue

import android.net.Uri
import android.os.Bundle
import android.widget.MediaController
import android.widget.VideoView
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.FileProvider
import com.storyapp.dialogue.api.AudioClip
import com.storyapp.dialogue.api.ParsedStoryWithVoices
import java.io.File

class MainActivity : ComponentActivity() {
    private val viewModel: StoryViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    StoryScreen(viewModel)
                }
            }
        }
    }
}

@Composable
fun StoryScreen(viewModel: StoryViewModel) {
    val state by viewModel.uiState.collectAsState()
    var storyText by remember { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text(text = "Story Dialogue", style = MaterialTheme.typography.headlineSmall)

        OutlinedTextField(
            value = storyText,
            onValueChange = { storyText = it },
            modifier = Modifier.fillMaxWidth().height(180.dp),
            label = { Text("Paste your story") },
        )

        Button(
            onClick = { viewModel.submitStory(storyText) },
            modifier = Modifier.padding(top = 12.dp),
        ) {
            Text("Generate dialogue")
        }

        when (val current = state) {
            is UiState.Idle -> Unit
            is UiState.Parsing -> LoadingRow("Understanding the story...")
            is UiState.GeneratingAudio -> LoadingRow("Generating character voices...")
            is UiState.GeneratingVideo -> LoadingRow("Generating scene videos...")
            is UiState.AssemblingVideo -> LoadingRow("Assembling final video...")
            is UiState.Error -> Text(
                text = "Error: ${current.message}",
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(top = 12.dp),
            )
            is UiState.DialogueReady -> Column {
                ResultList(
                    parsed = current.parsed,
                    clips = current.clips,
                    onPlay = viewModel::playClip,
                )
                Button(
                    onClick = { viewModel.generateVideo() },
                    modifier = Modifier.padding(top = 12.dp),
                ) {
                    Text("Generate video")
                }
            }
            is UiState.VideoReady -> Column {
                ResultList(
                    parsed = current.parsed,
                    clips = current.clips,
                    onPlay = viewModel::playClip,
                )
                Text(
                    "Final video",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 16.dp),
                )
                VideoPlayer(current.videoFile)
            }
        }
    }
}

@Composable
fun LoadingRow(label: String) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        CircularProgressIndicator()
        Text(label)
    }
}

@Composable
fun ResultList(
    parsed: ParsedStoryWithVoices,
    clips: List<AudioClip>,
    onPlay: (AudioClip) -> Unit,
) {
    LazyColumn(modifier = Modifier.padding(top = 16.dp)) {
        item {
            Text("Characters", style = MaterialTheme.typography.titleMedium)
        }
        items(parsed.characters) { character ->
            Text("• ${character.name}: ${character.description}")
        }

        item {
            Text(
                "Dialogue",
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 16.dp),
            )
        }
        items(clips) { clip ->
            Column(modifier = Modifier.padding(vertical = 6.dp)) {
                Text("${clip.speaker}: \"${clip.line}\"")
                Button(onClick = { onPlay(clip) }) {
                    Text("Play")
                }
            }
        }
    }
}

@Composable
fun VideoPlayer(videoFile: File) {
    AndroidView(
        modifier = Modifier.fillMaxWidth().height(220.dp),
        factory = { context ->
            VideoView(context).apply {
                val uri: Uri = FileProvider.getUriForFile(
                    context, "${context.packageName}.fileprovider", videoFile
                )
                setVideoURI(uri)
                setMediaController(MediaController(context).also { it.setAnchorView(this) })
                setOnPreparedListener { start() }
            }
        },
    )
}
