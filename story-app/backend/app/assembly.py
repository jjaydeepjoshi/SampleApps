import base64
import os
import subprocess
import tempfile

from .models import AudioClip, VideoClip


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")


def _write_bytes(path: str, data_base64: str) -> None:
    with open(path, "wb") as f:
        f.write(base64.b64decode(data_base64))


def _write_concat_list(path: str, file_paths: list[str]) -> None:
    with open(path, "w") as f:
        for p in file_paths:
            f.write(f"file '{p}'\n")


def assemble_final_video(video_clips: list[VideoClip], audio_clips: list[AudioClip]) -> bytes:
    audio_by_scene: dict[int, list[AudioClip]] = {}
    for clip in audio_clips:
        audio_by_scene.setdefault(clip.scene_id, []).append(clip)

    with tempfile.TemporaryDirectory() as tmp:
        scene_paths: list[str] = []

        for video_clip in sorted(video_clips, key=lambda v: v.scene_id):
            video_path = os.path.join(tmp, f"scene_{video_clip.scene_id}.mp4")
            _write_bytes(video_path, video_clip.video_base64)

            scene_audio = audio_by_scene.get(video_clip.scene_id, [])
            if not scene_audio:
                scene_paths.append(video_path)
                continue

            audio_paths = []
            for i, audio_clip in enumerate(scene_audio):
                audio_path = os.path.join(tmp, f"scene_{video_clip.scene_id}_line_{i}.mp3")
                _write_bytes(audio_path, audio_clip.audio_base64)
                audio_paths.append(audio_path)

            if len(audio_paths) == 1:
                scene_audio_path = audio_paths[0]
            else:
                scene_audio_path = os.path.join(tmp, f"scene_{video_clip.scene_id}_audio.mp3")
                list_path = os.path.join(tmp, f"scene_{video_clip.scene_id}_audio_list.txt")
                _write_concat_list(list_path, audio_paths)
                _run_ffmpeg(
                    ["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", scene_audio_path]
                )

            merged_path = os.path.join(tmp, f"scene_{video_clip.scene_id}_merged.mp4")
            _run_ffmpeg(
                [
                    "-i", video_path,
                    "-i", scene_audio_path,
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-shortest",
                    merged_path,
                ]
            )
            scene_paths.append(merged_path)

        final_list_path = os.path.join(tmp, "final_list.txt")
        _write_concat_list(final_list_path, scene_paths)

        final_path = os.path.join(tmp, "final.mp4")
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", final_list_path, "-c", "copy", final_path])

        with open(final_path, "rb") as f:
            return f.read()
