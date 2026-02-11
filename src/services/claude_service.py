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

    TAILORING_PROMPT_TEMPLATE = """⚠️⚠️⚠️ CRITICAL RULES - READ FIRST ⚠️⚠️⚠️

RULE 1 - SPACING (check EVERY bullet before submitting):
- MUST add space after symbols: "3× at" NOT "3×at", "70% by" NOT "70%by", "2× via" NOT "2×via"

RULE 2 - BULLET LENGTH (ABSOLUTE MAXIMUM 75 chars visible - COUNT AFTER REMOVING \\textbf):
- Strip ALL \\textbf{{}} markup, then count remaining text - MUST be ≤75 chars
- Example: "Built \\textbf{{Python}} services" → remove markup → "Built Python services" (21 chars) ✓
- If ANY bullet exceeds 75 visible chars, you MUST shorten it before submitting
- Target 65-72 chars to be safe - bullets at 73-75 are HIGH RISK for wrapping
- TOO LONG (107): "Developed C++ Unreal Engine medical simulation for WHO deployed in 12 countries; improved frame stability 25%"
- STILL TOO LONG (85): "Built backend infra for multi-tenant platform w/ Python and Go serving 200K+ users"
- STILL TOO LONG (77): "Built backend for multi-tenant platform w/ Python, Go"
- FIXED (68): "Built \\textbf{{backend}} for \\textbf{{multi-tenant}} w/ \\textbf{{Python}}, \\textbf{{Go}}"
- BEST (62): "Developed \\textbf{{C++}} modules for WHO \\textbf{{simulation}}"

RULE 3 - LaTeX SYNTAX (CRITICAL - check before submitting):
- EVERY \\textbf{{ MUST have matching closing }}
- Check: count opening {{ and closing }} - must be EQUAL
- WRONG: "Built \\textbf{{Python services" (missing }})
- CORRECT: "Built \\textbf{{Python}} services"
- In JSON strings, use double backslash: \\textbf NOT \textbf (single \t becomes tab!)

You are an expert resume writer and ATS optimization specialist. Tailor this resume to match the job description while maintaining factual accuracy.

Job Description:
{job_description}

Current Resume Data (JSON):
{resume_json}

Instructions:
1. Carefully analyze the job description for:
   - Required skills and technologies (list EVERY technology mentioned)
   - Key responsibilities and qualifications
   - Important keywords for ATS systems (tools, frameworks, methodologies)
   - Company values and culture indicators
   - Domain-specific terminology and jargon
   - Soft skills and competencies mentioned

2. Tailor the resume by:
   - CRITICAL: Incorporate as many JD keywords as possible while maintaining truthfulness
   - If a technology/skill from JD matches resume experience, MUST include that exact term
   - Reordering experience bullets to highlight most relevant achievements first
   - Rewriting bullet points to emphasize matching skills and experiences
   - Prioritizing projects that demonstrate relevant technologies from JD
   - Adjusting technical skills order to highlight JD-relevant ones FIRST
   - Add JD technologies to bullets where genuinely applicable
   - Mirror JD terminology: if JD says "microservices", use "microservices" not "distributed systems"
   - For each bullet, aim to include 2-3 keywords from JD naturally
   - BOLD ALL keywords that match JD using LaTeX \\textbf{{}} syntax - you MUST use TWO backslashes
   - CRITICAL: Write \\textbf NOT \textbf (single backslash \t will break as tab character)
   - Bold: technologies, frameworks, metrics, important verbs, domain terms
   - Example: "Built \\textbf{{Spring Boot}} \\textbf{{microservices}} with \\textbf{{Redis}} caching serving \\textbf{{200K+ users}}"
   - For percents in bold: \\textbf{{25%}} - note the TWO backslashes before textbf
   - Maximize keyword density without fabricating experience

3. Keyword Strategy - SYSTEMATIC EXTRACTION:
   Step 1: EXTRACT from JD (read JD line by line):
   - ALL single-word technical terms: languages (Python, Java), frameworks (React, Spring Boot), tools (Docker, Redis)
   - ALL multi-word phrases: "distributed systems", "architectural trade-offs", "design patterns", "technical leadership"
   - ALL compound technical terms: "synchronous and asynchronous design patterns", "distributed transaction management", "database architecture"
   - ALL methodologies and practices: "best engineering practices", "code review", "unit tested", "continuous integration"
   - ALL soft skills with exact phrasing: if JD says "technical leadership" use that, not "led team"
   - ALL operational terms: "24x7", "high-volume", "large scale", "reliable", "speediness and quality"
   - ALL domain-specific protocols/standards: "TCP/IP", "REST APIs", "relational databases"

   Step 2: MAP to resume content:
   - For EACH keyword/phrase extracted, identify where in resume it genuinely applies
   - If keyword describes something you did, substitute the JD's exact terminology
   - Examples of mappings:
     * "monitoring" → use JD term "engineering productivity" if that's what JD emphasizes
     * "design decisions" → use "architectural trade-offs" if JD uses that phrase
     * "async processing" → use "synchronous and asynchronous design patterns" if applicable
     * "database work" → use "relational databases" and "database architecture" if truthful
     * "always available" → use "operate 24x7" if JD uses that phrasing

   Step 3: INCORPORATE systematically:
   - Technical Skills section: List JD keywords FIRST, then others
   - Each bullet: aim for 3-5 JD keywords per bullet (not just 2-3)
   - Use exact multi-word phrases from JD, not paraphrases
   - Bold EVERY keyword that matches between resume and JD
   - For each experience bullet, ask: "What keywords from JD list apply here?" and add them
   - Target: 70-90% of JD keywords should appear somewhere in final resume

4. Critical constraints:
   - NEVER fabricate or exaggerate information
   - Maintain all factual details (dates, companies, degrees, etc.)
   - Keep the same overall structure
   - Include ALL work experiences from the original resume (do not remove any)
   - Each experience entry should have {max_bullets_per_job} bullet points maximum
   - Include maximum {max_projects} projects (prioritize most relevant)

   ⚠️ SPACING - CHECK EVERY BULLET ⚠️:
   - MANDATORY: Add space after ALL symbols: "3× at" NOT "3×at", "40% by" NOT "40%by", "2× via" NOT "2×via"
   - This is causing wrapping issues - check EVERY bullet before submitting

   ⚠️ BULLET LENGTH - HARD LIMIT 75 CHARS ⚠️:
   - ABSOLUTE MAXIMUM: 75 characters of visible text (count ONLY text, NOT LaTeX markup like \\textbf{{}})
   - REQUIRED: After writing EACH bullet, manually count visible characters
   - If approaching 70+ chars while writing, STOP and find shorter phrasing
   - If exceeds 75 chars, MUST shorten using:
     * Abbreviations: "w/" not "with", "via" not "by doing"
     * Remove articles: delete "a/an/the" where natural
     * Shorter synonyms: "apps" not "applications", "sync/async" not "synchronous/asynchronous"
     * Combine terms: "multi-tier scalable" instead of "multi-tier scalable distributed"
   - Example TOO LONG (107 chars): "Build and maintain large scale distributed systems for multi-tenant analytics platform serving 200K+ users"
   - Example FIXED (68 chars): "Build \\textbf{{distributed systems}} for \\textbf{{multi-tenant}} w/ \\textbf{{200K+ users}}"

   CONTENT FORMAT:
   - Pack maximum information: action verb + metric + HOW you did it (method/technologies used)
   - ALWAYS use complete XYZ format: "Accomplished [X] as measured by [Y] by doing [Z]"
   - The METHOD (Z part) is REQUIRED - never omit the "how" or technologies used
   - Example GOOD (88 chars): "Reduced \\textbf{{API}} latency \\textbf{{40%}} by optimizing \\textbf{{queries}} w/ \\textbf{{indexes}} and \\textbf{{caching}}"
   - Example TOO LONG (100 chars): "Built distributed applications with synchronous/asynchronous design patterns for high-volume workloads" - WRONG, will wrap!
   - Example FIXED (87 chars): "Built \\textbf{{distributed apps}} w/ \\textbf{{sync/async patterns}} for \\textbf{{high-volume}} workloads"
   - Use strong action verbs, quantify ALL achievements, and include specific technologies/methods used
   - More technical keywords naturally included = better ATS performance

5. Optimization for 1-page format:
   - Write CONCISE single-line bullets to maximize information density
   - Use shorter phrasing but preserve ALL key details, metrics, AND keywords
   - Recent positions (2024-2025) should have more bullets showing depth of experience
   - Compress sentences: "Built X that achieved Y" not "Responsible for building X which resulted in Y"
   - Keep all quantified achievements AND technical keywords - both are critical for ATS

6. Return format:
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
        prompt = f"""⚠️⚠️⚠️ CRITICAL RULES - READ FIRST ⚠️⚠️⚠️

