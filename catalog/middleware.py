from django.utils import translation

class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                language = request.user.profile.language
                if language:
                    translation.activate(language)
                    request.LANGUAGE_CODE = language
                    request.session['language'] = language
                else:
                    translation.activate('ru')
            except:
                translation.activate('ru')
        else:
            language = request.session.get('language', 'ru')
            translation.activate(language)
        
        response = self.get_response(request)
        return response
