"""Create (or update) the Compass Bedrock guardrail and store its id in SSM /compass/guardrail_id.

  python -m scripts.create_guardrail
"""
import boto3

REGION = "us-west-2"
NAME = "compass-guardrail"
br = boto3.client("bedrock", region_name=REGION)

TOPICS = [
    {"name": "Diagnosis", "type": "DENY",
     "definition": "Naming, suggesting or assessing a medical or mental health condition, disorder or illness for the user.",
     "examples": ["Do I have depression?", "Sounds like you have ADHD.", "Is this an anxiety disorder?"]},
    {"name": "Medication advice", "type": "DENY",
     "definition": "Advice about taking, dosing, combining, stopping or obtaining medications, supplements or drugs, including sleep aids.",
     "examples": ["What pills help me sleep?", "How much melatonin should I take?", "Can I take Adderall to study?"]},
    {"name": "Self-harm methods", "type": "DENY",
     "definition": "Any information about methods, means, amounts or plans for self-harm or suicide.",
     "examples": ["How many pills would it take?", "What is the most painless way?", "Where is a high bridge near campus?"]},
]


def main() -> None:
    kw = dict(
        description="Compass: student wellness navigator. No diagnosis, no medication advice, no self-harm methods, no PII, no prompt attacks.",
        topicPolicyConfig={"topicsConfig": TOPICS},
        contentPolicyConfig={"filtersConfig": [
            {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "INSULTS", "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "VIOLENCE", "inputStrength": "MEDIUM", "outputStrength": "HIGH"},
            {"type": "MISCONDUCT", "inputStrength": "MEDIUM", "outputStrength": "HIGH"},
            {"type": "SEXUAL", "inputStrength": "HIGH", "outputStrength": "HIGH"},
            {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
        ]},
        sensitiveInformationPolicyConfig={"piiEntitiesConfig": [
            # Only email and SSN: resource answers legitimately contain venue names ("Paul Robeson Campus Center"),
            # phone numbers and street addresses from public listings. Names in student posts are held by wins moderation.
            {"type": t, "action": "ANONYMIZE"} for t in ("EMAIL", "US_SOCIAL_SECURITY_NUMBER")
        ]},
        blockedInputMessaging="Compass can only help with campus resources and events.",
        blockedOutputsMessaging="Compass can only help with campus resources and events.",
        tags=[{"key": "project", "value": "compass"}],
    )
    existing = [g for g in br.list_guardrails()["guardrails"] if g["name"] == NAME]
    if existing:
        gid = existing[0]["id"]
        kw.pop("tags")
        br.update_guardrail(guardrailIdentifier=gid, name=NAME, **kw)
    else:
        gid = br.create_guardrail(name=NAME, **kw)["guardrailId"]
    ver = br.create_guardrail_version(guardrailIdentifier=gid, description="compass v1")["version"]
    boto3.client("ssm", region_name=REGION).put_parameter(Name="/compass/guardrail_id", Value=f"{gid}:{ver}", Type="String", Overwrite=True)
    print("guardrail", gid, "version", ver)


if __name__ == "__main__":
    main()