RULE 1 - SPACING (check EVERY bullet):
- MUST add space after symbols: "3× at" NOT "3×at", "70% by" NOT "70%by"

RULE 2 - BULLET LENGTH (ABSOLUTE MAXIMUM 70 chars visible - COUNT AFTER REMOVING \\textbf):
- Strip ALL \\textbf{{}} markup, then count remaining text - MUST be ≤70 chars
- Example: "Built \\textbf{{Python}} services" → remove markup → "Built Python services" (21 chars) ✓
- If ANY bullet exceeds 70 visible chars, you MUST shorten it before submitting
- Target 60-67 chars to be safe - bullets at 68-70 are risky
- TOO LONG (107): "Developed C++ Unreal Engine medical simulation for WHO deployed in 12 countries; improved frame stability 25%"
- STILL TOO LONG (85): "Built backend infra for multi-tenant platform w/ Python and Go serving 200K+ users"
- FIXED (62): "Built \\textbf{{backend}} for \\textbf{{multi-tenant}} w/ \\textbf{{Python}}, \\textbf{{Go}}"

RULE 3 - LaTeX SYNTAX (CRITICAL - check before submitting):
- EVERY \\textbf{{ MUST have matching closing }}
- Check: opening {{ and closing }} - must be EQUAL
- WRONG: "Built \\textbf{{Python services" (missing }})
- CORRECT: "Built \\textbf{{Python}} services"
- In JSON strings, use double backslash: \\textbf NOT \textbf (single \t becomes tab!)

