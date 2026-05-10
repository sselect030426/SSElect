import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from products.models import Product, Category

logger = logging.getLogger(__name__)


def home(request):
    products = Product.objects.filter(is_active=True).order_by("-average_rating")[:8]
    categories = Category.objects.filter(is_active=True)[:6]
    return render(request, "core/home.html", {
        "products": products,
        "categories": categories
    })


def about(request):
    return render(request, "core/about.html")


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        
        logger.info(f"Contact form submitted: {name} ({email}) - {subject}")
        
        # Email Context
        context = {
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
        }
        
        # Render HTML and Plain Text
        html_message = render_to_string("emails/contact_email.html", context)
        plain_message = strip_tags(html_message) # what does this line  do 
        try:
            send_mail( #  what is this ? does it have special config too 
                f"Contact Form: {subject}",
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                html_message=html_message,
                fail_silently=False,
            )
            print(f"✅ SUCCESS: Contact email sent successfully from {settings.DEFAULT_FROM_EMAIL}")
            messages.success(request, f"Thank you {name}! Your message has been sent.")
        except Exception as e: # i need to create some other type of exceptio mtoo . now it only catches the deault one i need to caqtch all the ones sepratly while giving the seprate warning 
            logger.error(f"Error sending contact email: {e}")
            messages.error(request, "There was an error sending your message. Please try again later.")
        
        return redirect("core:contact") # this i happpend afyer the message has sent and can i use this indide like notmal statement .  why return 
        
    return render(request, "core/contact.html")


def partnership(request):
    if request.method == "POST":
        business_name = request.POST.get("business_name", "").strip()
        contact_person = request.POST.get("contact_person", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone_number", "").strip()
        business_type = request.POST.get("business_type", "").strip()
        message = request.POST.get("message", "").strip()
        logger.info(f"Partnership inquiry: {business_name} (Contact: {contact_person})")
        # Email Context
        context = {
            "business_name": business_name,
            "contact_person": contact_person,
            "email": email,
            "phone": phone,
            "business_type": business_type,
            "message": message,
        }
        
        # Render HTML and Plain Text
        html_message = render_to_string("emails/partnership_email.html", context)
        plain_message = strip_tags(html_message) # what dies this strip_tags do 
        
        try:
            send_mail(
                f"Partnership Inquiry: {business_name}",
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                html_message=html_message,
                fail_silently=False,
            )
            print(f"✅ SUCCESS: Partnership inquiry sent successfully for {business_name}")
            messages.success(request, f"Thank you {contact_person}! Your partnership inquiry for {business_name} has been received.")
        except Exception as e:
            logger.error(f"Error sending partnership email: {e}")
            messages.error(request, "There was an error sending your inquiry. Please try again later.")
            
        return redirect("core:partnership")
        
    return render(request, "core/partnership.html")
