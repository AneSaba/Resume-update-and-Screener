"""Pydantic models for resume data structure."""
from typing import List, Dict, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class PersonalInfo(BaseModel):
    """Personal contact information."""
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    github: Optional[str] = Field(None, description="GitHub profile URL")
    location: Optional[str] = Field(None, description="City, State or location")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Basic phone number validation."""
        # Remove common phone formatting characters
        cleaned = ''.join(c for c in v if c.isdigit() or c in '()- +')
        if len(cleaned) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        return v


class Education(BaseModel):
    """Education entry."""
    institution: str = Field(..., description="University or school name")
    location: str = Field(..., description="City, State")
    degree: str = Field(..., description="Degree and major")
    dates: str = Field(..., description="Date range (e.g., 'Aug 2018 - May 2022')")
    gpa: Optional[str] = Field(None, description="GPA (optional)")
    additional_info: Optional[List[str]] = Field(None, description="Additional details or honors")


class Experience(BaseModel):
    """Work experience entry."""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: str = Field(..., description="City, State")
    dates: str = Field(..., description="Date range (e.g., 'June 2022 - Present')")
    bullets: List[str] = Field(..., description="List of achievements and responsibilities")

    @field_validator('bullets')
    @classmethod
    def validate_bullets(cls, v: List[str]) -> List[str]:
        """Ensure bullets list is not empty."""
        if not v:
            raise ValueError("Experience must have at least one bullet point")
        return v


class Project(BaseModel):
    """Project entry."""
    name: str = Field(..., description="Project name")
    technologies: str = Field(..., description="Technologies used (comma-separated)")
    date: str = Field(..., description="Date or date range")
    bullets: List[str] = Field(..., description="Project descriptions and achievements")

    @field_validator('bullets')
    @classmethod
    def validate_bullets(cls, v: List[str]) -> List[str]:
        """Ensure bullets list is not empty."""
        if not v:
            raise ValueError("Project must have at least one bullet point")
        return v


class ResumeData(BaseModel):
    """Complete resume data structure."""
    personal_info: PersonalInfo = Field(..., description="Personal contact information")
    education: List[Education] = Field(..., description="Education history")
    experience: List[Experience] = Field(..., description="Work experience")
    projects: List[Project] = Field(default_factory=list, description="Projects (optional)")
    skills: Dict[str, List[str]] = Field(..., description="Skills organized by category")

    @field_validator('education')
    @classmethod
    def validate_education(cls, v: List[Education]) -> List[Education]:
        """Ensure at least one education entry."""
        if not v:
            raise ValueError("Resume must have at least one education entry")
        return v

    @field_validator('experience')
    @classmethod
    def validate_experience(cls, v: List[Experience]) -> List[Experience]:
        """Ensure at least one experience entry."""
        if not v:
            raise ValueError("Resume must have at least one experience entry")
        return v

    @field_validator('skills')
    @classmethod
    def validate_skills(cls, v: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Ensure skills dict is not empty."""
        if not v:
            raise ValueError("Resume must have at least one skills category")
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict) -> "ResumeData":
        """Create from dictionary (e.g., from YAML)."""
        return cls(**data)
