import subprocess
import sys
import time
import zipfile
from pathlib import Path

import streamlit as st

from config import (
    DEFAULT_MANUAL_PDF,
    FRAMES_V3_DIR,
    VIDEO_V3_PATH,
    V2_JSON_DIR,
    V2_OUTPUT_DIR,
    ensure_project_dirs,
)


st.set_page_config(
    page_title="AI Assembly Video Generator",
    page_icon="🛠️",
    layout="wide",
)


PIPELINE_STEPS = [
    "Upload PDF",
    "PDF to Images",
    "Manual Understanding",
    "Assembly Graph",
    "Motion Plan",
    "Scene Layout",
    "Visual Geometry",
    "Blender Render",
    "MP4 Video",
    "Complete",
]


def render_pipeline_status(active_index: int):
    cols = st.columns(5)

    for i, step in enumerate(PIPELINE_STEPS[:5]):
        with cols[i]:
            if i < active_index:
                st.success(f"[DONE]\n\n{step}")
            elif i == active_index:
                st.warning(f"[RUNNING]\n\n{step}")
            else:
                st.info(f"[WAITING]\n\n{step}")

    cols = st.columns(5)

    for j, step in enumerate(PIPELINE_STEPS[5:], start=5):
        with cols[j - 5]:
            if j < active_index:
                st.success(f"[DONE]\n\n{step}")
            elif j == active_index:
                st.warning(f"[RUNNING]\n\n{step}")
            else:
                st.info(f"[WAITING]\n\n{step}")


def detect_step(line: str, current_step: int) -> int:
    text = line.lower()

    if "extracted" in text:
        return max(current_step, 1)
    if "page_state_agent" in text or "page state" in text:
        return max(current_step, 2)
    if "universal_graph_engine" in text or "graph" in text:
        return max(current_step, 3)
    if "motion_planner" in text or "motion planner" in text:
        return max(current_step, 4)
    if "scene_layout_engine" in text or "scene layout" in text:
        return max(current_step, 5)
    if "diagram_analyzer" in text or "part shape" in text or "proxy geometry" in text:
        return max(current_step, 6)
    if "blender" in text or "saved:" in text or "rendering" in text:
        return max(current_step, 7)
    if "moviepy" in text or "video created" in text:
        return max(current_step, 8)
    if "mvp pipeline complete" in text:
        return 9

    return current_step


def run_live_command(cmd, log_box, progress_bar, status_area, current_step):
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    logs = []
    frame_count = 0
    total_frame_hint = 1000

    for line in process.stdout:
        line = line.rstrip()
        logs.append(line)

        current_step = detect_step(line, current_step)

        if "Saved:" in line and "frame_" in line:
            frame_count += 1
            progress_bar.progress(
                min(frame_count / total_frame_hint, 1.0),
                text=f"Rendering Blender frames... {frame_count}"
            )
        else:
            progress_bar.progress(
                min(current_step / (len(PIPELINE_STEPS) - 1), 1.0),
                text=f"Current step: {PIPELINE_STEPS[current_step]}"
            )

        with status_area.container():
            render_pipeline_status(current_step)

        log_box.code("\n".join(logs[-100:]))

    return_code = process.wait()

    if return_code != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    return current_step


def run_pipeline():
    status_area = st.empty()
    progress_bar = st.progress(0, text="Starting pipeline...")

    with st.expander("Live pipeline logs", expanded=True):
        log_box = st.empty()

    start_time = time.time()
    current_step = 1

    with status_area.container():
        render_pipeline_status(current_step)

    commands = [
        [sys.executable, "-u", "utils/pdf_to_images.py"],
        [sys.executable, "-u", "v2/run_mvp_pipeline.py"],
    ]

    for cmd in commands:
        current_step = run_live_command(
            cmd,
            log_box,
            progress_bar,
            status_area,
            current_step,
        )

    elapsed = time.time() - start_time

    progress_bar.progress(1.0, text=f"Complete in {elapsed:.1f} seconds")

    with status_area.container():
        render_pipeline_status(9)


def create_json_zip() -> Path:
    zip_path = Path("outputs/generated_json_files.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    json_files = list(V2_JSON_DIR.glob("*.json")) + list(V2_OUTPUT_DIR.glob("*.json"))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in json_files:
            zipf.write(file, arcname=file.name)

    return zip_path


def show_json_downloads():
    st.subheader("Generated JSON Outputs")

    json_files = list(V2_JSON_DIR.glob("*.json")) + list(V2_OUTPUT_DIR.glob("*.json"))

    if not json_files:
        st.info("No JSON files generated yet.")
        return

    zip_path = create_json_zip()

    with open(zip_path, "rb") as f:
        st.download_button(
            "Download All JSON Files",
            data=f,
            file_name="generated_json_files.zip",
            mime="application/zip",
        )

    with st.expander("View individual JSON files"):
        for file in json_files:
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"`{file}`")

            with col2:
                with open(file, "rb") as f:
                    st.download_button(
                        "Download",
                        data=f,
                        file_name=file.name,
                        mime="application/json",
                        key=str(file),
                    )


def main():
    ensure_project_dirs()

    st.title("🛠️ Azure AI Universal Assembly Video Generator")
    st.caption("Upload an instructional manual PDF and generate an AI-planned proxy assembly animation.")

    st.markdown("---")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("1. Upload Manual")

        uploaded_file = st.file_uploader(
            "Upload instruction manual PDF",
            type=["pdf"],
        )

        if uploaded_file:
            DEFAULT_MANUAL_PDF.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_MANUAL_PDF.write_bytes(uploaded_file.read())

            st.success("Manual uploaded successfully")
            st.code(str(DEFAULT_MANUAL_PDF.resolve()))
        else:
            st.info("Upload a PDF manual to begin.")

    with right:
        st.subheader("2. Output Locations")
        st.write("Frames:")
        st.code(str(FRAMES_V3_DIR.resolve()))
        st.write("Video:")
        st.code(str(VIDEO_V3_PATH.resolve()))

    st.markdown("---")

    uploaded_ready = DEFAULT_MANUAL_PDF.exists()

    if st.button(
        "Generate Assembly Video",
        type="primary",
        disabled=not uploaded_ready,
        use_container_width=True,
    ):
        try:
            run_pipeline()
            st.success("[SUCCESS] Assembly video generated successfully!")

        except Exception as e:
            st.error(str(e))
            return

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Generated Video", "Frame Preview", "JSON Outputs"])

    with tab1:
        if VIDEO_V3_PATH.exists():
            st.subheader("Generated Assembly Video")
            st.video(str(VIDEO_V3_PATH))

            with open(VIDEO_V3_PATH, "rb") as f:
                st.download_button(
                    "Download MP4",
                    data=f,
                    file_name="assembly_animation_v3.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )
        else:
            st.info("Video will appear here after generation.")

    with tab2:
        if FRAMES_V3_DIR.exists():
            frames = sorted(FRAMES_V3_DIR.glob("*.png"))

            if frames:
                st.subheader(f"Frame Preview ({len(frames)} frames)")

                preview_cols = st.columns(3)
                preview_frames = [
                    frames[0],
                    frames[len(frames) // 2],
                    frames[-1],
                ]
                labels = ["First frame", "Middle frame", "Final frame"]

                for col, frame, label in zip(preview_cols, preview_frames, labels):
                    with col:
                        st.image(str(frame), caption=label)
            else:
                st.info("Frames will appear here after rendering.")
        else:
            st.info("Frames folder not created yet.")

    with tab3:
        show_json_downloads()


if __name__ == "__main__":
    main()