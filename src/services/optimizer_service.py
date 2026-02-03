"""Page optimization service to ensure resume fits on exactly one page."""
from pathlib import Path
from typing import Optional
import click

from src.models.resume import ResumeData
from src.services.claude_service import ClaudeService
from src.services.latex_service import LaTeXService


class OptimizationError(Exception):
    """Raised when optimization fails."""
    pass


class PageOptimizer:
    """Service for optimizing resume to fit on exactly one page."""

    def __init__(self, latex_service: Optional[LaTeXService] = None,
                 claude_service: Optional[ClaudeService] = None):
        """
        Initialize the page optimizer.

        Args:
            latex_service: LaTeX service instance (creates new if None)
            claude_service: Claude service instance (creates new if None)
        """
        self.latex_service = latex_service or LaTeXService()
        self.claude_service = claude_service or ClaudeService()

    def optimize_to_one_page(
        self,
        resume_data: ResumeData,
        output_name: str,
        max_iterations: int = 5,
        verbose: bool = True
    ) -> tuple[ResumeData, Path]:
        """
        Iteratively optimize resume to fit on exactly one page.

        Args:
            resume_data: Initial resume data
            output_name: Base name for output files
            max_iterations: Maximum optimization attempts
            verbose: Whether to print progress messages

        Returns:
            Tuple of (optimized_resume_data, pdf_path)

        Raises:
            OptimizationError: If cannot optimize to one page after max iterations
        """
        current_data = resume_data
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if verbose:
                click.echo(f"  Optimization attempt {iteration}/{max_iterations}...")

            # Render and compile
            try:
                pdf_path, page_count = self.latex_service.render_and_compile(
                    current_data,
                    f"{output_name}_attempt_{iteration}"
                )
            except Exception as e:
                raise OptimizationError(f"Failed to compile LaTeX: {e}")

            if verbose:
                click.echo(f"    Generated PDF with {page_count} page(s)")

            # Check if we've achieved the target
            if page_count == 1:
                if verbose:
                    click.echo(click.style("  ✓ Resume fits on 1 page!", fg="green"))

                # Copy to final location
                final_pdf = self.latex_service.pdfs_dir / f"{output_name}.pdf"
                final_pdf.write_bytes(pdf_path.read_bytes())

                # Save final .tex file
                tex_content = self.latex_service.render_template(current_data)
                final_tex = self.latex_service.generated_dir / f"{output_name}.tex"
                final_tex.write_text(tex_content, encoding="utf-8")

                return current_data, final_pdf

            elif page_count < 1:
                raise OptimizationError("Resume is empty or invalid")

            else:
                # Too many pages - need to reduce content
                if verbose:
                    click.echo(f"    Resume is too long ({page_count} pages), reducing content...")

                if iteration >= max_iterations:
                    # Last attempt failed
                    break

                # Use Claude to intelligently reduce content
                try:
                    current_data = self.claude_service.suggest_content_reduction(
                        current_data,
                        current_pages=page_count,
                        target_pages=1
                    )
                except Exception as e:
                    if verbose:
                        click.echo(
                            click.style(f"    Warning: Claude optimization failed: {e}", fg="yellow")
                        )
                    # Fall back to manual reduction
                    current_data = self._manual_content_reduction(current_data)

        # If we get here, we couldn't optimize to one page
        if verbose:
            click.echo(
                click.style(
                    f"  ⚠ Warning: Could not optimize to exactly 1 page after {max_iterations} attempts",
                    fg="yellow"
                )
            )
            click.echo("  Saving best attempt...")

        # Save best attempt
        pdf_path, page_count = self.latex_service.render_and_compile(
            current_data,
            output_name
        )

        return current_data, pdf_path

    def _manual_content_reduction(self, resume_data: ResumeData) -> ResumeData:
        """
        Manually reduce content using heuristics.

        This is a fallback when Claude-based reduction fails.

        Args:
            resume_data: Resume data to reduce

        Returns:
            Reduced resume data
        """
        # Strategy 1: Limit projects to top 2
        if len(resume_data.projects) > 2:
            resume_data.projects = resume_data.projects[:2]

        # Strategy 2: Reduce bullets per job
        for exp in resume_data.experience:
            if len(exp.bullets) > 3:
                exp.bullets = exp.bullets[:3]

        # Strategy 3: Reduce bullets per project
        for proj in resume_data.projects:
            if len(proj.bullets) > 2:
                proj.bullets = proj.bullets[:2]

        # Strategy 4: Remove GPA from older education entries (keep only the first)
        if len(resume_data.education) > 1:
            for edu in resume_data.education[1:]:
                edu.gpa = None
                edu.additional_info = None

        return resume_data

    def check_page_count(self, resume_data: ResumeData, output_name: str) -> int:
        """
        Compile resume and return page count without optimization.

        Args:
            resume_data: Resume data to check
            output_name: Base name for output files

        Returns:
            Number of pages in generated PDF
        """
        _, page_count = self.latex_service.render_and_compile(
            resume_data,
            output_name
        )
        return page_count
