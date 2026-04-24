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

🚨🚨🚨 BEFORE YOU SUBMIT: EVERY bullet MUST be 90-100 chars (after removing \\textbf markup) 🚨🚨🚨
Bullets under 90 chars are TOO SHORT. Bullets over 100 chars WILL WRAP to 2 lines! This is MANDATORY.

RULE 1 - SPACING (check EVERY bullet before submitting):
- MUST add space after symbols: "3× at" NOT "3×at", "70% by" NOT "70%by", "2× via" NOT "2×via"

RULE 2 - BULLET LENGTH ⚠️ CRITICAL: 90-100 CHARS MAX - STRICT ENFORCEMENT ⚠️:
- TARGET RANGE: 90-100 characters (after removing ALL \\textbf{{}} markup)
- ABSOLUTE MAXIMUM: 100 characters - anything longer WILL WRAP and break formatting!
- Count method: Remove all \\textbf{{}} tags, count what remains - MUST be 90-100 chars
- CRITICAL: Bold text takes MORE SPACE - limit to MAX 4 bold sections per bullet
- Before submitting: Manually COUNT EVERY BULLET - no bullet can exceed 100 chars!

HOW TO COUNT (follow this exactly):
1. Take your bullet text
2. Remove all \\textbf{{}} markup completely
3. Count remaining characters - MUST be 90-100, NO EXCEPTIONS!
4. Count bold sections - MUST be MAX 4 per bullet (bold text takes more space!)

EXAMPLES WITH ACTUAL COUNTS:
- PERFECT (98 chars, 3 bold): "Built \\textbf{{backend}} for \\textbf{{multi-tenant}} platform w/ \\textbf{{Python}} serving 200K+ users"
  WITHOUT MARKUP: "Built backend for multi-tenant platform w/ Python serving 200K+ users" = 98 chars ✓
  BOLD COUNT: 3 ✓

- PERFECT (102 chars, 4 bold): "Optimized \\textbf{{MongoDB}} queries, improving \\textbf{{API latency}} \\textbf{{40%}} for \\textbf{{200K+ users}}"
  WITHOUT MARKUP: "Optimized MongoDB queries, improving API latency 40% for 200K+ users" = 102 chars ✓
  BOLD COUNT: 4 ✓

- TOO LONG - REJECTED (114): "Build and maintain distributed applications for multi-tenant analytics platform using Golang and REST APIs"
  COUNT: 114 chars - WRAPS TO 2 LINES! Must trim to 100!

- TOO LONG - REJECTED (115): "Built React and TypeScript accessibility components meeting WCAG 2.1, deployed across 1K+ production sites"
  COUNT: 115 chars - WRAPS TO 2 LINES! Must trim to 100!

- FIXED (102): "Built \\textbf{{React}} accessibility components meeting \\textbf{{WCAG 2.1}}, deployed across \\textbf{{1K+ sites}}"
  WITHOUT MARKUP: "Built React accessibility components meeting WCAG 2.1, deployed across 1K+ sites" = 102 chars ✓
  BOLD SECTIONS: 3 ✓

RULE 3 - LaTeX SYNTAX (CRITICAL - check before submitting):
- In JSON: Use double backslash before textbf, but SINGLE curly braces
- CORRECT JSON format: use two backslashes, one opening brace, one closing brace
- Do NOT escape the curly braces themselves - only the backslash
- Every textbf opening brace must have matching closing brace

