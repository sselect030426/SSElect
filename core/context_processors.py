from django.conf import settings


def contact_info(request):
    """
    Returns site contact information from settings to all templates.
    """
    return {
        "contact": getattr(settings, "SITE_CONTACT", {})
    }  # do i realy  need te context processor as a seprate file