You are optimizing a resume from {current_pages} pages to {target_pages} page(s).

Resume Data (JSON):
{json.dumps(resume_data.to_dict(), indent=2)}

3. Strategies to use (in order of preference):
   - Compress bullets to single lines with XYZ format keeping all metrics
   - ALWAYS use complete XYZ format: "Accomplished [X] as measured by [Y] by doing [Z]"
   - NEVER omit the method/technology (the Z part) - it contains critical keywords
   - CRITICAL: Add spaces around metrics and symbols (e.g., "3× at" not "3×at")
   - Use shorter synonyms: "via" not "by doing", "w/" not "with", abbreviate naturally
   - Remove least impactful projects (keep top 2 most impressive)
   - Reduce bullet points for OLDER positions only (keep 4-6 bullets for recent roles)
   - Compress wording but preserve all technical details, numbers, and keywords
   - Consolidate similar skills in the skills section
   - For positions before 2023, keep fewer details

4. Maintain:
   - All factual accuracy
   - Most impressive achievements and quantified results
   - Recent and relevant experience in full detail
   - Overall structure and formatting
   - ALL keywords and technical terms - never remove technologies/tools mentioned
   - BOLD ALL key terms using \\textbf{{}} - MUST use TWO backslashes (single \t becomes tab!)
   - Bold technologies, frameworks, metrics, keywords, domain terms
   - Example: \\textbf{{MongoDB}} or \\textbf{{25%}} - always TWO backslashes
   - Compress wording but preserve every technical keyword

5. Return ONLY valid JSON matching the input structure.

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
