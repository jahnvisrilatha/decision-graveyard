"""LLM Client Abstraction for Decision Graveyard.

Supports:
- Google Gemini API (default recommended provider via GEMINI_API_KEY)
- OpenAI API (via OPENAI_API_KEY)
- Built-in Mock / Fallback Mode (for offline development and CI/testing)

Never hardcodes API keys; loads environment variables via python-dotenv.
Exposes a unified interface: generate_analysis(prompt)
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import requests
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """Configurable LLM client abstracting underlying providers (Gemini, OpenAI, Mock)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_to_mock: bool = True,
    ):
        """Initialize the LLM client.

        Args:
            provider: 'gemini', 'openai', or 'mock'. If None, reads LLM_PROVIDER or auto-detects.
            api_key: Optional explicit API key. If None, reads from environment variables.
            model: Optional model name. If None, reads GEMINI_MODEL or OPENAI_MODEL.
            fallback_to_mock: Whether to fall back to mock mode if an API call fails or keys are absent.
        """
        self.fallback_to_mock = fallback_to_mock

        # Read environment variables (never hardcode keys)
        self.gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.openai_api_key = api_key or os.getenv("OPENAI_API_KEY")

        # Determine provider
        env_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if provider:
            self.provider = provider.strip().lower()
        elif env_provider in ("gemini", "openai", "mock"):
            self.provider = env_provider
        elif self.gemini_api_key and not self._is_placeholder(self.gemini_api_key):
            self.provider = "gemini"
        elif self.openai_api_key and not self._is_placeholder(self.openai_api_key):
            self.provider = "openai"
        else:
            self.provider = "mock"

        # Model configuration
        if self.provider == "gemini":
            self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        elif self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.openai_base_url = os.getenv(
                "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
            )
        else:
            self.model = "mock-internal-reasoning"

        logger.info(
            f"Decision Graveyard LLMClient active with provider: '{self.provider}', model: '{self.model}'"
        )

    def _is_placeholder(self, key: Optional[str]) -> bool:
        """Check if an API key is just a placeholder template."""
        if not key:
            return True
        placeholders = [
            "your_gemini_api_key_here",
            "your_openai_api_key_here",
            "placeholder",
            "changeme",
        ]
        return any(p in key.lower() for p in placeholders)

    def generate_analysis(
        self, prompt: str, system_instruction: Optional[str] = None
    ) -> str:
        """Primary method to generate decision intelligence analysis from the LLM.

        The rest of the application does not need to know which provider is used.

        Args:
            prompt: Formatted prompt containing proposal, decisions, and context.
            system_instruction: Optional persona / system instruction for the LLM.

        Returns:
            String response (typically valid JSON formatted text).
        """
        if self.provider == "gemini" and self.gemini_api_key and not self._is_placeholder(self.gemini_api_key):
            try:
                return self._call_gemini(prompt, system_instruction)
            except Exception as e:
                logger.warning(f"Gemini API call failed: {e}")
                if self.fallback_to_mock:
                    logger.info("Falling back to local mock reasoning engine.")
                    return self._generate_mock_analysis(prompt)
                raise

        elif self.provider == "openai" and self.openai_api_key and not self._is_placeholder(self.openai_api_key):
            try:
                return self._call_openai(prompt, system_instruction)
            except Exception as e:
                logger.warning(f"OpenAI API call failed: {e}")
                if self.fallback_to_mock:
                    logger.info("Falling back to local mock reasoning engine.")
                    return self._generate_mock_analysis(prompt)
                raise

        else:
            # Default to mock/fallback mode
            return self._generate_mock_analysis(prompt)

    def generate_analysis_json(
        self, prompt: str, system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method that calls generate_analysis and returns parsed JSON dict."""
        raw_text = self.generate_analysis(prompt, system_instruction)
        return self._clean_and_parse_json(raw_text)

    # -----------------------------------------------------------------------
    # Provider Implementations
    # -----------------------------------------------------------------------

    def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate analysis using Google Gemini API (via google-genai SDK or direct REST)."""
        combined_text = ""
        if system_instruction:
            combined_text += f"{system_instruction}\n\n"
        combined_text += prompt
        combined_text += (
            "\n\nIMPORTANT: Return a pure JSON object without markdown formatting or code blocks."
        )

        # Try official google-genai SDK first
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
            response = client.models.generate_content(
                model=self.model,
                contents=combined_text,
                config=config,
            )
            if response.text:
                return response.text
        except ImportError:
            pass  # Fall back to direct REST API below
        except Exception as e:
            logger.warning(f"google-genai SDK call error ({e}). Trying direct HTTP REST...")

        # Direct REST API fallback
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.gemini_api_key}"
        )
        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [{"parts": [{"text": combined_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


    def _call_openai(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate analysis using OpenAI-compatible REST API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}",
        }

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({
            "role": "user",
            "content": prompt + "\n\nIMPORTANT: Return valid JSON matching the requested schema.",
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        response = requests.post(
            self.openai_base_url, headers=headers, json=payload, timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _generate_mock_analysis(self, prompt: str) -> str:
        """Deterministic mock generator allowing full agent testing without API calls.

        Identifies proposal ID or multi-proposal context from the prompt and returns
        a complete, structured JSON string.
        """
        # 1. Multi-proposal collective evaluation check
        if (
            "CURRENT PROPOSALS AND INITIATIVES TO EVALUATE COLLECTIVELY" in prompt
            or "MULTI-PROPOSAL" in prompt
            or "Composite Ghost Decision" in prompt
        ):
            multi_report = {
                "is_composite_ghost_detected": True,
                "headline": "Potential Composite Ghost Decision Detected: Proposals P005A, P005B, and P005C collectively recreate prior decision D001 (Employee Mobile Application).",
                "confidence_level": "High",
                "composite_ghost_groups": [
                    {
                        "matched_historical_decision_id": "D001",
                        "matched_historical_decision_title": "Employee Mobile Application",
                        "historical_status": "Abandoned",
                        "grouped_proposal_ids": ["P005A", "P005B", "P005C"],
                        "grouped_proposal_titles": [
                            "Mobile Attendance",
                            "Mobile Leave Management",
                            "Mobile Notifications",
                        ],
                        "composite_relationship_explanation": (
                            "Proposals P005A, P005B, and P005C individually present discrete mobile features, "
                            "but together they recreate the exact functional scope of historical decision D001 "
                            "(Employee Mobile Application), which attempted to build dedicated native apps and was abandoned in 2024."
                        ),
                        "historical_blockers": [
                            "Only 18% of employees regularly used mobile devices for company tasks in 2024.",
                            "The engineering team had only 5 developers.",
                            "Maintaining separate Android and iOS applications created significant development overhead.",
                            "The existing web portal already supported most required employee workflows.",
                            "Expected adoption did not justify the additional maintenance cost.",
                        ],
                        "lesson_learned": (
                            "A native mobile application should not be built when target user adoption is low "
                            "and the existing web platform already satisfies most of the required workflow."
                        ),
                        "blockers_that_still_apply": [
                            "Functional overlap with the existing employee web portal and Progressive Web Application (D006).",
                            "Developing and maintaining three separate mobile modules independently risks code duplication and fragmented release cycles.",
                            "Maintaining dedicated mobile apps requires ongoing mobile engineering capacity.",
                        ],
                        "blockers_that_may_have_changed": [
                            "Employee mobile adoption increased substantially from 18% in 2024 to 76% in 2026.",
                            "Engineering team capacity increased from 5 to 15 developers.",
                            "DevOps maturity transitioned from Low to High with automated CI/CD pipelines.",
                        ],
                        "blocker_comparisons": [
                            {
                                "historical_blocker": "Low employee mobile adoption: Only 18% of employees regularly used mobile devices for company tasks in 2024.",
                                "current_company_condition": "Employee mobile adoption has surged to 76% across the organization in 2026.",
                                "status": "May Have Changed",
                                "evidence_and_reasoning": "In 2024 (D001), lack of user demand made mobile apps unjustifiable. In 2026, 76% mobile adoption demonstrates proven user demand."
                            },
                            {
                                "historical_blocker": "Small engineering team capacity: The engineering team had only 5 developers to maintain core systems and mobile apps.",
                                "current_company_condition": "The engineering team has expanded by 200% to 15 developers in 2026.",
                                "status": "May Have Changed",
                                "evidence_and_reasoning": "Engineering team capacity tripled from 5 to 15 developers, though dedicated mobile specialization must still be verified."
                            },
                            {
                                "historical_blocker": "Low DevOps maturity: Manual deployment processes and lack of automated pipelines created high release friction in 2024.",
                                "current_company_condition": "DevOps maturity transitioned from Low to High with fully automated CI/CD pipelines in 2026.",
                                "status": "May Have Changed",
                                "evidence_and_reasoning": "Automated CI/CD pipelines and High DevOps maturity eliminate the manual release friction that contributed to abandoning D001."
                            },
                            {
                                "historical_blocker": "Existing web portal sufficiency: The existing web portal already supported most required employee workflows.",
                                "current_company_condition": "NovaTech maintains an active employee web portal AND successfully launched Progressive Web Application (D006) in May 2025.",
                                "status": "Still Applies",
                                "evidence_and_reasoning": "Historical decision D006 succeeded specifically because a PWA delivered mobile access without app store overhead. Building dedicated native apps duplicates capabilities already active in the PWA."
                            },
                            {
                                "historical_blocker": "High dual-platform native maintenance overhead: Maintaining separate Android and iOS applications created significant ongoing overhead.",
                                "current_company_condition": "NovaTech currently supports a unified web codebase via PWA (D006). Native apps re-introduce dual-platform App Store and Play Store overhead.",
                                "status": "Still Applies",
                                "evidence_and_reasoning": "Unless cross-platform tooling or PWA expansion is adopted, native mobile apps inherently require maintaining two independent codebases and app store releases."
                            },
                            {
                                "historical_blocker": "Fragmented scope and uncoordinated initiatives: Independent feature requests without unified architecture led to unsustainable maintenance.",
                                "current_company_condition": "Proposals P005A, P005B, and P005C are submitted as separate incremental initiatives rather than a unified mobile roadmap.",
                                "status": "Still Applies",
                                "evidence_and_reasoning": "Treating P005A, P005B, and P005C as isolated tickets risks code duplication and fragmented user experiences without an overarching architecture."
                            }
                        ],
                        "current_company_conditions": {
                            "mobile_adoption": "76%",
                            "engineering_team_size": 15,
                            "devops_maturity": "High",
                            "existing_solution": "Web-based employee portal and Progressive Web Application",
                            "total_employees": 5000
                        },
                        "human_review_questions": [
                            "Are P005A, P005B, and P005C intended to be built as separate native apps, a single native app, or extensions to the existing Progressive Web Application (D006)?",
                            "Can these three capabilities be delivered through the current PWA without incurring native mobile app store maintenance overhead?",
                            "Is there a coordinated product and engineering roadmap unifying these three mobile features to avoid duplicating the failure causes of D001?",
                        ],
                    }
                ],
                "reasoning": (
                    "Individually, proposals P005A, P005B, and P005C appear to be small, isolated feature additions. "
                    "However, when evaluated collectively, their combined scope encompasses employee attendance, leave management, "
                    "and push notifications—the exact composite scope of decision D001 ('Employee Mobile Application') from March 2024. "
                    "While organizational conditions have improved (76% mobile adoption, 15 engineers), the PM must evaluate whether "
                    "these features should be added to the existing Progressive Web Application (D006) rather than re-creating the overhead of D001."
                ),
                "guidance_for_product_manager": [
                    "Review whether these three initiatives should be consolidated under an overarching architecture rather than treated as uncoordinated tickets.",
                    "Check whether Progressive Web Application (D006) capabilities can satisfy employee attendance and notification needs directly.",
                    "Confirm ongoing mobile maintenance allocation across the 15-developer engineering team.",
                ],
            }
            return json.dumps(multi_report, indent=2)

        match = re.search(r"PROPOSAL ID:\s*([A-Za-z0-9_-]+)", prompt)
        proposal_id = match.group(1).upper() if match else "P001"

        if proposal_id in ("P001", "P005"):
            report = {
                "proposal_id": proposal_id,
                "proposal_title": "Unified Employee Mobile Platform" if proposal_id == "P001" else "Employee Mobile Feature Expansion",
                "related_historical_decisions": [
                    {
                        "decision_id": "D001",
                        "title": "Employee Mobile Application",
                        "status": "Abandoned",
                        "category": "Product",
                        "similarity_reason": "Attempted to build native Android and iOS mobile applications for employee attendance, leave management, and company notifications.",
                        "actual_outcome": "Project was abandoned after the initial development phase.",
                        "outcome_drivers": [
                            "Only 18% of employees regularly used mobile devices for company tasks in 2024.",
                            "The engineering team had only 5 developers.",
                            "Maintaining separate Android and iOS applications created significant development overhead.",
                            "Existing web portal already supported most required employee workflows."
                        ],
                        "lesson_learned": "A native mobile application should not be built when target user adoption is low and the existing web platform already satisfies most of the required workflow."
                    },
                    {
                        "decision_id": "D006",
                        "title": "Progressive Web Application",
                        "status": "Successful",
                        "category": "Product",
                        "similarity_reason": "Adopted PWA as a cost-effective mobile-friendly alternative after native app (D001) was abandoned.",
                        "actual_outcome": "Successfully launched and reached high employee adoption without app store overhead.",
                        "outcome_drivers": [
                            "Single codebase for both desktop and mobile.",
                            "Leveraged existing web development expertise without requiring mobile app store release cycles."
                        ],
                        "lesson_learned": "Progressive Web Applications are an effective middle ground when native mobile application maintenance overhead cannot be justified."
                    }
                ],
                "historical_outcomes": [
                    "Native mobile app (D001) was abandoned in 2024 due to high dual-platform overhead and low employee adoption (18%).",
                    "PWA initiative (D006) succeeded, providing responsive access to existing portal workflows."
                ],
                "historical_blockers": [
                    "Low employee mobile usage (18% in 2024).",
                    "Small engineering team (5 developers in 2024).",
                    "High dual-platform maintenance overhead (separate iOS and Android apps).",
                    "Redundancy with existing web portal."
                ],
                "current_conditions": {
                    "employees": 5000,
                    "mobile_adoption": "76%",
                    "engineering_team_size": 15,
                    "devops_maturity": "High",
                    "existing_solution": "Web-based employee portal and Progressive Web Application"
                },
                "historical_vs_current_comparison": (
                    "In 2024 (D001), employee mobile adoption was only 18% and the engineering team had 5 members. "
                    "In 2026, mobile adoption has surged to 76% and engineering has expanded to 15 developers with automated CI/CD. "
                    "However, NovaTech now already operates an active employee web portal and PWA."
                ),
                "blockers_that_may_still_apply": [
                    "Maintaining separate native iOS/Android codebases still requires dedicated mobile engineers.",
                    "Functional overlap with the already successful Progressive Web Application (D006) and web portal."
                ],
                "blockers_that_may_have_changed": [
                    "Employee mobile adoption increased from 18% to 76%.",
                    "Engineering team capacity increased from 5 to 15 developers.",
                    "Deployment and CI/CD maturity improved from manual to automated."
                ],
                "analysis": (
                    "Yes, NovaTech has tried this before. In March 2024, decision D001 ('Employee Mobile Application') attempted "
                    "to build native iOS and Android apps with attendance, leave management, and notifications. It was abandoned "
                    "because only 18% of employees used mobile for work and maintaining two native apps overwhelmed the 5-person team. "
                    "Today's conditions are significantly more favorable with 76% mobile adoption and 15 engineers. "
                    "However, because D006 (PWA) successfully solved the core web mobile access problem, the PM must justify why "
                    "dedicated native apps are required over enhancing the existing PWA."
                ),
                "questions_for_product_manager": [
                    "Can the desired mobile attendance and push notification capabilities be added directly to the existing Progressive Web Application (D006) instead of building a separate native app?",
                    "What specific device hardware APIs (e.g. background geolocation, biometric security) are strictly necessary that the current PWA cannot access?",
                    "Does the team have dedicated iOS and Android engineers to maintain separate app store submission lifecycles?"
                ]
            }
        elif proposal_id == "P002":
            report = {
                "proposal_id": "P002",
                "proposal_title": "Microservices Architecture for New Product",
                "related_historical_decisions": [
                    {
                        "decision_id": "D002",
                        "title": "Microservices Migration",
                        "status": "Abandoned",
                        "category": "Engineering",
                        "similarity_reason": "Attempted to migrate backend architecture from a monolith into microservices.",
                        "actual_outcome": "Project was abandoned after encountering high operational complexity.",
                        "outcome_drivers": [
                            "Team had limited distributed systems experience.",
                            "Low DevOps maturity with manual deployment processes.",
                            "Lack of centralized monitoring and observability.",
                            "Operational overhead exceeded engineering team capacity."
                        ],
                        "lesson_learned": "Microservices require adequate engineering capacity, DevOps maturity, automated deployment, and monitoring before adoption."
                    },
                    {
                        "decision_id": "D008",
                        "title": "Kubernetes Migration",
                        "status": "Successful",
                        "category": "Infrastructure",
                        "similarity_reason": "Migrated applications to Kubernetes container orchestration.",
                        "actual_outcome": "Successfully established modern containerized deployment infrastructure.",
                        "outcome_drivers": [
                            "Focused implementation scope.",
                            "Standardized container deployment."
                        ],
                        "lesson_learned": "Standardized container orchestration provides foundation for distributed services."
                    }
                ],
                "historical_outcomes": [
                    "Microservices migration (D002) abandoned in 2024 due to manual deployments and low DevOps maturity.",
                    "Kubernetes migration (D008) succeeded in 2025, providing a stable container platform."
                ],
                "historical_blockers": [
                    "Low DevOps maturity (2024).",
                    "Manual deployment pipeline.",
                    "Limited centralized monitoring and observability.",
                    "Lack of distributed systems experience in 5-person team."
                ],
                "current_conditions": {
                    "engineering_team_size": 15,
                    "devops_maturity": "High",
                    "deployment_process": "Automated CI/CD",
                    "monitoring": "Centralized monitoring and observability",
                    "container_platform": "Kubernetes"
                },
                "historical_vs_current_comparison": (
                    "In 2024, NovaTech attempted to break up an existing monolith with 5 developers, manual deployments, and no observability. "
                    "In 2026, NovaTech has 15 engineers, High DevOps maturity, automated CI/CD, Kubernetes in production, and centralized monitoring. "
                    "Crucially, P002 applies to a NEW product rather than refactoring a legacy monolith."
                ),
                "blockers_that_may_still_apply": [
                    "Managing inter-service communication contracts, API versioning, and distributed transaction boundaries.",
                    "Team distributed systems experience is moderate, requiring architectural guidelines."
                ],
                "blockers_that_may_have_changed": [
                    "DevOps maturity transitioned from Low to High.",
                    "Automated CI/CD is fully operational.",
                    "Kubernetes container platform is mature and running.",
                    "Centralized observability and monitoring are in place."
                ],
                "analysis": (
                    "Yes, NovaTech attempted microservices in 2024 (D002) and abandoned it because operational tooling was inadequate. "
                    "However, virtually all historical blockers identified in D002 have been resolved through the successful adoption "
                    "of Kubernetes (D008), automated CI/CD, centralized monitoring, and tripling the engineering team. "
                    "Furthermore, building a greenfield product with microservices carries lower risk than migrating a live legacy monolith."
                ),
                "questions_for_product_manager": [
                    "Have domain service boundaries been clearly defined to prevent creating a distributed monolith?",
                    "What are the latency and data consistency requirements between the proposed microservices?",
                    "Are shared libraries or standardized scaffolding in place for logging, tracing, and authentication?"
                ]
            }
        elif proposal_id == "P003":
            # Control case: No strong historical ghost
            report = {
                "proposal_id": "P003",
                "proposal_title": "Regional Customer Data Center Expansion",
                "ghost_detected": False,
                "confidence": "None",
                "is_potential_ghost": False,
                "confidence_level": "None",
                "headline": "No Strong Historical Ghost Detected: Routine infrastructure expansion without previous failure precedents.",
                "related_historical_decisions": [],
                "ghost_candidates": [],
                "historical_matches": [],
                "historical_status": "No Precedent Failure",
                "relationship_explanation": "This proposal introduces distinct operational scope that does not substantially recreate previously abandoned failure drivers.",
                "historical_outcomes": ["No direct prior failures in regional cloud expansion."],
                "historical_blockers": ["Network latency variability across non-peered regions."],
                "current_conditions": {
                    "customers_in_new_region": 2500,
                    "application_latency": "Higher than target",
                    "cloud_infrastructure": "Existing multi-region capable architecture"
                },
                "historical_vs_current_comparison": "NovaTech has not previously failed or abandoned a regional infrastructure expansion. Current multi-region architecture is mature.",
                "blockers_that_may_still_apply": ["Inter-region database replication latency."],
                "blockers_that_may_have_changed": ["Multi-region cloud tooling and cross-region VPC peering are now standard."],
                "analysis": (
                    "No strong historical ghost decision detected for proposal P003 (Regional Customer Data Center Expansion). "
                    "NovaTech's organizational memory does not contain an abandoned or failed regional infrastructure project. "
                    "This represents standard operational scaling to support 2,500 regional customers."
                ),
                "questions_for_product_manager": [
                    "What are the projected cross-region data transfer costs?",
                    "Is database replication asynchronous or synchronous between regions?",
                    "Does local data residency compliance require isolated customer storage?"
                ]
            }
        else:
            # P004 and other business strategy proposals
            report = {
                "proposal_id": proposal_id or "P004",
                "proposal_title": "Tiered Subscription Pricing" if proposal_id == "P004" else "Proposal Analysis",
                "ghost_detected": True,
                "confidence": "High",
                "is_potential_ghost": True,
                "confidence_level": "High",
                "headline": "Potential Ghost Decision Detected: Proposal relates to prior decision D004 (Subscription Pricing Model).",
                "related_historical_decisions": [
                    {
                        "decision_id": "D004",
                        "title": "Subscription Pricing Model",
                        "status": "Failed",
                        "category": "Business Strategy",
                        "similarity_reason": "Evaluated revenue and business model transition from usage-based to flat subscription tiers.",
                        "actual_outcome": "Failed due to customer churn caused by a one-size-fits-all model without segmentation.",
                        "outcome_drivers": ["Lack of usage segmentation and tier differentiation."],
                        "lesson_learned": "Pricing changes require granular customer usage segmentation."
                    }
                ],
                "ghost_candidates": [
                    {
                        "decision_id": "D004",
                        "title": "Subscription Pricing Model",
                        "status": "Failed",
                        "category": "Business Strategy",
                        "relationship_explanation": "Attempting subscription pricing model transition previously tried in D004.",
                        "historical_outcome": "Failed due to customer churn from one-size-fits-all model.",
                        "historical_blockers": [
                            "Incomplete customer behavior data and lack of usage tiers."
                        ],
                        "lesson_learned": "Pricing changes require granular customer usage segmentation.",
                        "blockers_that_may_still_apply": [
                            "Customer friction during contract renewals."
                        ],
                        "blockers_that_may_have_changed": [
                            "Granular customer segmentation data is now available."
                        ]
                    }
                ],
                "historical_matches": ["D004"],
                "historical_status": "Failed",
                "relationship_explanation": "Proposal P004 relates to historical decision D004 (Subscription Pricing Model), which failed when implemented without usage segmentation.",
                "historical_outcomes": ["Past strategic pricing model failed due to lack of usage segmentation."],
                "historical_blockers": ["Incomplete customer behavior data and lack of usage tiers."],
                "current_conditions": {"customer_base": 20000, "customer_usage_segmentation": "Available"},
                "historical_vs_current_comparison": "Current organization has 20,000 customers and granular usage data available.",
                "blockers_that_may_still_apply": ["Customer friction during contract renewals."],
                "blockers_that_may_have_changed": ["Granular customer segmentation data is now available."],
                "analysis": (
                    f"NovaTech has historical precedents regarding strategic initiatives in proposal {proposal_id}. "
                    "In 2024, D004 (Subscription Pricing Model) failed because a single pricing model alienated light users. "
                    "Proposal P004 explicitly mitigates this by introducing tiered pricing based on segmented usage analytics."
                ),
                "questions_for_product_manager": [
                    "How are the tier limits calibrated to ensure low-volume customers are not penalized?",
                    "What telemetry will be monitored to gauge early subscriber churn?"
                ]
            }

        return json.dumps(report, indent=2)

    def _clean_and_parse_json(self, raw_text: str) -> Dict[str, Any]:
        """Strip markdown fences and parse clean JSON."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)
