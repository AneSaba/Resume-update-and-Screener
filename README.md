# Resume Tailor

AI-powered resume tailoring tool that uses Claude API to customize your resume for specific job descriptions. Generates perfectly formatted 1-page PDFs using Jake's Resume LaTeX template.

## Features

- **AI-Powered Tailoring**: Uses Claude Opus 4.5 to intelligently match your resume to job descriptions
- **ATS Optimization**: Optimizes for Applicant Tracking Systems with keyword matching
- **1-Page Guarantee**: Automatically optimizes content to fit on exactly one page
- **Beautiful Formatting**: Uses the popular Jake's Resume LaTeX template
- **Easy to Use**: Simple CLI interface with clear commands
- **Version Control**: Keeps all generated versions with timestamps

## Prerequisites

### 1. Python 3.9 or higher

Check your Python version:
```bash
python3 --version
```

### 2. LaTeX Distribution

This tool requires LaTeX to generate PDFs. Choose one option:

#### Option A: MacTeX (Full Installation - Recommended)
```bash
brew install --cask mactex
```
- Size: ~4 GB
- Includes all LaTeX packages
- Best for regular use

#### Option B: BasicTeX (Minimal Installation)
```bash
brew install --cask basictex

# After installation, add required packages:
sudo tlmgr update --self
sudo tlmgr install titlesec enumitem hyperref fancyhdr babel tabularx
```
- Size: ~100 MB
- Includes only essential packages
- Good for occasional use

**After installing LaTeX:**
1. Restart your terminal to refresh PATH
2. Verify installation:
   ```bash
   pdflatex --version
   ```
   You should see: `pdfTeX 3.14159...` or similar

### 3. Anthropic API Key

