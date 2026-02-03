"""Main CLI application for resume tailoring."""
import sys
from pathlib import Path
from datetime import datetime

import click
import yaml
from pydantic import ValidationError

from src.config import get_settings
from src.models.resume import ResumeData
from src.services.claude_service import ClaudeService, ClaudeAPIError
from src.services.latex_service import LaTeXService, LaTeXCompilationError
from src.services.optimizer_service import PageOptimizer, OptimizationError


@click.group()
def cli():
    """Resume Tailor - AI-powered resume tailoring using Claude API."""
    pass


@cli.command()
def init():
    """Initialize a new resume source YAML file."""
    settings = get_settings()
    resume_path = settings.resume_source_path

    if resume_path.exists():
        click.echo(
            click.style(f"Resume file already exists at: {resume_path}", fg="yellow")
        )
        if not click.confirm("Do you want to overwrite it?"):
            click.echo("Initialization cancelled.")
            return

    # The template already exists in data/resume_source.yaml
    click.echo(click.style(f"✓ Resume template ready at: {resume_path}", fg="green"))
    click.echo("\nNext steps:")
    click.echo("1. Edit the file with your personal information")
    click.echo("2. Create a .env file with your Anthropic API key (see .env.example)")
    click.echo("3. Run: python -m src.main tailor <job_description_file>")