MULTIPLICATION SYMBOLS (CRITICAL):
- For "3x" or "2x" multipliers, write them as plain "3x" or "2x" (lowercase x)
- Do NOT use LaTeX math mode or special symbols
- CORRECT in JSON: "improved latency 3x at peak" or "cutting time 2x faster"
- WRONG: Do not use dollar signs, backslashes, or times symbols

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
   - NEVER modify the education section — copy it exactly as-is from the input JSON
   - Keep the same overall structure
   - Include ALL work experiences from the original resume (do not remove any)
   - Each experience entry should have {max_bullets_per_job} bullet points maximum
   - Include maximum {max_projects} projects (prioritize most relevant)

   ⚠️ SPACING - CHECK EVERY BULLET ⚠️:
   - MANDATORY: Add space after ALL symbols: "3× at" NOT "3×at", "40% by" NOT "40%by", "2× via" NOT "2×via"
   - This is causing wrapping issues - check EVERY bullet before submitting

   ⚠️⚠️⚠️ BULLET LENGTH - STRICT: 90-100 CHARS MAX (NO WRAPPING!) ⚠️⚠️⚠️:
   - REQUIRED MINIMUM: 90 characters (after removing \\textbf markup)
   - OPTIMAL TARGET: 90-100 characters
   - ABSOLUTE MAXIMUM: 100 characters - ANYTHING OVER 100 WILL WRAP TO 2 LINES!
   - MAX 4 BOLD SECTIONS per bullet - more than 4 bold sections cause wrapping!
   - CRITICAL: After writing EACH bullet, COUNT the visible characters (strip \\textbf{{}} first)
   - IF ANY bullet is under 90 chars, ADD MORE DETAIL - more technologies, methods, context
   - IF ANY bullet is over 100 chars, TRIM IT - use "w/" for "with", remove filler words
   - Every bullet MUST fit on 1 line - wrapping breaks the format and wastes space
   - Example PERFECT (98): "Built \\textbf{{backend}} for \\textbf{{multi-tenant}} platform w/ \\textbf{{Python}} serving 200K+ users"
   - Example PERFECT (102): "Optimized \\textbf{{MongoDB}} queries, improving \\textbf{{API latency}} \\textbf{{40%}} for \\textbf{{200K+ users}}"
   - Example TOO SHORT (75): "Built \\textbf{{backend}} for \\textbf{{platform}} serving \\textbf{{users}}" - REJECTED! Add technologies and methods!

   CONTENT FORMAT:
   - Pack maximum information: action verb + metric + HOW you did it (method/technologies used)
   - ALWAYS use complete XYZ format: "Accomplished [X] as measured by [Y] by doing [Z]"
   - The METHOD (Z part) is REQUIRED - never omit the "how" or technologies used
   - Example EXCELLENT (98 chars): "Reduced \\textbf{{API latency}} \\textbf{{40%}} via \\textbf{{query optimization}} and \\textbf{{Redis caching}}"
   - Example GOOD (104 chars): "Built \\textbf{{distributed apps}} w/ \\textbf{{async patterns}} for \\textbf{{multi-tenant}} \\textbf{{workloads}}"
   - Example GREAT (102 chars): "Architected \\textbf{{microservices}} using \\textbf{{Spring Boot}}, serving \\textbf{{1M+ requests/day}}"
   - Use strong action verbs, quantify ALL achievements, and include specific technologies/methods used
   - More technical keywords naturally included = better ATS performance

5. Optimization for 1-page format:
   - ⚠️ EVERY BULLET: 90-100 CHARS MAX - MUST FIT ON 1 LINE ⚠️
   - Write DETAILED bullets with technical stack and metrics - NO WRAPPING ALLOWED
   - Recent positions (2024-2025): maximize bullets (5-6), EACH 90-100 chars exactly
   - ALWAYS include complete XYZ format, but fit within 100 char limit
   - If bullet exceeds 100 chars, TRIM using "w/" for "with", remove filler words
   - Pack in multiple technologies: "\\textbf{{Python}}, \\textbf{{Django}}, \\textbf{{PostgreSQL}}, \\textbf{{Redis}}"
   - If under 90 chars, ADD detail; if over 100 chars, TRIM immediately
   - Target 90-100 chars - sweet spot for detail without wrapping

6. MANDATORY PRE-SUBMISSION CHECK:
   Before submitting your JSON response, you MUST verify EVERY bullet:
   - For EACH bullet, mentally strip the \\textbf{{}} markup
   - COUNT the remaining characters - MUST be 90-100 chars
   - If under 90 chars: ADD technologies, methods, context
   - If over 100 chars: TRIM using "w/" instead of "with", remove "and", cut filler
   - Check that NO bullet exceeds 100 chars (anything over wraps!)
   - Do NOT submit until ALL bullets are 90-100 characters
   - This verification step is MANDATORY - wrapping breaks the 1-page format

7. Return format:
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

🚨🚨🚨 BEFORE YOU SUBMIT: EVERY bullet MUST be 90-100 chars (after removing \\textbf markup) 🚨🚨🚨
Bullets under 90 chars are TOO SHORT. Bullets over 100 chars WILL WRAP to 2 lines! This is MANDATORY.

RULE 1 - SPACING (check EVERY bullet):
- MUST add space after symbols: "3× at" NOT "3×at", "70% by" NOT "70%by"

RULE 2 - BULLET LENGTH ⚠️ CRITICAL: 90-100 CHARS MAX - STRICT ENFORCEMENT ⚠️:
- TARGET RANGE: 90-100 characters (after removing ALL \\textbf{{}} markup)
- ABSOLUTE MAXIMUM: 100 characters - anything longer WILL WRAP and break formatting!
- Count method: Remove all \\textbf{{}} tags, count what remains - MUST be 90-100 chars
- Before submitting: Manually COUNT EVERY BULLET - no bullet can exceed 100 chars!

HOW TO COUNT (follow this exactly):
1. Take your bullet text
2. Remove all \\textbf{{}} markup completely
3. Count remaining characters - MUST be 90-100, NO EXCEPTIONS!
4. Count bold sections - MUST be MAX 4 per bullet (bold text takes more space!)

