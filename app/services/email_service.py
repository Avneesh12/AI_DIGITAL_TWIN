import httpx
from app.config import get_settings
from loguru import logger
from app.utils.email_templates import render_template

settings = get_settings()

BREVO_URL = "https://api.brevo.com/v3/smtp/email"

async def send_welcome_email(email: str, name: str):
    try:
        html_content = render_template("welcome.html", {
            "name": name,
            "frontend_url": settings.FRONTEND_URL
        })

        payload = {
            "sender": {
                "name": settings.EMAIL_SENDER_NAME,
                "email": settings.EMAIL_SENDER
            },
            "to": [{"email": email, "name": name}],
            "subject": "Welcome to Digital Twin 🚀",
            "htmlContent": html_content,
            "textContent": f"Welcome {name}! Visit {settings.FRONTEND_URL}"
        }

        headers = {
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(BREVO_URL, json=payload, headers=headers)

        if response.status_code != 201:
            logger.error(f"Email failed: {response.text}")
        else:
            logger.info(f"Welcome email sent to {email}")

    except Exception as e:
        logger.error(f"Email exception: {str(e)}")