@cli.command()
@click.argument('job_description', type=click.Path(exists=True))
@click.option('--output', '-o', default=None, help='Custom output filename (without extension)')
@click.option('--no-optimize', is_flag=True, help='Skip 1-page optimization')
@click.option('--preview', is_flag=True, help='Show tailored content without generating PDF')
def tailor(job_description, output, no_optimize, preview):
    """
    Tailor resume to match a job description.

    JOB_DESCRIPTION: Path to text file containing the job description
    """
    try:
        settings = get_settings()

        # Load job description
        click.echo(click.style("Loading job description...", fg="blue"))
        jd_path = Path(job_description)
        jd_text = jd_path.read_text(encoding="utf-8")

        if not jd_text.strip():
            click.echo(click.style("Error: Job description file is empty", fg="red"))
            sys.exit(1)

        click.echo(f"  Loaded {len(jd_text)} characters from {jd_path.name}")

        # Load resume data
        click.echo(click.style("\nLoading resume data...", fg="blue"))
        resume_path = settings.resume_source_path

        if not resume_path.exists():
            click.echo(click.style(f"Error: Resume file not found at {resume_path}", fg="red"))
            click.echo("Run 'python -m src.main init' first to create a template.")
            sys.exit(1)

        try:
            with open(resume_path, 'r', encoding='utf-8') as f:
                resume_dict = yaml.safe_load(f)
            resume_data = ResumeData.from_dict(resume_dict)
            click.echo(f"  Loaded resume for {resume_data.personal_info.name}")
        except ValidationError as e:
            click.echo(click.style(f"Error: Invalid resume data format", fg="red"))
            click.echo(str(e))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Error loading resume: {e}", fg="red"))
            sys.exit(1)

        # Initialize services
        claude_service = ClaudeService()
        latex_service = LaTeXService()

        # Check if LaTeX is installed
        if not latex_service.check_latex_installed() and not preview:
            click.echo(click.style("\nError: LaTeX (pdflatex) is not installed!", fg="red"))
            click.echo("\nTo install LaTeX on macOS:")
            click.echo("  brew install --cask mactex")
            click.echo("\nOr for a smaller installation:")
            click.echo("  brew install --cask basictex")
            click.echo("  sudo tlmgr update --self")
            click.echo("  sudo tlmgr install titlesec enumitem hyperref fancyhdr babel tabularx")
            click.echo("\nAfter installation, restart your terminal and try again.")
            sys.exit(1)

        # Tailor resume with Claude
        click.echo(click.style("\nTailoring resume with Claude API...", fg="blue"))
        click.echo("  (This may take 10-30 seconds)")

        try:
            tailored_data = claude_service.tailor_resume(
                resume_data,
                jd_text,
                max_bullets_per_job=6,
                max_projects=2
            )
            click.echo(click.style("  ✓ Resume tailored successfully!", fg="green"))
        except ClaudeAPIError as e:
            click.echo(click.style(f"\nError calling Claude API: {e}", fg="red"))
            click.echo("\nPlease check:")
            click.echo("1. Your ANTHROPIC_API_KEY is set correctly in .env")
            click.echo("2. Your API key is valid and has available credits")
            click.echo("3. You have internet connectivity")
            sys.exit(1)

        # Preview mode - just show the tailored data
        if preview:
            click.echo(click.style("\n=== Tailored Resume Preview ===", fg="cyan"))
            click.echo(yaml.dump(tailored_data.to_dict(), default_flow_style=False))
            click.echo(click.style("\nPreview complete. Use without --preview to generate PDF.", fg="blue"))
            return

        # Generate output filename
        if output:
            output_name = output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"resume_{timestamp}"

        # Optimize to one page or just compile
        if no_optimize:
            click.echo(click.style("\nGenerating PDF (without optimization)...", fg="blue"))
            try:
                pdf_path, page_count = latex_service.render_and_compile(
                    tailored_data,
                    output_name
                )
                click.echo(click.style(f"  ✓ PDF generated: {page_count} page(s)", fg="green"))
            except LaTeXCompilationError as e:
                click.echo(click.style(f"\nLaTeX compilation error: {e}", fg="red"))
                sys.exit(1)
        else:
            click.echo(click.style("\nOptimizing for 1-page format...", fg="blue"))
            optimizer = PageOptimizer(latex_service, claude_service)

            try:
                optimized_data, pdf_path = optimizer.optimize_to_one_page(
                    tailored_data,
                    output_name,
                    max_iterations=5,
                    verbose=True
                )
            except OptimizationError as e:
                click.echo(click.style(f"\nOptimization error: {e}", fg="red"))
                sys.exit(1)

        # Success!
        click.echo(click.style("\n✓ Resume generated successfully!", fg="green", bold=True))
        click.echo(f"\nOutput saved to: {click.style(str(pdf_path), fg='cyan')}")
        click.echo(f"LaTeX source: {click.style(str(latex_service.generated_dir / f'{output_name}.tex'), fg='cyan')}")

        # Open PDF (macOS)
        if click.confirm("\nWould you like to open the PDF?", default=True):
            import subprocess
            subprocess.run(["open", str(pdf_path)])

    except KeyboardInterrupt:
        click.echo(click.style("\n\nOperation cancelled by user", fg="yellow"))
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"\n\nUnexpected error: {e}", fg="red"))
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def check():
    """Check if all dependencies are properly configured."""
    click.echo(click.style("Checking configuration...\n", fg="blue", bold=True))

    all_good = True

    # Check resume file
    settings = get_settings()
    resume_path = settings.resume_source_path

    if resume_path.exists():
        click.echo(click.style("✓", fg="green") + f" Resume file found: {resume_path}")
        try:
            with open(resume_path, 'r', encoding='utf-8') as f:
                resume_dict = yaml.safe_load(f)
            ResumeData.from_dict(resume_dict)
            click.echo(click.style("✓", fg="green") + " Resume data is valid")
        except Exception as e:
            click.echo(click.style("✗", fg="red") + f" Resume data is invalid: {e}")
            all_good = False
    else:
        click.echo(click.style("✗", fg="red") + f" Resume file not found: {resume_path}")
        click.echo("  Run 'python -m src.main init' to create one")
        all_good = False

    # Check .env file
    env_path = settings.project_root / ".env"
    if env_path.exists():
        click.echo(click.style("✓", fg="green") + " .env file found")
    else:
        click.echo(click.style("✗", fg="red") + " .env file not found")
        click.echo("  Copy .env.example to .env and add your API key")
        all_good = False

    # Check API key
    try:
        if settings.anthropic_api_key and settings.anthropic_api_key != "your_api_key_here":
            click.echo(click.style("✓", fg="green") + " Anthropic API key is configured")
        else:
            click.echo(click.style("✗", fg="red") + " Anthropic API key not set")
            click.echo("  Add ANTHROPIC_API_KEY to your .env file")
            all_good = False
    except Exception:
        click.echo(click.style("✗", fg="red") + " Could not load API key from .env")
        all_good = False

    # Check LaTeX
    latex_service = LaTeXService()
    if latex_service.check_latex_installed():
        click.echo(click.style("✓", fg="green") + " LaTeX (pdflatex) is installed")
    else:
        click.echo(click.style("✗", fg="red") + " LaTeX (pdflatex) not found")
        click.echo("  Install with: brew install --cask mactex")
        all_good = False

    # Summary
    click.echo()
    if all_good:
        click.echo(click.style("✓ All checks passed! You're ready to tailor resumes.", fg="green", bold=True))
    else:
        click.echo(click.style("✗ Some checks failed. Please fix the issues above.", fg="red", bold=True))
        sys.exit(1)


if __name__ == "__main__":
    cli()
