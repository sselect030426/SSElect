from django.apps import AppConfig


# now what is a signals then
class ReviewsConfig(AppConfig):
    name = "reviews"

    def ready(self):
        import reviews.signals