1. Go to [https://console.anthropic.com/](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (you'll need it during setup)

## Installation

### 1. Clone the Repository

```bash
cd /path/to/Resume-update-and-Screener
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API key:
```bash
ANTHROPIC_API_KEY=your_actual_api_key_here
CLAUDE_MODEL=claude-opus-4-5-20251101
MAX_TOKENS=4096
```

### 5. Initialize Your Resume

```bash
python -m src.main init
```

This creates `data/resume_source.yaml` with a template structure.

### 6. Add Your Information

Edit `data/resume_source.yaml` with your personal information, work experience, education, projects, and skills.

Example structure:
```yaml
personal_info:
  name: "Your Name"
  email: "your.email@example.com"
  phone: "(123) 456-7890"
  linkedin: "linkedin.com/in/yourprofile"
  github: "github.com/yourusername"

education:
  - institution: "Your University"
    location: "City, State"
    degree: "Bachelor of Science in Computer Science"
    dates: "Aug 2018 - May 2022"
    gpa: "3.8/4.0"

experience:
  - title: "Software Engineer"
    company: "Company Name"
    location: "City, State"
    dates: "June 2022 - Present"
    bullets:
      - "Achievement with quantified results"
      - "Responsibility with impact"
      - "Project you led"

# ... add more experience, projects, and skills
```

## Usage

### Check Configuration

Verify everything is set up correctly:

```bash
python -m src.main check
```

This will check:
- Resume file exists and is valid
- .env file is configured
- API key is set
- LaTeX is installed

### Tailor Your Resume

#### Basic Usage

```bash
python -m src.main tailor path/to/job_description.txt
```

This will:
1. Load your master resume from `data/resume_source.yaml`
2. Read the job description
3. Use Claude API to tailor your resume
4. Optimize content to fit on exactly 1 page
5. Generate a PDF in `output/pdfs/`

#### Custom Output Name

```bash
python -m src.main tailor job.txt -o software_engineer_google
```

Output will be saved as `output/pdfs/software_engineer_google.pdf`

#### Skip Optimization (Allow Multiple Pages)

```bash
python -m src.main tailor job.txt --no-optimize
```

#### Preview Without PDF Generation

```bash
python -m src.main tailor job.txt --preview
```

Shows the tailored content without generating a PDF (useful for debugging).

## CLI Commands

### `init`
Initialize a new resume template file.
```bash
python -m src.main init
```

### `tailor`
Tailor your resume to a job description.
```bash
python -m src.main tailor <job_description_file> [OPTIONS]

Options:
  -o, --output TEXT      Custom output filename (without extension)
  --no-optimize          Skip 1-page optimization
  --preview              Show tailored content without generating PDF
  --help                 Show this message and exit
```

### `check`
Verify that all dependencies and configuration are correct.
```bash
python -m src.main check
```

## Project Structure

```
Resume-update-and-Screener/
├── src/
│   ├── main.py                   # CLI application
│   ├── config.py                 # Configuration management
│   ├── models/
│   │   └── resume.py             # Resume data models
│   ├── services/
│   │   ├── claude_service.py     # Claude API integration
│   │   ├── latex_service.py      # LaTeX rendering & compilation
│   │   └── optimizer_service.py  # Page optimization
│   └── templates/
│       └── jake_resume.tex.j2    # Jake's Resume LaTeX template
├── data/
│   └── resume_source.yaml        # Your master resume
├── output/
│   ├── generated/                # Generated .tex files
│   └── pdfs/                     # Final PDF outputs
├── .env                          # Your API keys (not in git)
├── .env.example                  # API key template
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## How It Works

1. **Load Your Resume**: Reads your master resume from YAML file
2. **Analyze Job Description**: Extracts key requirements, skills, and keywords
3. **AI Tailoring**: Claude API rewrites bullet points, prioritizes relevant experience, and optimizes keyword matching
4. **LaTeX Rendering**: Converts to LaTeX using Jake's Resume template
5. **PDF Compilation**: Compiles LaTeX to PDF using pdflatex
6. **Page Optimization**: Iteratively reduces content until it fits on 1 page
7. **Output**: Saves timestamped PDF and LaTeX source

## Troubleshooting

### "pdflatex is not installed"

**Solution**: Install LaTeX using one of the methods in Prerequisites section. After installation, restart your terminal.

### "Anthropic API key not set"

**Solution**: Make sure you've:
1. Created a `.env` file (copy from `.env.example`)
2. Added your actual API key to `ANTHROPIC_API_KEY`
3. Saved the file

### "Resume file not found"

**Solution**: Run `python -m src.main init` to create the template, then edit `data/resume_source.yaml` with your information.

### "LaTeX compilation failed"

**Possible causes**:
- Special characters in resume (use plain text, avoid & % $ # without escaping)
- Very long URLs (shorten or remove)
- Invalid LaTeX in custom fields

**Solution**: Run with `--preview` flag to see the tailored content, then check for special characters.

### "Could not optimize to 1 page"

**Solution**: The tool will save the best attempt. You can:
- Manually edit `data/resume_source.yaml` to shorten content
- Use `--no-optimize` flag to see the full version
- Review older/less relevant experience and projects

### API Rate Limits

If you get rate limit errors:
- Wait a few minutes before trying again
- Claude Opus 4.5 has generous rate limits, but very rapid requests may hit limits
- Check your API usage at [https://console.anthropic.com/](https://console.anthropic.com/)

## Tips for Best Results

### Writing Your Master Resume

1. **Be Comprehensive**: Include all your experience, projects, and skills
2. **Use Action Verbs**: Start bullets with strong verbs (Developed, Led, Improved, etc.)
3. **Quantify Results**: Include numbers, percentages, metrics whenever possible
4. **Keep It Factual**: Claude will rephrase but won't fabricate information
5. **Update Regularly**: Add new projects and skills as you gain them

### Preparing Job Descriptions

1. **Copy Full Text**: Include the entire job posting for best matching
2. **Include Company Info**: Add company description if available
3. **Plain Text Format**: Save as `.txt` file
4. **Remove Formatting**: No special characters or HTML tags

### Optimizing Results

1. **Review AI Output**: Always review the generated resume before submitting
2. **Iterate**: If results aren't perfect, adjust your master resume and try again
3. **A/B Testing**: Generate multiple versions with different job descriptions
4. **Save Versions**: Keep PDFs organized by company/role for tracking applications

## Cost Considerations

- Claude Opus 4.5 costs approximately $15 per million input tokens and $75 per million output tokens
- Average resume tailoring uses ~5,000 input tokens and ~3,000 output tokens
- Cost per resume: approximately $0.30-0.50
- Budget for testing: $5-10 should cover 10-20 resumes

You can switch to Claude Sonnet for lower costs (~$0.10 per resume) by changing `CLAUDE_MODEL` in `.env`:
```
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

## Architecture

```
┌─────────────┐
│    CLI      │  User runs tailor command with job description
│   (main.py) │
└─────┬───────┘
      │
      ├──> Load resume_source.yaml
      │
      ├──> ┌──────────────────┐
      │    │ Claude Service   │  Analyze JD, tailor content
      └───>│ (claude_service) │  Returns optimized ResumeData
           └────────┬─────────┘
                    │
           ┌────────▼─────────┐
           │ Optimizer        │  Iteratively reduce content
           │ (optimizer)      │  Until fits on 1 page
           └────────┬─────────┘
                    │
           ┌────────▼─────────┐
           │ LaTeX Service    │  Render template, compile PDF
           │ (latex_service)  │  Returns PDF path
           └──────────────────┘
```

## Credits

- **LaTeX Template**: [Jake's Resume](https://github.com/jakegut/resume) by Jake Gutierrez (MIT License)
- **AI Model**: [Claude Opus 4.5](https://www.anthropic.com/claude) by Anthropic
- **Inspiration**: Based on the common need to tailor resumes for different job applications

## License

This project is open source. The Jake's Resume LaTeX template is under MIT License.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review your configuration with `python -m src.main check`
3. Ensure all prerequisites are installed correctly

## Future Enhancements

Potential features for future versions:
- Web interface for easier use
- Cover letter generation
- ATS compatibility scoring
- Batch processing for multiple job descriptions
- Resume analytics and tracking
- Multiple template options
- LinkedIn profile import

---

**Happy job hunting! 🎯**
