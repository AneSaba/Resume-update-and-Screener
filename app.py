"""Streamlit web UI for resume tailoring."""
import streamlit as st
import yaml
from pathlib import Path
import tempfile
from datetime import datetime
import shutil

from src.models.resume import ResumeData
from src.services.claude_service import ClaudeService, ClaudeAPIError
from src.services.latex_service import LaTeXService
from src.services.optimizer_service import PageOptimizer
from src.config import get_settings


def get_downloads_folder():
    """Get the user's Downloads folder path."""
    home = Path.home()
    downloads = home / "Downloads"
    if not downloads.exists():
        downloads.mkdir(parents=True, exist_ok=True)
    return downloads


st.set_page_config(
    page_title="AI Resume Tailor",
    page_icon="📄",
    layout="wide"
)

st.title("🤖 AI Resume Tailor")
st.markdown("Tailor your resume to match any job description using Claude AI")

# Initialize services
@st.cache_resource
def init_services():
    settings = get_settings()
    claude_service = ClaudeService()
    latex_service = LaTeXService()
    optimizer = PageOptimizer(latex_service, claude_service)
    return settings, claude_service, latex_service, optimizer


try:
    settings, claude_service, latex_service, optimizer = init_services()

    # Check if LaTeX is installed
    if not latex_service.check_latex_installed():
        st.error("⚠️ LaTeX (pdflatex) is not installed! Please install MacTeX or BasicTeX first.")
        st.stop()

    # Load resume data
    resume_path = settings.resume_source_path
    if not resume_path.exists():
        st.error(f"❌ Resume file not found at {resume_path}")
        st.info("Run `python -m src.main init` to create a template.")
        st.stop()

    with open(resume_path, 'r', encoding='utf-8') as f:
        resume_dict = yaml.safe_load(f)
    resume_data = ResumeData.from_dict(resume_dict)

    st.success(f"✅ Loaded resume for **{resume_data.personal_info.name}**")

except Exception as e:
    st.error(f"Error initializing: {e}")
    st.stop()

# Main UI
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📋 Job Description")
    job_description = st.text_area(
        "Paste the job description here:",
        height=400,
        placeholder="Copy and paste the full job description from the job posting..."
    )

    st.subheader("⚙️ Options")
    max_bullets = st.slider("Max bullets per job", 3, 8, 6)
    max_projects = st.slider("Max projects", 1, 3, 2)
    skip_optimize = st.checkbox("Skip 1-page optimization (faster)", value=False)

with col2:
    st.subheader("📊 Status")
    status_placeholder = st.empty()
    progress_placeholder = st.empty()

    if st.button("🚀 Generate Tailored Resume", type="primary", use_container_width=True):
        if not job_description.strip():
            st.error("Please paste a job description first!")
        else:
            try:
                # Show progress
                with status_placeholder.container():
                    st.info("🤖 Tailoring resume with Claude AI...")
                progress_placeholder.progress(0.2)

                # Tailor resume
                tailored_data = claude_service.tailor_resume(
                    resume_data,
                    job_description,
                    max_bullets_per_job=max_bullets,
                    max_projects=max_projects
                )

                progress_placeholder.progress(0.5)

                # Generate PDF
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"resume_{timestamp}"

                if skip_optimize:
                    with status_placeholder.container():
                        st.info("📄 Generating PDF...")
                    pdf_path, page_count = latex_service.render_and_compile(
                        tailored_data,
                        output_name
                    )
                else:
                    with status_placeholder.container():
                        st.info("📄 Generating and optimizing PDF (may take 30-60 seconds)...")
                    progress_placeholder.progress(0.6)

                    tailored_data, pdf_path = optimizer.optimize_to_one_page(
                        tailored_data,
                        output_name,
                        max_iterations=5,
                        verbose=False
                    )
                    page_count = latex_service.count_pages(pdf_path)

                progress_placeholder.progress(1.0)

                # Copy to Downloads folder
                downloads_folder = get_downloads_folder()
                final_filename = f"resume_tailored_{timestamp}.pdf"
                downloads_path = downloads_folder / final_filename
                shutil.copy(pdf_path, downloads_path)

                # Success!
                with status_placeholder.container():
                    st.success(f"✅ Resume generated successfully! ({page_count} page{'s' if page_count != 1 else ''})")
                    st.success(f"💾 Saved to Downloads: `{final_filename}`")

                # Download button (for backup/alternative download)
                with open(pdf_path, 'rb') as pdf_file:
                    st.download_button(
                        label="⬇️ Download Resume PDF",
                        data=pdf_file,
                        file_name=final_filename,
                        mime="application/pdf",
                        use_container_width=True
                    )

                # Show preview info
                st.info(f"📁 Also saved in project: `{pdf_path}`")

            except ClaudeAPIError as e:
                with status_placeholder.container():
                    st.error(f"❌ Claude API Error: {e}")
                progress_placeholder.empty()
            except Exception as e:
                with status_placeholder.container():
                    st.error(f"❌ Error: {e}")
                progress_placeholder.empty()

# Sidebar with info
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This tool uses **Claude AI** to intelligently tailor your resume to match specific job descriptions.

    **Features:**
    - 🎯 Keyword optimization for ATS
    - 📊 XYZ format bullet points
    - ⚡ Bold key terms
    - 📄 1-page optimization

    **Tips:**
    - Paste the complete job description
    - Include requirements, responsibilities, and qualifications
    - The tool will reorder bullets to highlight relevant experience
    """)

    st.header("🔑 API Key")
    api_key_status = "✅ Set" if settings.anthropic_api_key else "❌ Not set"
    st.write(f"Status: {api_key_status}")

    if not settings.anthropic_api_key:
        st.warning("Set your `ANTHROPIC_API_KEY` in `.env`")
