"""The crisis response is fixed content plus rows from crisis_lines. No model writes any of it."""
from datetime import datetime

from app.models.common import CrisisLine, CrisisResponse, SupportCard, SupportOption

COPY = {
    "en": ("You don't have to handle this alone",
           "It sounds like things are really hard right now. You can reach a real person right now, any time, for free."),
    "es": ("No tienes que pasar por esto solo",
           "Parece que las cosas están muy difíciles ahora. Puedes hablar con una persona real ahora mismo, a cualquier hora y gratis."),
}

CONCERN_COPY = {
    "en": ("People you can talk to", "That sounds like a lot. If talking to someone would help, these are free for Rutgers students."),
    "es": ("Personas con quienes hablar", "Eso suena a mucho. Si hablar con alguien te ayuda, estos servicios son gratis para estudiantes de Rutgers."),
}


def crisis_lines(conn, campus: str, lang: str = "en") -> list[CrisisLine]:
    rows = conn.execute(
        """SELECT id, name, kind, contact, href, hours, campus, language, verified FROM crisis_lines
           WHERE campus IN ('all', %s) AND (language IN ('any', %s))
           ORDER BY (campus = 'all') DESC, sort, id""",
        (campus, lang),
    ).fetchall()
    return [CrisisLine(**{**r, "language": r["language"] if r["language"] in ("en", "es") else "any"}) for r in rows]


def crisis_response(conn, campus: str, lang: str, now: datetime, synthetic: bool = True) -> CrisisResponse:
    title, message = COPY.get(lang, COPY["en"])
    return CrisisResponse(synthetic=synthetic, now=now, title=title, message=message, lines=crisis_lines(conn, campus, lang))


SUPPORT = {
    "new_brunswick": [
        SupportOption(name="CAPS (Counseling, ADAP & Psychiatric Services)", kind="in_person", contact="848-932-7884",
                      url="https://health.rutgers.edu/medical-and-counseling-services/counseling-services",
                      address="17 Senior Street, New Brunswick, NJ 08901", hours="Call for options this week; after hours follow the prompts",
                      campus="new_brunswick"),
    ],
    "newark": [
        SupportOption(name="Rutgers–Newark Counseling Center", kind="in_person", contact="973-353-5805",
                      url="https://studentaffairs.newark.rutgers.edu/health-wellness/counseling-center",
                      address="Blumenthal Hall, 249 University Ave, Room 101, Newark, NJ 07102", hours="Mon–Fri 8:30 am–4:30 pm; telehealth available",
                      campus="newark"),
    ],
    "camden": [
        SupportOption(name="Rutgers–Camden Student Wellness Center", kind="in_person", contact="856-225-6005",
                      url="https://wellnesscenter.camden.rutgers.edu/", address="326 Penn Street, Campus Center 2nd floor, Camden, NJ",
                      hours="Mon–Fri 8:30 am–4:30 pm", campus="camden"),
    ],
}
SHARED_SUPPORT = [
    SupportOption(name="Uwill teletherapy", kind="teletherapy", url="https://app.uwill.com", hours="Evenings and weekends available", campus="online"),
    SupportOption(name="Togetherall peer community", kind="peer", url="https://togetherall.com", hours="24/7, moderated by licensed practitioners", campus="online"),
]

CARE_FIRST_COPY = {
    "en": ("Talking to someone can help",
           "Right now a person might be a better first step than an event. That's not a label, just an offer. All of these are free for Rutgers students."),
    "es": ("Hablar con alguien puede ayudar",
           "Ahora mismo, hablar con una persona puede ser un mejor primer paso que un evento. No es una etiqueta, solo una oferta. Todo esto es gratis para estudiantes de Rutgers."),
}


def support_card(campus: str, lang: str, kind: str = "care_first") -> SupportCard:
    title, message = (CARE_FIRST_COPY if kind == "care_first" else CONCERN_COPY).get(lang, CARE_FIRST_COPY["en"])
    return SupportCard(title=title, message=message, options=SUPPORT.get(campus, SUPPORT["new_brunswick"]) + SHARED_SUPPORT)