EXAMPLES WITH ACTUAL COUNTS:
- PERFECT (98 chars, 3 bold): "Built \\textbf{{backend}} for \\textbf{{multi-tenant}} platform w/ \\textbf{{Python}} serving 200K+ users"
  WITHOUT MARKUP: "Built backend for multi-tenant platform w/ Python serving 200K+ users" = 98 chars ✓
  BOLD COUNT: 3 ✓

- PERFECT (102 chars, 4 bold): "Optimized \\textbf{{MongoDB}} queries, improving \\textbf{{API latency}} \\textbf{{40%}} for \\textbf{{200K+ users}}"
  WITHOUT MARKUP: "Optimized MongoDB queries, improving API latency 40% for 200K+ users" = 102 chars ✓
  BOLD COUNT: 4 ✓

- TOO LONG - REJECTED (114): "Build and maintain distributed applications for multi-tenant analytics platform using Golang and REST APIs"
  COUNT: 114 chars - WRAPS TO 2 LINES! Must trim to 100!

- TOO LONG - REJECTED (115): "Built React and TypeScript accessibility components meeting WCAG 2.1, deployed across 1K+ production sites"
  COUNT: 115 chars - WRAPS TO 2 LINES! Must trim to 100!

- FIXED (102): "Built \\textbf{{React}} accessibility components meeting \\textbf{{WCAG 2.1}}, deployed across \\textbf{{1K+ sites}}"
  WITHOUT MARKUP: "Built React accessibility components meeting WCAG 2.1, deployed across 1K+ sites" = 102 chars ✓
  BOLD SECTIONS: 3 ✓

RULE 3 - LaTeX SYNTAX (CRITICAL - check before submitting):
- In JSON: Use double backslash before textbf, but SINGLE curly braces
- CORRECT JSON format: use two backslashes, one opening brace, one closing brace
- Do NOT escape the curly braces themselves - only the backslash
- Every textbf opening brace must have matching closing brace

MULTIPLICATION SYMBOLS (CRITICAL):
- For "3x" or "2x" multipliers, write them as plain "3x" or "2x" (lowercase x)
- Do NOT use LaTeX math mode or special symbols
- CORRECT in JSON: "improved latency 3x at peak" or "cutting time 2x faster"
- WRONG: Do not use dollar signs, backslashes, or times symbols

You are optimizing a resume from {current_pages} pages to {target_pages} page(s).

Resume Data (JSON):
{json.dumps(resume_data.to_dict(), indent=2)}

3. Strategies to use (in order of preference):
   - ⚠️ EVERY BULLET MUST BE 90-100 CHARS MAX - add detail if under 95, trim if over 105 ⚠️
   - Write LONG, COMPLETE bullets with full XYZ format: "Accomplished [X] measured by [Y] using [Z: specific tech stack]"
   - NEVER omit the method/technology (the Z part) - list multiple technologies per bullet
   - Pack in technical keywords: "using \\textbf{{Python}}, \\textbf{{Django}}, \\textbf{{PostgreSQL}}, and \\textbf{{Redis}}"
   - DO NOT abbreviate unless over 100 chars - spell out "with", "using", "through", etc.
   - Remove least impactful projects (keep top 2 most impressive)
   - Reduce bullet COUNT for older positions (keep 3-4), but each bullet still 90-100 chars
   - Recent roles (2024-2025): 5-6 LONG bullets (90-100 chars each) showing depth
   - If bullet is under 90 chars, ADD MORE: more technologies, more methods, more context
   - If bullet exceeds 100 chars, it will WRAP to 2 lines - TRIM immediately
   - Consolidate similar skills in the skills section
   - EVERY bullet must be 90-100 chars - bullets over 100 will wrap and break format!

4. Maintain:
   - All factual accuracy
   - Most impressive achievements and quantified results
   - Recent and relevant experience in full detail
   - Overall structure and formatting
   - ALL keywords and technical terms - never remove technologies/tools mentioned
   - BOLD ALL key terms using \\textbf{{}} - MUST use TWO backslashes (single \t becomes tab!)
   - Bold technologies, frameworks, metrics, keywords, domain terms
   - Example: \\textbf{{MongoDB}} or \\textbf{{25%}} - always TWO backslashes
   - Add detail to preserve every technical keyword - DO NOT compress excessively

5. MANDATORY PRE-SUBMISSION CHECK:
   Before submitting your JSON response, you MUST verify EVERY bullet:
   - For EACH bullet, mentally strip the \\textbf{{}} markup
   - COUNT the remaining characters - MUST be 90-100 chars
   - If ANY bullet is under 90 characters, GO BACK and add more detail
   - If ANY bullet exceeds 100 characters, TRIM IT - it will wrap to 2 lines!
   - Do NOT submit until ALL bullets are 90-100 characters exactly
   - This verification step is MANDATORY - no exceptions

6. Return ONLY valid JSON matching the input structure.

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
