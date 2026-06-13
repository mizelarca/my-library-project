from django import template

register = template.Library()

@register.filter
def ru_plural(value, forms):
    """Возвращает правильную форму слова для русского языка"""
    try:
        value = int(value)
    except (ValueError, TypeError):
        return forms.split(',')[2]

    forms_list = forms.split(',')
    if len(forms_list) != 3:
        return forms

    if 11 <= value % 100 <= 19:
        return forms_list[2]

    remainder = value % 10
    if remainder == 1:
        return forms_list[0]
    elif 2 <= remainder <= 4:
        return forms_list[1]
    else:
        return forms_list[2]

@register.filter
def mood_emoji(value):
    emoji_map = {
        'sad': '😢',
        'funny': '😂',
        'shocking': '🤯',
        'cozy': '🥰',
        'exciting': '🔥',
        'thoughtful': '🤔',
        'useful': '🎯',
        'calming': '😌',
        'angry': '🤬',
        'beautiful': '🎨',
    }
    return emoji_map.get(value, '')

@register.filter
def get_item(list, index):
    """Получает элемент списка по индексу"""
    try:
        return list[index]
    except (IndexError, TypeError):
        return 0

@register.filter
def multiply(value, arg):
    """Умножение"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Деление"""
    try:
        if int(arg) == 0:
            return 0
        return int(value) / int(arg)
    except (ValueError, TypeError):
        return 0
