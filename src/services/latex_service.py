"""LaTeX template rendering and PDF compilation service."""
import re
import subprocess
from pathlib import Path
from typing import Optional
import shutil

from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader

from src.config import get_settings
from src.models.resume import ResumeData


class LaTeXCompilationError(Exception):
    """Raised when LaTeX compilation fails."""
    pass


class LaTeXService:
    """Service for rendering LaTeX templates and compiling PDFs."""

    def __init__(self):
        """Initialize the LaTeX service."""
        self.settings = get_settings()
        self.templates_dir = self.settings.templates_dir
        self.output_dir = self.settings.output_dir
        self.generated_dir = self.output_dir / "generated"
        self.pdfs_dir = self.output_dir / "pdfs"

        # Ensure output directories exist
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.pdfs_dir.mkdir(parents=True, exist_ok=True)

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False  # LaTeX has its own escaping rules
        )

        # Add custom LaTeX escape filter
        self.env.filters['latex_escape'] = self._latex_escape

    @staticmethod
    def _latex_escape(text: str) -> str:
        """
        Escape special LaTeX characters in text while preserving valid LaTeX commands.

        Args:
            text: Text to escape

        Returns:
            LaTeX-safe text
        """
        if not isinstance(text, str):
            return text

        # Step 1: Protect valid LaTeX commands by temporarily replacing them
        # This includes \textbf{...}, \textit{...}, etc.
        # But first, we need to escape special chars inside the commands

        # Find and temporarily replace LaTeX commands
        latex_commands = []
        # Use a placeholder with only alphanumeric chars that won't be affected by escaping
        # Format: XLATEXPROTECTX followed by index followed by XLATEXPROTECTX
        def get_placeholder(idx):
            return f"XLATEXPROTECTX{idx}XLATEXPROTECTX"

        # Pattern to match \textbf{...}, \textit{...}, etc. with optional space before brace
        # This handles both \textbf{text} and \textbf {text}
        latex_cmd_pattern = r'(\\text(?:bf|it|tt|sc|sl|em))\s*\{([^}]*)\}'

        def protect_command(match):
            idx = len(latex_commands)
            cmd_name = match.group(1)  # e.g., \textbf
            content = match.group(2)    # e.g., ≈25%

            # First, handle Unicode characters in the content
            unicode_replacements = {
                '≈': r'$\approx$',
                '±': r'$\pm$',
                '×': r'$\times$',
                '÷': r'$\div$',
                '≤': r'$\leq$',
                '≥': r'$\geq$',
                '≠': r'$\neq$',
                '→': r'$\rightarrow$',
                '←': r'$\leftarrow$',
                '−': r'$-$',
                '–': r'--',
                '—': r'---',
                '"': r'``',
                '"': r"''",
                ''': r'`',
                ''': r"'",
                '…': r'\ldots{}',
            }
            for char, replacement in unicode_replacements.items():
                content = content.replace(char, replacement)

            # Then escape special LaTeX characters in the content
            # Note: We skip '$' because Unicode replacements use it for math mode
            # Also, we need to be careful not to double-escape already escaped characters
            replacements_dict = {
                '%': r'\%',
                '&': r'\&',
                '#': r'\#',
                '_': r'\_'
            }
            for char, escaped in replacements_dict.items():
                # Only replace if not already escaped
                content = content.replace(char, escaped)

            # Reconstruct the command with escaped content
            # Use string concatenation to avoid any f-string escape issues
            cmd = cmd_name + '{' + content + '}'
            latex_commands.append(cmd)
            return get_placeholder(idx)

        text = re.sub(latex_cmd_pattern, protect_command, text)

        # Step 2: Handle common Unicode characters first (before escaping special chars)
        unicode_replacements = {
            '≈': r'$\approx$',  # Approximately equal
            '±': r'$\pm$',      # Plus-minus
            '×': r'$\times$',   # Multiplication
            '÷': r'$\div$',     # Division
            '≤': r'$\leq$',     # Less than or equal
            '≥': r'$\geq$',     # Greater than or equal
            '≠': r'$\neq$',     # Not equal
            '→': r'$\rightarrow$',  # Right arrow
            '←': r'$\leftarrow$',   # Left arrow
            '−': r'$-$',        # Minus sign (different from hyphen)
            '–': r'--',         # En dash
            '—': r'---',        # Em dash
            '"': r'``',         # Left double quote
            '"': r"''",         # Right double quote
            ''': r'`',          # Left single quote
            ''': r"'",          # Right single quote
            '…': r'\ldots{}',   # Ellipsis
        }

        for char, replacement in unicode_replacements.items():
            text = text.replace(char, replacement)

        # Step 3: Escape special LaTeX characters
        replacements = {
            '\\': r'\textbackslash{}',
            '%': r'\%',
            '$': r'\$',
            '&': r'\&',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
        }

        # Apply replacements (backslash must be first)
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        # Step 4: Restore protected LaTeX commands
        for idx, cmd in enumerate(latex_commands):
            text = text.replace(get_placeholder(idx), cmd)

        return text

    def check_latex_installed(self) -> bool:
        """Check if pdflatex is installed and available."""
        return shutil.which("pdflatex") is not None

    def render_template(self, resume_data: ResumeData) -> str:
        """
        Render the LaTeX template with resume data.

        Args:
            resume_data: Resume data model

        Returns:
            Rendered LaTeX content as string
        """
        template = self.env.get_template("jake_resume.tex.j2")

        # Convert resume data to dict for template rendering
        context = {
            "personal_info": resume_data.personal_info.model_dump(),
            "education": [edu.model_dump() for edu in resume_data.education],
            "experience": [exp.model_dump() for exp in resume_data.experience],
            "projects": [proj.model_dump() for proj in resume_data.projects],
            "skills": resume_data.skills,
        }

        return template.render(**context)

    def compile_latex(self, tex_content: str, output_name: str) -> Path:
        """
        Compile LaTeX content to PDF.

        Args:
            tex_content: LaTeX source code
            output_name: Base name for output files (without extension)

        Returns:
            Path to generated PDF

        Raises:
            LaTeXCompilationError: If compilation fails
        """
        # Check if pdflatex is available
        if not self.check_latex_installed():
            raise LaTeXCompilationError(
                "pdflatex is not installed or not in PATH. "
                "Please install LaTeX (MacTeX for macOS: brew install --cask mactex)"
            )

        # Write .tex file
        tex_path = self.generated_dir / f"{output_name}.tex"
        tex_path.write_text(tex_content, encoding="utf-8")

        # Compile with pdflatex (run twice for proper formatting)
        for run in range(2):
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-output-directory", str(self.generated_dir),
                    str(tex_path)
                ],
                capture_output=True,
                text=True,
                cwd=str(self.generated_dir)
            )

            if result.returncode != 0:
                error_msg = self._extract_latex_error(result.stdout)
                raise LaTeXCompilationError(
                    f"LaTeX compilation failed:\n{error_msg}\n\n"
                    f"Full output:\n{result.stdout}"
                )

        # Move PDF to pdfs directory
        source_pdf = self.generated_dir / f"{output_name}.pdf"
        dest_pdf = self.pdfs_dir / f"{output_name}.pdf"

        if not source_pdf.exists():
            raise LaTeXCompilationError(
                f"PDF was not generated at expected location: {source_pdf}"
            )

        shutil.copy(source_pdf, dest_pdf)

        # Clean up auxiliary files
        self.clean_aux_files(output_name)

        return dest_pdf

    def _extract_latex_error(self, latex_output: str) -> str:
        """Extract the most relevant error message from LaTeX output."""
        lines = latex_output.split("\n")
        error_lines = []

        for i, line in enumerate(lines):
            if line.startswith("!"):
                # Found an error line
                error_lines.append(line)
                # Add next few lines for context
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip():
                        error_lines.append(lines[j])

        if error_lines:
            return "\n".join(error_lines)
        return "Unknown LaTeX error (check full output)"

    def count_pages(self, pdf_path: Path) -> int:
        """
        Count the number of pages in a PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages
        """
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)

    def validate_one_page(self, pdf_path: Path) -> bool:
        """
        Check if PDF is exactly one page.

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if exactly one page, False otherwise
        """
        return self.count_pages(pdf_path) == 1

    def clean_aux_files(self, output_name: str) -> None:
        """
        Remove auxiliary LaTeX files.

        Args:
            output_name: Base name of files to clean
        """
        extensions = [".aux", ".log", ".out", ".toc", ".fdb_latexmk", ".fls", ".synctex.gz"]

        for ext in extensions:
            file_path = self.generated_dir / f"{output_name}{ext}"
            if file_path.exists():
                file_path.unlink()

        # Also remove PDF from generated dir (we keep it in pdfs dir)
        pdf_in_generated = self.generated_dir / f"{output_name}.pdf"
        if pdf_in_generated.exists():
            pdf_in_generated.unlink()

    def render_and_compile(self, resume_data: ResumeData, output_name: str) -> tuple[Path, int]:
        """
        Render template and compile to PDF in one step.

        Args:
            resume_data: Resume data model
            output_name: Base name for output files

        Returns:
            Tuple of (pdf_path, page_count)
        """
        tex_content = self.render_template(resume_data)
        pdf_path = self.compile_latex(tex_content, output_name)
        page_count = self.count_pages(pdf_path)

        return pdf_path, page_count
