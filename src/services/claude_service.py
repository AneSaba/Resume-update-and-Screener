"""Claude API service for resume tailoring."""
import json
import re
from typing import Optional

from anthropic import Anthropic
from pydantic import ValidationError

from src.config import get_settings
from src.models.resume import ResumeData


class ClaudeAPIError(Exception):
    """Raised when Claude API call fails."""
    pass


class ClaudeService:
    """Service for interacting with Claude API to tailor resumes."""

    TAILORING_PROMPT_TEMPLATE = """You are an expert resume writer and ATS optimization specialist. Your task is to tailor a resume to match a specific job description while maintaining factual accuracy.

Job Description:
{job_description}

Current Resume Data (in JSON format):
{resume_json}

Instructions:
1. Carefully analyze the job description for:
   - Required skills and technologies
   - Key responsibilities and qualifications
   - Important keywords for ATS systems
   - Company values and culture indicators

2. Tailor the resume by:
   - Reordering experience bullets to highlight most relevant achievements first
   - Rewriting bullet points to emphasize matching skills and experiences
   - Prioritizing projects that demonstrate relevant technologies
   - Adjusting technical skills order to highlight most relevant ones
   - Using keywords from the job description naturally (no keyword stuffing)

3. Critical constraints:
   - NEVER fabricate or exaggerate information
   - Maintain all factual details (dates, companies, degrees, etc.)
   - Keep the same overall structure
   - Each experience entry should have {max_bullets_per_job} bullet points maximum
   - Include maximum {max_projects} projects (prioritize most relevant)
   - Each bullet point should be concise (under 120 characters if possible)
   - Use strong action verbs and quantify achievements when available

4. Optimization for 1-page format:
   - Be concise while maintaining impact
   - Focus on quality over quantity of bullet points
   - Remove or shorten less relevant details

5. Return format:
   - Return ONLY a valid JSON object matching the exact structure of the input
   - Do not include any explanation or commentary
   - Ensure all required fields are present
   - The JSON should be parseable by Python's json.loads()

Return the tailored resume data as valid JSON now:"""

    def __init__(self):
        """Initialize the Claude service."""
        self.settings = get_settings()
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)

    def tailor_resume(
        self,
        resume_data: ResumeData,
        job_description: str,
        max_bullets_per_job: int = 3,
        max_projects: int = 3
    ) -> ResumeData:
        """
        Tailor resume content to match job description using Claude API.

        Args:
            resume_data: Original resume data
            job_description: Target job description text
            max_bullets_per_job: Maximum bullet points per job
            max_projects: Maximum number of projects to include

        Returns:
            Tailored resume data

        Raises:
            ClaudeAPIError: If API call fails or response is invalid
        """
        # Prepare the prompt
        resume_json = json.dumps(resume_data.to_dict(), indent=2)
        prompt = self.TAILORING_PROMPT_TEMPLATE.format(
            job_description=job_description,
            resume_json=resume_json,
            max_bullets_per_job=max_bullets_per_job,
            max_projects=max_projects
        )

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=self.settings.max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract text response
            response_text = message.content[0].text

            # Parse JSON from response
            tailored_json = self._extract_json(response_text)

            # Validate and return as ResumeData
            try:
                tailored_data = ResumeData.from_dict(tailored_json)
                return tailored_data
            except ValidationError as e:
                raise ClaudeAPIError(
                    f"Claude returned invalid resume data structure: {e}"
                )

        except Exception as e:
            if isinstance(e, ClaudeAPIError):
                raise
            raise ClaudeAPIError(f"Failed to tailor resume with Claude API: {e}")

    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON object from Claude's response text.

        Args:
            text: Response text that may contain JSON

        Returns:
            Parsed JSON as dict

        Raises:
            ClaudeAPIError: If JSON cannot be extracted or parsed
        """
        # Try to find JSON in code blocks first
        code_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        code_match = re.search(code_block_pattern, text, re.DOTALL)

        if code_match:
            json_str = code_match.group(1)
        else:
            # Try to find raw JSON object
            json_pattern = r"\{.*\}"
            json_match = re.search(json_pattern, text, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)
            else:
                # Maybe the entire response is JSON
                json_str = text.strip()

        # Try to parse the JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ClaudeAPIError(
                f"Failed to parse JSON from Claude response: {e}\n"
                f"Response text:\n{text[:500]}..."
            )

    def suggest_content_reduction(
        self,
        resume_data: ResumeData,
        current_pages: int,
        target_pages: int = 1
    ) -> ResumeData:
        """
        Use Claude to intelligently suggest content reduction.

        Args:
            resume_data: Current resume data
            current_pages: Current number of pages
            target_pages: Target number of pages (default: 1)

        Returns:
            Resume data with reduced content

        Raises:
            ClaudeAPIError: If API call fails
        """
        prompt = f"""You are helping optimize a resume that is currently {current_pages} pages long to fit on {target_pages} page(s).

Current Resume Data (in JSON format):
{json.dumps(resume_data.to_dict(), indent=2)}

Instructions:
1. Reduce the content while preserving the most impactful information
2. Strategies to use (in order of preference):
   - Remove least impactful projects (keep top 2-3 most impressive)
   - Reduce bullet points per job (aim for 2-3 per position)
   - Shorten verbose bullet points while keeping key achievements
   - Consolidate similar skills in the skills section
   - For older/less relevant positions, keep fewer details

3. Maintain:
   - All factual accuracy
   - Most impressive achievements and quantified results
   - Recent and relevant experience in full detail
   - Overall structure and formatting

4. Return ONLY valid JSON matching the input structure.

Return the optimized resume data as valid JSON now:"""

        try:
            message = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=self.settings.max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            reduced_json = self._extract_json(response_text)

            try:
                return ResumeData.from_dict(reduced_json)
            except ValidationError as e:
                raise ClaudeAPIError(
                    f"Claude returned invalid resume data structure: {e}"
                )

        except Exception as e:
            if isinstance(e, ClaudeAPIError):
                raise
            raise ClaudeAPIError(
                f"Failed to get content reduction suggestions: {e}"
            )
