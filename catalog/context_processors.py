def user_language(request):
    """Добавляет язык пользователя в контекст всех шаблонов"""
    if request.user.is_authenticated:
        language = getattr(request.user.profile, 'language', 'ru')
    else:
        language = request.session.get('language', 'ru')
    return {'user_language': language}
