import os
import tkinter as tk
from tkinter import filedialog
import subprocess
import cv2


class VideoFormatConverter:
    def __init__(self):
        self.input_path = ""
        self.output_path = ""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "video_path": ("STRING", {"multiline": False, "default": ""}),
                "output_enabled": (["true", "false"],),
                "output_filename": ("STRING", {"multiline": False, "default": ""}),
                "video_format": (["avi", "mov", "mkv", "mp4"], {"default": "mp4"}),
                "codec": (
                    ["av1", "h264", "h264(NVENC)", "hevc", "hevc(NVENC)"],
                    {"default": "h264"},
                ),
                "video_quality": (
                    "INT",
                    {
                        "default": 10,
                        "min": 5,
                        "max": 40,
                        "step": 1,
                        "display": "slider",
                    },
                ),
                "frame_rate": (
                    ["8", "15", "24", "25", "30", "50", "59", "60", "120"],
                    {"default": "25"},
                ),
                "opencl_acceleration": (["enable", "disable"],),
                "video_width": ("STRING", {"multiline": False, "default": "720"}),
                "video_height": ("STRING", {"multiline": False, "default": "1280"}),
                "scaling_filter": (
                    ["bilinear", "bicubic", "neighbor", "area", "bicublin", "lanczos"],
                    {"default": "bicubic"},
                ),
                "processing_method": (["fill", "crop"],),
                "audio_codec": (["copy", "mp3", "aac"], {"default": "aac"}),
                "bit_rate": (["96", "128", "192"], {"default": "192"}),
                "audio_channels": (
                    ["original", "mono", "stereo"],
                    {"default": "stereo"},
                ),
                "sample_rate": (["44100", "48000"], {"default": "48000"}),
                # --- NEW WIDGET ADDED HERE ---
                "generate_silent_audio": (
                    ["disable", "enable"],
                    {"default": "disable"},
                ),
                "output_path": ("STRING", {"multiline": False, "default": ""}),
            },
        }

    # --- RETURN TYPES AND NAMES MODIFIED ---
    RETURN_TYPES = ("STRING", "VHS_VIDEOINFO", "STRING")
    RETURN_NAMES = ("output_filename", "video_info", "silent_audio_path")
    FUNCTION = "process_video"

    CATEGORY = "ZZX/Video"

    def select_input_file(self):
        # This function remains but won't be called in a headless environment
        # if a path is provided.
        root = tk.Tk()
        root.withdraw()
        self.input_path = filedialog.askopenfilename(title="Select input video file")
        return self.input_path

    def select_output_file(self):
        # This function remains but won't be called in a headless environment
        # if a path is provided.
        root = tk.Tk()
        root.withdraw()
        self.output_path = filedialog.asksaveasfilename(
            title="Select output video file"
        )
        return self.output_path

    def get_unique_filename(self, output_path, output_filename, video_format):
        # Ensure the output filename has the correct format extension
        base_name, _ = os.path.splitext(output_filename)
        if not output_filename:
            base_name = "video"  # Default name if empty

        counter = 0
        while True:
            # Note: The extension is now passed as video_format, not part of the filename
            new_filename = f"{base_name}_{counter:04d}.{video_format}"
            full_path = os.path.join(output_path, new_filename)
            if not os.path.exists(full_path):
                return full_path
            counter += 1

    def calculate_bitrate(self, original_bitrate, video_quality):
        min_quality = 1
        max_quality = 40
        min_bitrate = 100  # kbps for quality=40
        max_bitrate = 10000  # kbps for quality=1
        return int(
            (max_bitrate - min_bitrate)
            / (min_quality - max_quality)
            * (video_quality - max_quality)
            + max_bitrate
        )

    # --- FUNCTION SIGNATURE MODIFIED ---
    def process_video(
        self,
        video_path,
        output_enabled,
        output_filename,
        video_format,
        codec,
        video_quality,
        frame_rate,
        opencl_acceleration,
        video_width,
        video_height,
        scaling_filter,
        processing_method,
        audio_codec,
        bit_rate,
        audio_channels,
        sample_rate,
        generate_silent_audio,  # <-- NEW PARAMETER
        output_path,
    ):
        valid_codecs = {
            "avi": ["av1", "h264", "h264(NVENC)"],
            "mov": ["h264", "h264(NVENC)", "hevc", "hevc(NVENC)"],
            "mkv": ["av1", "h264", "h264(NVENC)", "hevc", "hevc(NVENC)"],
            "mp4": ["av1", "h264", "h264(NVENC)", "hevc", "hevc(NVENC)"],
        }

        if codec not in valid_codecs.get(video_format, []):
            raise ValueError("选择的格式不正确Incorrect format selected")

        if not video_path:
            raise ValueError("Input video_path is required.")

        if output_enabled == "false":
            return ("Output disabled", {}, None)

        if not output_path:
            raise ValueError("Output path is required for headless operation.")

        if not output_filename:
            raise ValueError("Output filename is required.")

        video_path = video_path.replace("\\", "/")
        output_path = output_path.replace("\\", "/")

        if not output_path.endswith("/"):
            output_path += "/"

        os.makedirs(output_path, exist_ok=True)

        output_full_path = self.get_unique_filename(
            output_path, output_filename, video_format
        )

        video_cap = cv2.VideoCapture(video_path)
        if not video_cap.isOpened():
            raise ValueError(f"{video_path} could not be loaded with cv.")
        source_fps = video_cap.get(cv2.CAP_PROP_FPS)
        source_width = int(video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        source_height = int(video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        source_frame_count = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        source_duration = source_frame_count / source_fps
        original_bitrate = video_cap.get(cv2.CAP_PROP_BITRATE) / 1000
        video_cap.release()

        bitrate = self.calculate_bitrate(original_bitrate, video_quality)

        codec_map = {
            "h264(NVENC)": "h264_nvenc",
            "hevc(NVENC)": "hevc_nvenc",
            "hevc": "libx265",
            "av1": "libaom-av1",
        }
        if codec in codec_map:
            codec = codec_map[codec]

        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-c:v",
            codec,
            "-b:v",
            f"{bitrate}k",
            "-r",
            frame_rate,
            "-vf",
            f"scale={video_width}:{video_height}:flags={scaling_filter}",
            "-c:a",
            audio_codec,
            "-b:a",
            f"{bit_rate}k",
            "-ac",
            (
                "2"
                if audio_channels == "stereo"
                else "1" if audio_channels == "mono" else "copy"
            ),
            "-ar",
            sample_rate,
            "-y",
            output_full_path,
        ]

        if opencl_acceleration == "enable":
            cmd.insert(1, "-hwaccel")
            cmd.insert(2, "opencl")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg command: {' '.join(cmd)}")
            raise RuntimeError(f"FFmpeg error: {result.stderr}")

        # --- NEW LOGIC FOR SILENT AUDIO ---
        silent_audio_output_path = None
        if generate_silent_audio == "enable":
            base_name, _ = os.path.splitext(output_full_path)
            silent_audio_output_path = f"{base_name}_silent.wav"

            print(
                f"Generating silent audio of duration {source_duration}s to {silent_audio_output_path}"
            )

            silent_cmd = [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r={sample_rate}:cl={'stereo' if audio_channels == 'stereo' else 'mono'}",
                "-t",
                str(source_duration),
                "-q:a",
                "0",  # Use high quality for WAV
                "-y",
                silent_audio_output_path,
            ]

            silent_result = subprocess.run(silent_cmd, capture_output=True, text=True)
            if silent_result.returncode != 0:
                print(
                    f"Warning: FFmpeg failed to generate silent audio: {silent_result.stderr}"
                )
                silent_audio_output_path = None  # Ensure it's None on failure

        video_cap = cv2.VideoCapture(output_full_path)
        loaded_fps = video_cap.get(cv2.CAP_PROP_FPS)
        loaded_width = int(video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        loaded_height = int(video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        loaded_frame_count = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        loaded_duration = loaded_frame_count / loaded_fps
        video_info = {
            "source_fps": source_fps,
            "source_frame_count": source_frame_count,
            "source_duration": source_duration,
            "source_width": source_width,
            "source_height": source_height,
            "loaded_fps": loaded_fps,
            "loaded_frame_count": loaded_frame_count,
            "loaded_duration": loaded_duration,
            "loaded_width": loaded_width,
            "loaded_height": loaded_height,
        }
        video_cap.release()

        # --- RETURN STATEMENT MODIFIED ---
        return (output_full_path, video_info, silent_audio_output_path)


NODE_CLASS_MAPPINGS = {"VideoFormatConverter": VideoFormatConverter}
NODE_DISPLAY_NAME_MAPPINGS = {"VideoFormatConverter": "Video Format Converter"}
